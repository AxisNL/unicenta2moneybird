import configparser
import datetime
import decimal
import math
import os
import urllib
import numpy
import requests
import json
import logging

# default verbosity, will be overwritten by main class
flagVerbose = False
flagNoop = False

config = configparser.ConfigParser()
config.read('etc/izettle2moneybird.conf')

tokenMoneyBird = config['Moneybird']['Token']
administratie_id = config['Moneybird']['administratie_id']

store_contacts = os.path.join("var", 'moneybird_contacts.json')
store_financial_accounts = os.path.join("var", 'moneybird_financial_accounts.json')
store_ledger_accounts = os.path.join("var", 'moneybird_ledger_accounts.json')
store_financial_mutations_sync = os.path.join("var", 'moneybird_financial_mutations_sync.json')
store_financial_mutations = os.path.join("var", 'moneybird_financial_mutations.json')
store_sales_invoices = os.path.join("var", 'moneybird_sales_invoices.json')
store_purchase_invoices = os.path.join("var", 'moneybird_purchase_invoices.json')
store_tax_rates = os.path.join("var", 'moneybird_tax_rates.json')


def LookupContactId(company_name):
    with open(store_contacts) as json_file:
        data = json.load(json_file)
    for contact in data:
        if contact['company_name'] == company_name:
            return contact['id']
    logging.error("Could not lookup contact with name '{0}' (watch out, case sensitive!)".format(company_name))
    exit(1)


def LookupLedgerAccountId(name):
    with open(store_ledger_accounts) as json_file:
        data = json.load(json_file)
    for ledger_account in data:
        if ledger_account['name'] == name:
            return ledger_account['id']
    logging.error("Could not lookup ledger account with name '{0}' (watch out, case sensitive!)".format(name))
    exit(1)


def LookupFinancialAccountId(name):
    with open(store_financial_accounts) as json_file:
        data = json.load(json_file)
    for financial_account in data:
        if financial_account['name'] == name:
            return financial_account['id']
    logging.error("Could not lookup financial account with name '{0}' (watch out, case sensitive!)".format(name))
    exit(1)


def numericEqual(x, y, epsilon=1 * 10 ** (-8)):
    """Return True if two values are close in numeric value
        By default close is withing 1*10^-8 of each other
        i.e. 0.00000001
    """
    return abs(x - y) <= epsilon


def LookupTaxrateId(tax_rate_type, percentage):
    try:
        percentage = float(percentage)
    except:
        logging.error("Can not convert value '{0}' to float".format(percentage))

    with open(store_tax_rates) as json_file:
        data = json.load(json_file)
    for tax_rate in data:

        if tax_rate["tax_rate_type"] == tax_rate_type:
            if percentage == 0.0:
                if tax_rate['name'] == "Geen btw":
                    return tax_rate['id']
            if tax_rate['percentage'] is not None:
                try:
                    if numericEqual(float(tax_rate['percentage']), percentage):
                        return tax_rate['id']
                except:
                    logging.exception("There was a problem comparing tax rate percentage '{0}' with value {1} from json.".format(percentage, tax_rate['percentage']))

    logging.error("Could not lookup tax rate with percentage '{0}' (watch out, case sensitive!)".format(percentage))
    exit(1)


def LookupTaxrateIdPurchase(percentage):
    return LookupTaxrateId("purchase_invoice", percentage)
    #
    #     with open(store_tax_rates) as json_file:
    #     data = json.load(json_file)
    # for tax_rate in data:
    #     if tax_rate["tax_rate_type"] == "purchase_invoice":
    #         if percentage == 0:
    #             if tax_rate['name'] == "Geen btw":
    #                 return tax_rate['id']
    #         else:
    #             try:
    #                 if numericEqual(tax_rate['percentage'], percentage):
    #                     return tax_rate['id']
    #             except:
    #                 logging.error("There was a problem comparing tax rate percentage '{0}' with another numeric value".format(percentage))
    #
    # logging.error("Could not lookup tax rate with percentage '{0}' (watch out, case sensitive!)".format(percentage))
    # exit(1)


def LookupTaxrateIdSales(percentage):
    return LookupTaxrateId("sales_invoice", percentage)
    #
    # with open(store_tax_rates) as json_file:
    #     data = json.load(json_file)
    # for tax_rate in data:
    #     if tax_rate["tax_rate_type"] == "sales_invoice":
    #         if numericEqual(percentage, 0):
    #             if tax_rate['name'] == "Geen btw":
    #                 return tax_rate['id']
    #         else:
    #             mbTaxRatePercentage = float(tax_rate['percentage'])
    #             if numericEqual(mbTaxRatePercentage, percentage):
    #                 return tax_rate['id']
    # logging.error("Could not lookup tax rate with percentage '{0}' (watch out, case sensitive!)".format(percentage))
    # exit(1)


def DownloadContacts():
    contacts = []
    per_page = 100
    count = 1
    continueloop = True
    while continueloop:
        url = "https://moneybird.com/api/v2/{0}/contacts.json?page={1}&per_page={2}".format(administratie_id, count,
                                                                                            per_page)
        o = MakeGetRequest(url)
        for contact in o:
            contacts.append(contact)
        if len(o) < per_page:
            continueloop = False
        count = count + 1

    with open(store_contacts, 'w') as outfile:
        json.dump(contacts, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded Moneybird contacts ({0} items)'.format(len(contacts)))


def DownloadFinancialAccounts():
    url = "https://moneybird.com/api/v2/{0}/financial_accounts.json".format(administratie_id)
    o = MakeGetRequest(url)

    with open(store_financial_accounts, 'w') as outfile:
        json.dump(o, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded Moneybird financial accounts ({0} items)'.format(len(o)))


def DownloadLedgerAccounts():
    url = "https://moneybird.com/api/v2/{0}/ledger_accounts.json".format(administratie_id)
    o = MakeGetRequest(url)

    with open(store_ledger_accounts, 'w') as outfile:
        json.dump(o, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded Moneybird ledger accounts ({0} items)'.format(len(o)))


def DownloadTaxRates():
    url = "https://moneybird.com/api/v2/{0}/tax_rates.json".format(administratie_id)
    o = MakeGetRequest(url)

    with open(store_tax_rates, 'w') as outfile:
        json.dump(o, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded Moneybird tax rates ({0} items)'.format(len(o)))


def DownloadFinanancialMutations(startdate, enddate):
    startdatestring = startdate.strftime("%Y%m%d")
    enddatestring = enddate.strftime("%Y%m%d")

    # First, get a list of all id's
    url = "https://moneybird.com/api/v2/{0}/financial_mutations/synchronization.json?filter=period%3A{1}..{2}".format(
        administratie_id, startdatestring, enddatestring)
    o = MakeGetRequest(url)

    with open(store_financial_mutations_sync, 'w') as outfile:
        json.dump(o, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded Moneybird financial mutations sync ({0} items)'.format(len(o)))

    # store result
    financial_mutations = []

    if len(o) > 0:
        # we can only download up to a 100 mutations at once. See how many requests we need
        number_of_splits = math.ceil(len(o) / 100)
        # split up into chunks
        chunks = numpy.array_split(o, number_of_splits)

        for chunk in chunks:
            idlistforthischunk = []
            for item in chunk:
                idlistforthischunk.append(item['id'])
            postObj = {"ids": idlistforthischunk}
            url = "https://moneybird.com/api/v2/{0}/financial_mutations/synchronization.json".format(administratie_id)
            o = MakePostRequest(url, postObj)
            for financial_mutation in o:
                financial_mutations.append(financial_mutation)

    with open(store_financial_mutations, 'w') as outfile:
        json.dump(financial_mutations, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded Moneybird financial mutations ({0} items)'.format(len(financial_mutations)))


def DownloadSalesInvoices(startdate, enddate):
    startdatestring = startdate.strftime("%Y%m%d")
    enddatestring = enddate.strftime("%Y%m%d")
    salesinvoices = []
    per_page = 100
    count = 1
    continueloop = True
    while continueloop:
        url = "https://moneybird.com/api/v2/{0}/sales_invoices.json?filter=period%3A{1}..{2}&page={3}&per_page={4}".format(
            administratie_id, startdatestring, enddatestring, count, per_page)
        o = MakeGetRequest(url)
        for salesinvoice in o:
            salesinvoices.append(salesinvoice)
        if len(o) < per_page:
            continueloop = False
        count = count + 1

    with open(store_sales_invoices, 'w') as outfile:
        json.dump(salesinvoices, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded Moneybird sales invoices ({0} items)'.format(len(salesinvoices)))


def GetSalesInvoices():
    with open(store_sales_invoices) as json_file:
        data = json.load(json_file)
    return data


def GetPurchaseInvoices():
    with open(store_purchase_invoices) as json_file:
        data = json.load(json_file)
    return data


def GetFinancialMutations():
    with open(store_financial_mutations) as json_file:
        data = json.load(json_file)
    return data


def DownloadPurchaseInvoices(startdate, enddate):
    startdatestring = startdate.strftime("%Y%m%d")
    enddatestring = enddate.strftime("%Y%m%d")
    purchaseinvoices = []
    per_page = 100
    count = 1
    continueloop = True
    while continueloop:
        url = "https://moneybird.com/api/v2/{0}/documents/purchase_invoices.json?filter=period%3A{1}..{2}&page={3}&per_page={4}".format(
            administratie_id, startdatestring, enddatestring, count, per_page)
        o = MakeGetRequest(url)
        for purchaseinvoice in o:
            purchaseinvoices.append(purchaseinvoice)
        if len(o) < per_page:
            continueloop = False
        count = count + 1

    with open(store_purchase_invoices, 'w') as outfile:
        json.dump(purchaseinvoices, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded Moneybird purchase invoices ({0} items)'.format(len(purchaseinvoices)))


def AddFinancialStatementAndMutation(reference, transactioncode, timestamp, amount_dec):
    financial_account_id_izettle = LookupFinancialAccountId(config['Moneybird']['financial_account_izettle'])
    if transactioncode == 'PAYOUT':
        amount_dec = 0 - amount_dec
    if transactioncode == 'CARD_PAYMENT_FEE':
        amount_dec = 0 - amount_dec

    statement = {
        "financial_statement":
            {
                "reference": reference,
                "financial_account_id": financial_account_id_izettle,
                "financial_mutations_attributes":
                    {
                        "1": {
                            "date": timestamp.strftime('%Y-%m-%d'),
                            "message": reference,
                            "amount": "{0:f}".format(amount_dec)}
                    }
            }
    }

    url = "https://moneybird.com/api/v2/{0}/financial_statements.json".format(administratie_id)

    if flagNoop:
        logging.info("NOOP: Should create financial mutation '{0}', but in read-only mode.".format(reference))
    else:
        statementpost = MakePostRequest(url, statement)
        financial_mutation_id = statementpost['financial_mutations'][0]['id']
        logging.info("Created financial statement '{0}'".format(reference))
        return financial_mutation_id


def LinkPayout(mutation_id, amount_dec):
    grootboekrekening_id_kruisposten = LookupLedgerAccountId(config['Moneybird']['ledger_kruisposten'])

    link = {
        "booking_type": "LedgerAccount",
        "booking_id": grootboekrekening_id_kruisposten,
        "price_base": "{0:f}".format(amount_dec)
    }
    url = "https://moneybird.com/api/v2/{0}/financial_mutations/{1}/link_booking.json".format(administratie_id,
                                                                                              mutation_id)
    MakePatchRequest(url, link)
    print("Linked payout to bank account")


def LinkSalesInvoice(mutation_id, salesinvoice_id, amount_dec):
    link = {
        "booking_type": "SalesInvoice",
        "booking_id": salesinvoice_id,
        "price_base": "{0:f}".format(amount_dec)
    }
    url = "https://moneybird.com/api/v2/{0}/financial_mutations/{1}/link_booking.json".format(administratie_id,
                                                                                              mutation_id)
    MakePatchRequest(url, link)


def MakeNegative(number):
    if number > 0:
        number = 0 - number
    return number


def MakePositive(number):
    if number < 0:
        number = 0 - number
    return number


def LinkPurchaseInvoice(mutation_id, purchaseinvoice_id, amount_dec):

    link = {
        "booking_type": "Document",
        "booking_id": purchaseinvoice_id,
        "price_base": "{0:f}".format(amount_dec)
    }
    url = "https://moneybird.com/api/v2/{0}/financial_mutations/{1}/link_booking.json".format(administratie_id,
                                                                                              mutation_id)
    MakePatchRequest(url, link)


def AddSalesInvoice(reference, invoice_date, products):
    details_attributes = []
    for product in products:
        description = product['description']
        if len(description) == 0:
            description = "Diversen"
        price = product['price']
        taxrateid = LookupTaxrateIdSales(product['tax_rate'])
        ladgeraccountid = LookupLedgerAccountId('Omzet')
        details_attribute = {
            "description": description,
            "price": "{0:f}".format(price),
            "tax_rate_id": taxrateid,
            "ledger_account_id": ladgeraccountid
        }
        details_attributes.append(details_attribute)

    postObject = {"sales_invoice":
                      {"reference": reference,
                       "invoice_date": invoice_date.isoformat(),
                       "contact_id": LookupContactId(config['Moneybird']['contact_passant']),
                       "details_attributes": details_attributes,
                       "prices_are_incl_tax": True
                       }
                  }
    url = "https://moneybird.com/api/v2/{0}/sales_invoices".format(administratie_id)
    invoicepost = MakePostRequest(url, postObject)
    invoiceid = invoicepost['id']
    return invoiceid


def SendInvoice(invoiceid):
    url = "https://moneybird.com/api/v2/{0}/sales_invoices/{1}/send_invoice.json".format(administratie_id, invoiceid)
    postObject = {"sales_invoice_sending":
                      {"delivery_method": "Manual"
                       }
                  }
    MakePatchRequest(url, postObject)


def AddPurchaseInvoice(reference, invoice_date, prijs_incl_decimal):
    contactid_izettle = LookupContactId(config['Moneybird']['contact_izettle'])
    ledgerid_bankkosten = LookupLedgerAccountId(config['Moneybird']['ledger_bankkosten'])
    taxrateid = LookupTaxrateIdPurchase(0)
    postObject = {"purchase_invoice":
                      {"reference": reference,
                       "date": invoice_date.isoformat(),
                       "contact_id": contactid_izettle,
                       "details_attributes": [
                           {
                               "description": "Administratiekosten bij pintransactie",
                               "price": "{0:f}".format(prijs_incl_decimal),
                               "ledger_account_id": ledgerid_bankkosten,
                               "tax_rate_id": taxrateid
                           }
                       ],
                       "prices_are_incl_tax": True
                       }
                  }

    if flagNoop:
        logging.info("NOOP: Purchase invoice '{0}' should be created, but in read-only mode".format(reference))
    else:
        url = "https://moneybird.com/api/v2/{0}/documents/purchase_invoices.json".format(administratie_id)
        MakePostRequest(url, postObject)
        logging.info("Purchase invoice '{0}' created".format(reference))


def MakeGetRequest(url):
    # print("DEBUG: get {0}".format(url))
    global tokenMoneyBird

    headers = {
        "authorization": "Bearer {0}".format(tokenMoneyBird)
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        logging.error("Error: {0} {1}".format(r.status_code, r.content))
        exit(1)


def MakePostRequest(url, postObj):
    # print("DEBUG: post {0}".format(url))
    global tokenMoneyBird

    headers = {
        "authorization": "Bearer {0}".format(tokenMoneyBird)
    }
    r = requests.post(url, json=postObj, headers=headers)
    if r.status_code == 200:
        return r.json()
    if r.status_code == 201:
        return r.json()
    if r.status_code > 299:
        logging.error("Error: {0}".format(r.content))
        exit(1)


def MakePatchRequest(url, postObj):
    global tokenMoneyBird

    headers = {
        "authorization": "Bearer {0}".format(tokenMoneyBird)
    }
    r = requests.patch(url, json=postObj, headers=headers)
    result = r.json()
    return result
