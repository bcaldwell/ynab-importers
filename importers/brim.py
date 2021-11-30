import requests
import pandas as pd
from io import StringIO
import logging
from ynab_sdk import YNAB
from ynab_sdk.api.models.requests.transaction import TransactionRequest


class BrimImporter:
    def __init__(self, secrets):
        self.brim_username = secrets.getSecret('brim.username').strip()
        self.brim_password = secrets.getSecret('brim.password').strip()
        self.brim_card_id = secrets.getSecret('brim.card_id').strip()
        self.brim_ynab_account_id = secrets.getSecret(
            'brim.ynab_account_id').strip()
        self.brim_ynab_budget_id = secrets.getSecret(
            'brim.ynab_budget_id').strip()

        self.ynab_token = secrets.getSecret(
            "ynab_token").strip()
        self.ynabClient = YNAB(self.ynab_token)

        self.logger = logging.getLogger('brim')

    def generate_ynab_import_id(self, transaction):
        #     YNAB:2015-12-30:Payee:-294230:2
        return "YNAB:{}:{}:{}:{}".format(transaction["Transaction Date"], transaction["Description"], transaction["ynabAmount"], transaction["import_id_occurrence"])

    def generate_yanb_transaction(self, transaction):
        return TransactionRequest(
            self.brim_ynab_account_id,
            transaction["Transaction Date"],
            int(transaction["ynabAmount"]),
            payee_name=transaction["Description"],
            cleared="cleared",
            approved=False,
            import_id=transaction["import_id"]
        )

    def run(self):
        brim = requests.Session()

        login_url = "https://brimfinancial.com/webportal/Login/validate_login"
        login_data = {
            'language': 'english',
            'username': self.brim_username,
            'password': self.brim_password
        }

        brim.get("https://brimfinancial.com/webportal/login")
        r = brim.post(login_url, data=login_data, allow_redirects=False)

        if r.status_code != 303 or r.headers["Location"] != "https://brimfinancial.com/webportal/Home":
            self.logger.error("Login failed")
            return

        brim.get("https://brimfinancial.com/webportal/Activity")
        get_csv_url = "https://brimfinancial.com/webportal/Activity/downloadExcel"
        get_csv_data = {
            "page": 1,
            "cardid": self.brim_card_id,
            "date_filter": 60,
            "showpending": "yes",
            "type": "csv"
        }
        req = brim.post(get_csv_url, data=get_csv_data)
        if req.text == "" or req.status_code != 200:
            print("failed to get transactions")
            return

        download_csv = req.text

        download_url = "https://brimfinancial.com/webportal/" + download_csv
        r = brim.get(download_url)
        if r.status_code != 200:
            self.logger.error("Failed to fetch csv file")
            return

        decoded_content = r.content.decode('utf-8')

        transactions = pd.read_csv(
            StringIO(decoded_content), sep=",", header=0)
        transaction_count = len(decoded_content.splitlines()) - 1

        unlink_csv_url = "https://brimfinancial.com/webportal/Activity/unlinkdownloadExcel"
        req = brim.post(unlink_csv_url, data={"filename": download_csv})

        # transform dataframe
        transactions['Amount'] = transactions['Amount'].astype(float)
        transactions["ynabAmount"] = (
            transactions["Amount"] * -1000).astype(int)
        transactions['import_id_occurrence'] = transactions.groupby(
            ['ynabAmount', "Transaction Date", "Description"])["ynabAmount"].rank(method="first").astype(int)
        transactions["import_id"] = transactions.apply(
            self.generate_ynab_import_id, axis=1)

        ynab_transaction = []

        for i in range(transaction_count):
            ynab_transaction.append(
                self.generate_yanb_transaction(transactions.loc[i]))

        # print(ynab_transaction)

        if len(transactions):
            try:
                self.ynabClient.transactions.create_transactions(
                    self.brim_ynab_budget_id, ynab_transaction)
                self.logger.info("Brim Done")
            except Exception as e:
                self.logger.error(
                    "Exception when calling ynab->create_transactions: %s\n" % e)
