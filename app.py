from secrets import Secrets
import importers
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
importers_to_run = list(map(lambda x: x.strip().lower(), args.importers))

logger = logging.getLogger("YNAB Importer")

s = Secrets(os.environ.get(
            "YNAB_IMPORTER_SECRETS_FILE", "./secrets.ejson"))
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if len(importers_to_run) == 0 or "brim" in importers_to_run:
    if s.getSecret('brim.enable') != False:
        logger.info("Starting brim")
        brim = importers.BrimImporter(s)
        brim.run()
        schedule.every().day.at("23:30").do(brim.run)

if len(importers_to_run) == 0 or "splitwise" in importers_to_run:
    if s.getSecret('splitwise.enable') != False:
        logger.info("Starting splitwise")
        splitwise = importers.SplitwiseImporter(s)
        splitwise.run()
        schedule.every().hour.do(splitwise.run)

if len(importers_to_run) == 0 or "plaid" in importers_to_run:
    if s.getSecret('plaid.enable') != False:
        logger.info("Starting plaid")
        plaid = importers.PlaidImporter(s)
        plaid.run()
        schedule.every().day.at("23:30").do(plaid.run)


if args.once:
    sys.exit(0)


logger.info("Starting cron")
while True:
    schedule.run_pending()
    time.sleep(1)
