from secrets import Secrets
from importers.brim import BrimImporter
from importers.wealthica import WealthicaImporter
import ynab
from pprint import pprint
import schedule
import time

s = Secrets("./secrets.ejson")

configuration = ynab.Configuration()
configuration.api_key['Authorization'] = s.getSecret("ynab_token")
configuration.api_key_prefix['Authorization'] = 'Bearer'

brim = BrimImporter(s)
brim.run()

wealthica = WealthicaImporter(s)
wealthica.run()

schedule.every().day.at("01:30").do(brim.run)
schedule.every().day.at("01:30").do(wealthica.run)

while True:
    schedule.run_pending()
    time.sleep(1)
