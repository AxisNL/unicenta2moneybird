import configparser
import logging
import requests
import json
from datetime import datetime
import mysql.connector

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

_DBConnection = None


def GetDBConnection():
    if _DBConnection is None:
        _DBConnection = mysql.connector.connect(
            host=Unicenta_MySQL_host,
            user=Unicenta_MySQL_user,
            passwd=Unicenta_MySQL_pass,
            database=Unicenta_MySQL_db
        )
    return _DBConnection


def DownloadTickets():
    mysql_query = 'SELECT * FROM tickets'
    mycursor = GetDBConnection().cursor()
    mycursor.execute(mysql_query)
    result = mycursor.fetchall()
    with open(ticketsfile, 'w') as outfile:
        json.dump(result, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded uniCenta tickets ({0} items)'.format(len(result)))


def DownloadTicketLines():
    mysql_query = 'SELECT * FROM ticketlines'
    mycursor = GetDBConnection().cursor()
    mycursor.execute(mysql_query)
    result = mycursor.fetchall()
    with open(ticketslinesfile, 'w') as outfile:
        json.dump(result, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded uniCenta ticketlines ({0} items)'.format(len(result)))


#
# def DownloadTicketsRaw(datestart, dateend):
#     ucDate1 = datestart.strftime("%Y-%m-%d")
#     ucDate2 = dateend.strftime("%Y-%m-%d")
#
#     mydb = mysql.connector.connect(
#         host=Unicenta_MySQL_host,
#         user=Unicenta_MySQL_user,
#         passwd=Unicenta_MySQL_pass,
#         database=Unicenta_MySQL_db
#     )
#
#     mysql_query = ''
#
#     mysql_query += 'SELECT '
#     mysql_query += 'ticketid as tickets_ticketid, '
#     mysql_query += 'r.datenew as receipts_datenew, '
#     mysql_query += 'p.name as product_name, '
#     mysql_query += 'payments.payment as payments_payment, '
#     mysql_query += 'payments.total as payments_total, '
#     mysql_query += 'payments.transid as payments_transid, '
#     mysql_query += 'tl.units as ticketlines_units, '
#     mysql_query += 'tl.price as ticketlines_price, '
#     mysql_query += 'taxes.rate as taxes_rate '
#     mysql_query += 'FROM ticketlines tl '
#     mysql_query += 'left outer join tickets t on tl.ticket=t.id '
#     mysql_query += 'left outer join products p on p.id=tl.product '
#     mysql_query += 'left outer join receipts r on r.id=t.id '
#     mysql_query += 'left outer join payments on r.id = payments.receipt '
#     mysql_query += 'left join taxes on taxes.id = tl.taxid '
#     mysql_query += 'order by ticketid '
#
#     mycursor = mydb.cursor()
#     mycursor.execute(mysql_query)
#     result = mycursor.fetchall()
#
#     with open(ticketsfile_raw, 'w') as outfile:
#         json.dump(result, outfile, indent=4, sort_keys=True)
#     logging.info('Downloaded uniCenta tickets ({0} items)'.format(len(result)))
#
#
# # The downloaded file is convoluted, make it into a nicer file
# def TransformTickets():
#     with open(ticketsfile_raw) as json_file:
#         data = json.load(json_file)
#     ticketstore = []
#
#     # first get a list of all ticketids
#     ticketids = []
#     for row in data:
#         if not row['tickets_ticketid'] in ticketids:
#             ticketids.append(row['tickets_ticketid'])
#     # print("found {0} ids in {1} rows".format(len(ticketids), len(data)))
#
#     for ticketid in ticketids:
#         currentTicket = {}
#         for row in data:
#             if ticketid == row['tickets_ticketid']:
#                 currentTicket["paymentmethod"] = row['payments_payment']
#                 currentTicket["paymenttotal"] = row['payments_total']
#                 currentTicket["timestamp"] = row['receipts_datenew']
#                 currentTicket["ticketid"] = row['tickets_ticketid']
#                 if 'products' not in currentTicket.keys():
#                     currentTicket['products'] = []
#                 if 'payments' not in currentTicket.keys():
#                     currentTicket['payments'] = []
#                 payment = {"method": row['payments_payment']}
#
#                 product = {"name": row['product_name'],
#                            "taxes_rate": row['taxes_rate'],
#                            "price_excl": row['ticketlines_price'],
#                            "price_incl": row['ticketlines_price'] * (1 + row['taxes_rate']),
#                            "quantity": row['ticketlines_units'],
#                            }
#                 currentTicket['products'].append(product)
#         if ValidateTicket(currentTicket):
#             ticketstore.append(currentTicket)
#         else:
#             logging.warning("Could not validate ticket {0}.".format(ticketid))
#
#     with open(ticketsfile, 'w') as outfile:
#         json.dump(ticketstore, outfile, indent=4, sort_keys=True)
#     logging.info('Transformed uniCenta tickets ({0} tickets)'.format(len(ticketstore)))
#
#
# def ValidateTicket(ticket):
#     # print("--> {0} {1}<--".format(ticket['paymenttotal'], type(ticket['paymenttotal'])))
#     paymenttotal = ticket['paymenttotal']
#     productstotal = 0.0
#     for product in ticket['products']:
#         productstotal = productstotal + (product['price_incl'] * product['quantity'])
#     print("Checking ticket: {0}".format(ticket['ticketid']))
#     print("Payment total: {0}".format(paymenttotal))
#     print("Products total: {0}".format(productstotal))
#
#     matchPayment = numericEqual(paymenttotal, productstotal)
#     print("Match: {0}".format(matchPayment))
#     if not matchPayment:
#         logging.warning(
#             "TicketId {0}: payment total is {1}, but products total is {2}. Ignoring ticket".format(ticket['ticketid'],
#                                                                                                     paymenttotal,
#                                                                                                     productstotal))
#         return False
#     else:
#         return True
#
# def GetTickets():
#     with open(ticketsfile_raw) as json_file:
#         data = json.load(json_file)
#     return data
#
#
# def numericEqual(x, y, epsilon=1 * 10 ** (-8)):
#     """Return True if two values are close in numeric value
#         By default close is withing 1*10^-8 of each other
#         i.e. 0.00000001
#     """
#     return abs(x - y) <= epsilon


# this code will only be run if this script is run directly
if __name__ == '__main__':
    print(json.dumps(DownloadTicketsRaw(), indent=2, sort_keys=True))
