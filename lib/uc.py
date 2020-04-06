import configparser
import logging
import json
import datetime
import mysql.connector
import xml.etree.ElementTree

# from lib import log

# default verbosity, will be overwritten by main class
flagVerbose = False

config = configparser.ConfigParser()
config.read('etc/unicenta2moneybird.conf')
Unicenta_MySQL_host = config['Unicenta']['Unicenta_MySQL_host']
Unicenta_MySQL_user = config['Unicenta']['Unicenta_MySQL_user']
Unicenta_MySQL_pass = config['Unicenta']['Unicenta_MySQL_pass']
Unicenta_MySQL_db = config['Unicenta']['Unicenta_MySQL_db']

ticketsfile = "var/unicenta_tickets.json"
ticketlinesfile = "var/unicenta_ticketlines.json"
receiptsfile = "var/unicenta_receipts.json"
paymentsfile = "var/unicenta_payments.json"
taxesfile = "var/unicenta_taxes.json"

customsalesfile = "var/custom_sales.json"

_DBConnection = None


def GetDBConnection():
    global _DBConnection
    if _DBConnection is None:
        _DBConnection = mysql.connector.connect(
            host=Unicenta_MySQL_host,
            user=Unicenta_MySQL_user,
            passwd=Unicenta_MySQL_pass,
            database=Unicenta_MySQL_db
        )
    return _DBConnection


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def DownloadTickets():
    mysql_query = 'SELECT * FROM tickets'
    mycursor = GetDBConnection().cursor(dictionary=True)
    mycursor.execute(mysql_query)
    result = mycursor.fetchall()
    with open(ticketsfile, 'w') as outfile:
        json.dump(result, outfile, indent=4, sort_keys=True, default=json_serial)
    logging.info('Downloaded uniCenta tickets ({0} items)'.format(len(result)))


def GetTickets():
    with open(ticketsfile) as json_file:
        data = json.load(json_file)
    return data


def DownloadTicketLines():
    mysql_query = 'SELECT * FROM ticketlines'
    mycursor = GetDBConnection().cursor(dictionary=True)
    mycursor.execute(mysql_query)
    result = mycursor.fetchall()
    with open(ticketlinesfile, 'w') as outfile:
        json.dump(result, outfile, indent=4, sort_keys=True, default=json_serial)
    logging.info('Downloaded uniCenta ticketlines ({0} items)'.format(len(result)))


def GetTicketLines():
    with open(ticketlinesfile) as json_file:
        data = json.load(json_file)
    return data


def DownloadReceipts():
    mysql_query = 'SELECT * FROM receipts ORDER BY datenew'
    mycursor = GetDBConnection().cursor(dictionary=True)
    mycursor.execute(mysql_query)
    result = mycursor.fetchall()
    with open(receiptsfile, 'w') as outfile:
        json.dump(result, outfile, indent=4, sort_keys=True, default=json_serial)
    logging.info('Downloaded uniCenta receipts ({0} items)'.format(len(result)))


def GetReceipts():
    with open(receiptsfile) as json_file:
        data = json.load(json_file)
    return data


def DownloadPayments():
    mysql_query = 'SELECT * FROM payments'
    mycursor = GetDBConnection().cursor(dictionary=True)
    mycursor.execute(mysql_query)
    result = mycursor.fetchall()
    with open(paymentsfile, 'w') as outfile:
        json.dump(result, outfile, indent=4, sort_keys=True, default=json_serial)
    logging.info('Downloaded uniCenta payments ({0} items)'.format(len(result)))


def GetPayments():
    with open(paymentsfile) as json_file:
        data = json.load(json_file)
    return data


def DownloadTaxes():
    mysql_query = 'SELECT * FROM taxes'
    mycursor = GetDBConnection().cursor(dictionary=True)
    mycursor.execute(mysql_query)
    result = mycursor.fetchall()
    with open(taxesfile, 'w') as outfile:
        json.dump(result, outfile, indent=4, sort_keys=True, default=json_serial)
    logging.info('Downloaded uniCenta taxes ({0} items)'.format(len(result)))


def GetTaxes():
    with open(taxesfile) as json_file:
        data = json.load(json_file)
    return data


def LookupTaxrate(categoryid):
    for tax in GetTaxes():
        if tax['category'] == categoryid:
            return tax['rate']
    logging.error("Cannot find tax category {0}".format(categoryid))
    exit(1)


def validateCustomSale(sale):
    # validate the sale to see if it is valid (fully paid, etc)

    # Payment method filter
    filter_exists = config.has_option('Unicenta', 'Payment_method_filter')
    if filter_exists:
        payment_method_filter = str(config['Unicenta']['Payment_method_filter'])
        payment_method_filter_items = []
        for item in payment_method_filter.split(','):
            payment_method_filter_items.append(item.strip())

        for payment in sale['payments']:
            if payment['method'] not in payment_method_filter_items:
                logging.warning("Sale '{0}' has a payment method '{1}'. This is not allowed according to your "
                                "configured filter '{2}'. Ignoring sale.".format(sale['reference'], payment['method'],
                                                                                 payment_method_filter_items))
                return False

    # get the total of all the products
    total_amount_products = 0
    for product in sale['products']:
        total_amount_products += product['priceexcl'] * (1 + product['taxrate']) * product['quantity']
    # print("total_amount_products: {0}".format(total_amount_products))

    # get the total of all the payments
    total_amount_payments = 0
    for payment in sale['payments']:
        total_amount_payments += payment['amount']
    # print("total_amount_payments: {0}".format(total_amount_payments))

    match = numericEqual(total_amount_products, total_amount_payments)

    if not match:
        logging.warning("Sale '{0}' can not be validated: the amount of products is {1}, but the payment is {2}. "
                        "Ignoring sale.".format(sale['reference'], total_amount_products, total_amount_payments))
        return False
    # print("match: {0}".format())
    return True


def numericEqual(x, y, epsilon=1 * 10 ** (-8)):
    """Return True if two values are close in numeric value
        By default close is withing 1*10^-8 of each other
        i.e. 0.00000001
    """
    return abs(x - y) <= epsilon


def TransformSales(startDate, endDate):
    sales = []
    for receipt in GetReceipts():
        # this is a custom object to massage uc objects into mb format
        sale = {}
        sale['date'] = datetime.datetime.strptime(receipt['datenew'], "%Y-%m-%dT%H:%M:%S")
        if startDate < sale['date'] < endDate:
            for ticket in GetTickets():
                if ticket['id'] == receipt['id']:
                    sale['reference'] = "POS verkoop {0}".format(ticket['ticketid'])
                    products = []
                    for ticketline in GetTicketLines():
                        if ticketline['ticket'] == ticket['id']:
                            productline = {}
                            productline['number'] = ticketline['line']
                            productline['priceexcl'] = ticketline['price']
                            productline['quantity'] = ticketline['units']

                            xmlattribute = ticketline['attributes']
                            tree = xml.etree.ElementTree.fromstring(xmlattribute)
                            for elem in tree:
                                if elem.tag == "entry":
                                    #print("{0}: {1}".format(elem.attrib['key'], elem.text))
                                    if elem.attrib['key'] == "product.taxcategoryid":
                                        ticketLineTaxCategoryId = elem.text
                                        productline['taxrate'] = LookupTaxrate(ticketLineTaxCategoryId)
                                    if elem.attrib['key'] == "product.name":
                                        productline['description'] = elem.text
                            products.append(productline)
                    sale['products'] = products

                    payments = []
                    for ucpayment in GetPayments():
                        payment = {}
                        if ucpayment['receipt'] == receipt['id']:
                            #print(ucpayment)
                            payment['method'] = ucpayment['payment']
                            payment['amount'] = ucpayment['total']
                            payment['transactionid'] = ucpayment['transid']
                            payments.append(payment)
                    sale['payments'] = payments

            if validateCustomSale(sale):
                sales.append(sale)
        else:
            logging.info("Skipping sale as the date {0} is not in the selection.".format(sale['date']))

    with open(customsalesfile, 'w') as outfile:
        json.dump(sales, outfile, indent=4, sort_keys=True, default=json_serial)
    logging.info('Transformed uniCenta sales ({0} items)'.format(len(sales)))


def GetTransformedSales():
    with open(customsalesfile) as json_file:
        data = json.load(json_file)
    return data
