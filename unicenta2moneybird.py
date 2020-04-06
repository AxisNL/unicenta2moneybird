import configparser
import decimal
import sys
import datetime
import argparse

from lib import uc, mb, log

parser = argparse.ArgumentParser(description='Sync iZettle to your Moneybird account.')
parser.add_argument('-n', '--noop', dest='noop', action='store_true', help="Only read, do not really change anything")
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help="Print extra output")
parser.add_argument('--startdate', dest='startdatestring', type=str, help="The date to start on, in the "
                                                                          "example format 31122019 for dec "
                                                                          "31st, 2019. If not specified, it "
                                                                          "will be yesterday.")
parser.add_argument('--enddate', dest='enddatestring', type=str, help="The date to start on, in the "
                                                                      "example format 31122019 for dec "
                                                                      "31st, 2019. If not specified, it "
                                                                      "will be tomorrow.")
args = parser.parse_args()
flagNoop = args.noop
flagVerbose = args.verbose

uc.flagVerbose = flagVerbose
mb.flagVerbose = flagVerbose
mb.flagNoop = flagNoop

######################################
# CONFIGURE LOGGING
# ####################################
logger = log.logger(flagVerbose)

######################################
# CHECK REQUIREMENTS
# ####################################

if sys.version_info <= (3, 6, 0):
    logger.critical("You are running Python version {0}, but ony >= 3.6 is tested".format(sys.version_info))
    exit(1)

######################################
# GET THE PARAMETERS FROM THE CONFIG FILE
# ####################################
config = configparser.ConfigParser()
config.read('etc/unicenta2moneybird.conf')

######################################
# PARSING INPUT
# ####################################

# SET THE DEFAULT START AND END DATES
date = datetime.datetime.today()
days_back_default = int(config['Global']['default_days_back'])
startDate = (date + datetime.timedelta(days=(0 - days_back_default)))
endDate = (date + datetime.timedelta(days=1))

if args.startdatestring is not None:
    try:
        startDate = datetime.datetime.strptime(args.startdatestring, "%d%m%Y").date()
    except ValueError as err:
        logger.exception("Could not convert '{0}' to date: {1}".format(args.startdatestring, err))
        exit(1)

if flagVerbose:
    logger.info("Starting date: {0}".format(startDate))

if args.enddatestring is not None:
    try:
        endDate = datetime.datetime.strptime(args.enddatestring, "%d%m%Y").date()
    except ValueError as err:
        logger.exception("Could not convert '{0}' to date: {1}".format(args.enddatestring, err))
        exit(1)

if flagVerbose:
    logger.info("Ending date: {0}".format(endDate))


######################################
# DOWNLOAD ALL REQUIRED DATA
# ####################################
uc.DownloadTickets()
uc.DownloadTicketLines()
uc.DownloadReceipts()
uc.DownloadPayments()
uc.DownloadTaxes()

mb.DownloadContacts()
mb.DownloadFinancialAccounts()
mb.DownloadLedgerAccounts()
mb.DownloadTaxRates()
mb.DownloadFinanancialMutations(startDate, endDate)
mb.DownloadSalesInvoices(startDate, endDate)
mb.DownloadPurchaseInvoices(startDate, endDate)

######################################
# PROCESS SALES (uc receipts)
# ####################################

uc.TransformSales(startDate, endDate)

sales = uc.GetTransformedSales()

# print(json.dumps(sales, sort_keys=True, indent=2, default=uc.json_serial))

flagMadeChanges = False
for sale in sales:
    flagFound = False
    # vergelijk met de Moneybird facturen
    for mbFactuur in mb.GetSalesInvoices():
        if mbFactuur['reference'] == sale['reference']:
            flagFound = True

    if not flagFound:
        # Voeg de invoice toe
        if flagNoop:
            logger.info("NOOP: Sales invoice with reference '{0}' should be added, but read-only mode is preventing "
                        "updates".format(sale['reference']))
        else:
            date = datetime.datetime.strptime(sale['date'], "%Y-%m-%dT%H:%M:%S")
            print(date)
            print("-------")
            ucProducts = sale['products']
            details_attributes = []
            for ucProduct in ucProducts:
                products = {"id": ucProduct['number'],
                            "description": ucProduct['description'],
                            "price": ucProduct['priceexcl'] * (1 + ucProduct['taxrate']),
                            "amount": ucProduct['quantity'],
                            "tax_rate": ucProduct['taxrate']*100
                            }
                details_attributes.append(products)
            new_id = mb.AddSalesInvoice(sale['reference'], date, details_attributes)
            logger.info("Created sales invoice ({0})".format(sale['reference']))
            if new_id is not None:
                mb.SendInvoice(new_id)
            flagMadeChanges = True

    if flagFound:
        logger.debug("Sales invoice already exists ({0})".format(sale['reference']))
# all done, now re-download the purchase invoices from moneybird
if flagMadeChanges:
    logger.info("Made changes, so re-downloading the Moneybird purchases")
    mb.DownloadPurchaseInvoices(startDate, endDate)

######################################
# PROCESS PAYMENTS
# ####################################

flagFinancialStatementsChanged = False

for sale in sales:
    for payment in sale['payments']:
        payment_reference = 'betaling van {0}'.format(sale['reference'])
        payment_date = datetime.datetime.strptime(sale['date'], "%Y-%m-%dT%H:%M:%S")

        flagFinancialMutationFound = False
        for mbFinancialMutation in mb.GetFinancialMutations():
            if mbFinancialMutation['message'] == payment_reference:
                flagFinancialMutationFound = True

        if not flagFinancialMutationFound:
            if flagNoop:
                logger.info("NOOP: should create financial statement {0}, but in read-only mode.".format(payment_reference))
            else:
                mb.AddFinancialStatementAndMutation(payment_reference, date, payment['amount'])
                logger.info("Created financial statement ({0}".format(payment_reference))
                flagFinancialStatementsChanged = True

        if flagFinancialMutationFound:
            logger.debug("Financial statement already exists ({0})".format(payment_reference))

if flagFinancialStatementsChanged:
    logger.info("Financial mutations were changed, re-downloading")
    mb.DownloadFinanancialMutations(startDate, endDate)

######################################
# PROCESS LINKS
######################################

# Now we will start the cross-checks to see if stuff needs to be linked.

for fm in mb.GetFinancialMutations():
    fmreference = str(fm['message'])
    if fmreference.startswith('betaling van POS verkoop'):
        # this is one of our UC financial statements
        fm_payments = fm['payments']
        fm_ledger_account_bookings = fm['ledger_account_bookings']
        fm_amount = decimal.Decimal(fm['amount'])

        if len(fm_payments) == 0:
            # these are no payments for this financial mutation, so we need to start linking!

            # this is a sales invoice. Find the sales invoice to go with it.
            flagSalesInvoiceFound = False
            for si in mb.GetSalesInvoices():
                sireference = str(si['reference'])

                if sireference in fmreference:
                    flagSalesInvoiceFound = True
                    if flagNoop:
                        logger.info(
                            "NOOP: should create link for financial mutation {0}, but in read-only mode.".format(
                                fmreference))
                    else:
                        mb.LinkSalesInvoice(fm['id'], si['id'], fm_amount)
                        logger.info("Created link for financial mutation {0}.".format(fmreference))
            if not flagSalesInvoiceFound:
                logger.info("Could not find a sales invoice for financial statement {0}, ignoring.".format(
                    fmreference))

logger.info("All done!")
