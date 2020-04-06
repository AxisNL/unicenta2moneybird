import configparser
import decimal
import json
import os
import sys
import dateutil.parser
import datetime
import argparse
import logging
import logging.handlers
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
# PARSING INPUT
# ####################################

# SET THE DEFAULT START AND END DATES
date = datetime.datetime.today()
startDate = (date + datetime.timedelta(days=-1))
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
# GET THE PARAMETERS FROM THE CONFIG FILE
# ####################################
config = configparser.ConfigParser()
config.read('etc/unicenta2moneybird.conf')

######################################
# DOWNLOAD ALL REQUIRED DATA
# ####################################
uc.DownloadTickets()
uc.DownloadTicketLines()
uc.DownloadReceipts()
uc.DownloadPayments()
uc.DownloadTaxes()

# mb.DownloadContacts()
# mb.DownloadFinancialAccounts()
# mb.DownloadLedgerAccounts()
# mb.DownloadTaxRates()
# mb.DownloadFinanancialMutations(startDate, endDate)
# mb.DownloadSalesInvoices(startDate, endDate)
# mb.DownloadPurchaseInvoices(startDate, endDate)


######################################
# PROCESS SALES (iZettle purchases)
# ####################################
#
# # Compare the iZettle purchases with the Moneybird purchases
# logger.info("Processing the iZettle purchases")
#
# flagMadeChanges = False
# for izPurchase in iz.GetPurchases():
#
#     globalPurchaseNumber = izPurchase['globalPurchaseNumber']
#
#     if len(izPurchase['payments']) == 0:
#         logger.error("This purchase (globalPurchaseNumber {0}) has no payments, not supported".format(globalPurchaseNumber))
#     if len(izPurchase['payments']) > 1:
#         logger.error(
#             "This purchase (globalPurchaseNumber {0}) has more than one payment, not supported".format(globalPurchaseNumber))
#
#     fmreference = "Izettle verkoop {0}".format(globalPurchaseNumber)
#     logger.info("Processing iZettle purchase {0}".format(globalPurchaseNumber))
#     flagFound = False
#     # vergelijk met de Moneybird facturen
#     for mbFactuur in mb.GetSalesInvoices():
#         if mbFactuur['reference'] == fmreference:
#             flagFound = True
#
#     if not flagFound:
#         # Voeg de invoice toe
#         if flagNoop:
#             logger.info("NOOP: Sales invoice with reference '{0}' should be added, but read-only mode is preventing updates".format(fmreference))
#         else:
#             timestamp = dateutil.parser.parse(izPurchase['timestamp'])
#             izProducts = izPurchase['products']
#             details_attributes = []
#             for izProduct in izProducts:
#                 unitPriceCents = int(izProduct['unitPrice'])
#                 quantity = int(izProduct['quantity'])
#                 totalproductcents = unitPriceCents * quantity
#                 totalproductamount = decimal.Decimal(totalproductcents / 100.0)
#                 products = {"description": izProduct['name'],
#                             "price": totalproductamount,
#                             "tax_rate": izProduct['vatPercentage']
#                             }
#                 details_attributes.append(products)
#             new_id = mb.AddSalesInvoice(fmreference, timestamp, details_attributes)
#             logger.info("Created sales invoice ({0})".format(fmreference))
#             if not new_id is None:
#                 mb.SendInvoice(new_id)
#             flagMadeChanges = True
#
#     if flagFound:
#         logger.debug("Sales invoice already exists ({0})".format(fmreference))
# # all done, now re-download the purchase invoices from moneybird
# if flagMadeChanges:
#     logger.info("Made changes, so re-downloading the Moneybird purchases")
#     mb.DownloadPurchaseInvoices(startDate, endDate)
#
# ######################################
# # PROCESS IZETTLE TRANSACTIONS
# ######################################
#
# # We will first walk through all transactions and set up the purchase invoices and financial statements (so we can link
# # them later in another step
#
# flagPurchaseInvoicesChanged = False
# flagFinancialStatementsChanged = False
#
# for izTransaction in iz.GetTransactions():
#
#     transactioncode = izTransaction['originatorTransactionType']
#     trans_orig_uuid = izTransaction['originatingTransactionUuid']
#     fmreference = "IZETTLE_{0}_{1}_{2}".format(transactioncode, izTransaction['timestamp'], trans_orig_uuid)
#
#     if transactioncode not in ['CARD_PAYMENT', 'CARD_PAYMENT_FEE', 'PAYOUT']:
#         logger.error("Transaction code {0} not handled!".format(transactioncode))
#         exit(1)
#
#     amount_cents = int(izTransaction['amount'])
#     # always get a positive number to work with
#     if amount_cents < 0:
#         amount_cents = 0 - amount_cents
#     amount_dec = decimal.Decimal(amount_cents / 100.0)
#
#     timestamp = dateutil.parser.parse(izTransaction['timestamp'])
#
#     ##############################
#     # Check the financial statements
#     ##############################
#     flagFinancialMutationFound = False
#     for mbFinancialMutation in mb.GetFinancialMutations():
#         if mbFinancialMutation['message'] == fmreference:
#             flagFinancialMutationFound = True
#
#     if not flagFinancialMutationFound:
#         if flagNoop:
#             logger.info("NOOP: should create financial statement {0}, but in read-only mode.".format(fmreference))
#         else:
#             mb.AddFinancialStatementAndMutation(fmreference, transactioncode, timestamp, amount_dec)
#             logger.info("Created financial statement ({0}".format(fmreference))
#             flagFinancialStatementsChanged = True
#
#     if flagFinancialMutationFound:
#         logger.debug("Financial statement already exists ({0})".format(fmreference))
#
#     ##############################
#     # Create purchase invoices
#     ##############################
#     if transactioncode == 'CARD_PAYMENT_FEE':
#
#         # ###############################################
#         # check if we have a purchase invoice
#         purchasereference = "Izettle inkoop {0}".format(trans_orig_uuid)
#
#         flagPurchaseInvoiceFound = False
#         for mbPurchaseinvoice in mb.GetPurchaseInvoices():
#             if mbPurchaseinvoice['reference'] == purchasereference:
#                 flagPurchaseInvoiceFound = True
#
#         if not flagPurchaseInvoiceFound:
#             if flagNoop:
#                 logger.info("Noop: should create purchase invoice {0}, but in read-only mode".format(fmreference))
#             else:
#                 mb.AddPurchaseInvoice(purchasereference, timestamp, amount_dec)
#                 logger.info("Created purchase invoice ({0}".format(fmreference))
#                 flagPurchaseInvoicesChanged = True
#
#         if flagPurchaseInvoiceFound:
#             logger.debug("Purchase invoice already exists ({0})".format(purchasereference))
#
# if flagPurchaseInvoicesChanged:
#     logging.info("Purchase invoices were changed, re-downloading")
#     mb.DownloadPurchaseInvoices(startDate, endDate)
#
# if flagFinancialStatementsChanged:
#     logging.info("Financial mutations were changed, re-downloading")
#     mb.DownloadFinanancialMutations(startDate, endDate)
#
#
# ######################################
# # PROCESS LINKS
# ######################################
#
# # Now we will start the cross-checks to see if stuff needs to be linked.
#
# for fm in mb.GetFinancialMutations():
#     fmreference = str(fm['message'])
#     if fmreference.startswith('IZETTLE_'):
#         # this is one of our iZettle financial statements
#         fm_payments = fm['payments']
#         fm_ledger_account_bookings = fm['ledger_account_bookings']
#
#         trans_orig_uuid = str(fm['message']).split('_')[-1]
#         amount = mb.MakePositive(decimal.Decimal(fm['amount']))
#
#         if fmreference.startswith('IZETTLE_CARD_PAYMENT_FEE_'):
#             if len(fm_payments) == 0:
#                 # these are no payments for this financial mutation, so we need to start linking!
#                 # this is a purchase invoice. Find the purchase invoice to go with it.
#                 flagPurchaseInvoiceFound = False
#                 for pi in mb.GetPurchaseInvoices():
#                     pireference = str(pi['reference'])
#                     if pireference.startswith('Izettle inkoop '):
#                         uuid = pireference.split(' ')[-1]
#                         if uuid == trans_orig_uuid:
#                             flagPurchaseInvoiceFound = True
#                             if flagNoop:
#                                 logging.info("NOOP: should create link for financial mutation {0}, but in read-only mode.".format(fmreference))
#                             else:
#                                 mb.LinkPurchaseInvoice(fm['id'], pi['id'], amount)
#                                 logging.info("Created link for financial mutation {0}.".format(fmreference))
#                 if not flagPurchaseInvoiceFound:
#                     logging.info("Could not find a purchange invoice for financial statement {0}, ignoring.".format(fmreference))
#
#         if fmreference.startswith('IZETTLE_CARD_PAYMENT_'):
#             if len(fm_payments) == 0:
#                 # these are no payments for this financial mutation, so we need to start linking!
#
#                 # this is a sales invoice. Find the sales invoice to go with it.
#                 flagSalesInvoiceFound = False
#                 for si in mb.GetSalesInvoices():
#                     sireference = str(si['reference'])
#
#                     if sireference.startswith('Izettle verkoop '):
#                         try:
#                             izSalesNumber = int(sireference.split(' ')[-1])
#                         except ValueError:
#                             logging.error("Could not parse a sales invoice with reference '{0}'. I am expecting 'Izettle verkoop <int>'. If you need to do a manual transaction, make sure it does not start with 'Izettle verkoop '".format(sireference))
#                             exit(1)
#                         izSalesPaymentUuid = iz.LookupSalesPaymentUuid(izSalesNumber)
#                         if izSalesPaymentUuid == trans_orig_uuid:
#                             flagSalesInvoiceFound = True
#                             if flagNoop:
#                                 logging.info(
#                                     "NOOP: should create link for financial mutation {0}, but in read-only mode.".format(
#                                         fmreference))
#                             else:
#                                 mb.LinkSalesInvoice(fm['id'], si['id'], amount)
#                                 logging.info("Created link for financial mutation {0}.".format(fmreference))
#                 if not flagSalesInvoiceFound:
#                     logging.info("Could not find a sales invoice for financial statement {0}, ignoring.".format(
#                         fmreference))
#
#         if fmreference.startswith('IZETTLE_PAYOUT_'):
#             if len(fm_ledger_account_bookings) == 0:
#                 # these are no links for this financial mutation, so we need to start linking!
#
#                 # this is a payout. Link it to the kruisposten ledger.
#                 if flagNoop:
#                     logging.info("NOOP: should create link for financial mutation {0}, but in read-only mode.".format(
#                             fmreference))
#                 else:
#                     mb.LinkPayout(fm['id'], amount)
#                     logging.info("Created link for financial mutation {0}.".format(fmreference))
#
#
# logging.info("All done!")
