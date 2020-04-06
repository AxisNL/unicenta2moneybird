import configparser
import logging
import requests
import json
from datetime import datetime
import mysql.connector
#from lib import log

# default verbosity, will be overwritten by main class
flagVerbose = False

config = configparser.ConfigParser()
config.read('etc/unicenta2moneybird.conf')
Unicenta_MySQL_host = config['Unicenta']['Unicenta_MySQL_host']
Unicenta_MySQL_user = config['Unicenta']['Unicenta_MySQL_user']
Unicenta_MySQL_pass = config['Unicenta']['Unicenta_MySQL_pass']
Unicenta_MySQL_db = config['Unicenta']['Unicenta_MySQL_db']

ticketsfile = "var/unicenta_tickets.json"

mydb = mysql.connector.connect(
    host=Unicenta_MySQL_host,
    user=Unicenta_MySQL_user,
    passwd=Unicenta_MySQL_pass,
    database=Unicenta_MySQL_db
)

def DownloadTickets(datestart, dateend):

    ucDate1 = datestart.strftime("%Y-%m-%d")
    ucDate2 = dateend.strftime("%Y-%m-%d")

    mysql_query = ''

    mysql_query += 'SELECT '
    mysql_query += 'ticketid as tickets_ticketid, '
    mysql_query += 'r.datenew as receipts_datenew,  '
    mysql_query += 'p.name as product_name,  '
    mysql_query += 'payments.payment as payments_payment,  '
    mysql_query += 'tl.units as ticketlines_units,  '
    mysql_query += 'tl.price as ticketlines_price,  '
    mysql_query += 'taxes.rate as taxes_rate  '
    mysql_query += 'FROM ticketlines tl  '
    mysql_query += 'left outer join tickets t on tl.ticket=t.id '
    mysql_query += 'left outer join products p on p.id=tl.product '
    mysql_query += 'left outer join receipts r on r.id=t.id '
    mysql_query += 'left outer join payments on r.id = payments.receipt '
    mysql_query += 'left join taxes on taxes.id = tl.taxid '
    mysql_query += 'order by ticketid '

    mycursor = mydb.cursor()
    mycursor.execute(mysql_query)
    result = mycursor.fetchall()

    with open(ticketsfile, 'w') as outfile:
        json.dump(result, outfile, indent=4, sort_keys=True)
    logging.info('Downloaded uniCenta tickets ({0} items)'.format(len(result)))


def GetTickets():
    with open(ticketsfile) as json_file:
        data = json.load(json_file)
    return data


def numericEqual(x, y, epsilon=1 * 10 ** (-8)):
    """Return True if two values are close in numeric value
        By default close is withing 1*10^-8 of each other
        i.e. 0.00000001
    """
    return abs(x - y) <= epsilon

# this code will only be run if this script is run directly
if __name__ == '__main__':
    print(json.dumps(DownloadTickets(), indent=2, sort_keys=True))
