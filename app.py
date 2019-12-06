from secrets import Secrets
from importers.brim import BrimImporter
from importers.wealthica import WealthicaImporter
from importers.wealthfront import WealthfrontImporter
from importers.splitwise import SplitwiseImporter
import ynab
from pprint import pprint
import schedule
import time
import os
import logging
import argparse
import sys

parser = argparse.ArgumentParser(description='Run YNAB Importers')
parser.add_argument('importers', nargs='*',
                    help='list of importers to run (default none runs all). Options: brim, wealthica')
parser.add_argument('--once', default=False, action='store_true',
                    help="Disable cron and only run the importer once.")

args = parser.parse_args()
importers = list(map(lambda x: x.strip().lower(), args.importers))

logger = logging.getLogger("YNAB Importer")

s = Secrets(os.environ.get(
            "YNAB_IMPORTER_SECRETS_FILE", "./secrets.ejson"))
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

configuration = ynab.Configuration()
configuration.api_key['Authorization'] = s.getSecret("ynab_token")
configuration.api_key_prefix['Authorization'] = 'Bearer'

if len(importers) == 0 or "brim" in importers:
    if s.getSecret('splitwise.enable') != False:
        logger.info("Starting brim")
        brim = BrimImporter(s)
        brim.run()
        schedule.every().day.at("01:30").do(brim.run)

if len(importers) == 0 or "wealthica" in importers:
    if s.getSecret('wealthica.enable') != False:
        logger.info("Starting wealthica")
        wealthica = WealthicaImporter(s)
        wealthica.run()
        schedule.every().day.at("01:30").do(wealthica.run)


if len(importers) == 0 or "splitwise" in importers:
    if s.getSecret('splitwise.enable') != False:
        logger.info("Starting splitwise")
        splitwise = SplitwiseImporter(s)
        splitwise.run()
        schedule.every().day.at("01:30").do(splitwise.run)

if len(importers) == 0 or "wealthfront" in importers:
    if s.getSecret('wealthfront.enable') != False:
        logger.info("Starting wealthfront")
        wealthfront = WealthfrontImporter(s)
        wealthfront.run()
        schedule.every().day.at("01:30").do(wealthfront.run)


if args.once:
    sys.exit(0)


logger.info("Starting cron")
while True:
    schedule.run_pending()
    time.sleep(1)
