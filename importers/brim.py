import requests
import pandas as pd
from io import StringIO
import ynab
from ynab.rest import ApiException


class BrimImporter:
    def __init__(self, Secrets):
        self.brim_username = Secrets.getSecret('brim.username').strip()
        self.brim_password = Secrets.getSecret('brim.password').strip()
        self.brim_card_id = Secrets.getSecret('brim.card_id').strip()
        self.brim_ynab_account_id = Secrets.getSecret(
            'brim.ynab_account_id').strip()
        self.brim_ynab_budget_id = Secrets.getSecret(
            'brim.ynab_budget_id').strip()

    def generate_ynab_import_id(self, transaction):
        #     YNAB:-294230:2015-12-30:2
        return "YNAB:{}:{}:{}".format(transaction["ynabAmount"], transaction["Transaction Date"], transaction["import_id_occurrence"])

    def generate_yanb_transaction(self, transaction):
        return {
            "account_id": self.brim_ynab_account_id,
            "date": transaction["Transaction Date"],
            "amount": int(transaction["ynabAmount"]),
            "payee_name": transaction["Description"],
            "cleared": "cleared",
            "approved": False,
            "import_id": transaction["import_id"]
        }

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
        # print(r.status_code, r.headers["Location"], r.headers["Location"]
        #       == "https://brimfinancial.com/webportal/Home")
        if r.headers["Location"] != "https://brimfinancial.com/webportal/Home":
            print("Login failed")
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
        # print(req.status_code, req.text != "")
        if req.text == "":
            print("failed to get transactions")
            return

        download_csv = req.text

        download_url = "https://brimfinancial.com/webportal/" + download_csv
        r = brim.get(download_url)
        # print(r.status_code)
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
            ['ynabAmount', "Transaction Date"])["ynabAmount"].rank(method="first").astype(int)
        transactions["import_id"] = transactions.apply(
            self.generate_ynab_import_id, axis=1)

        ynab_transaction = []

        for i in range(transaction_count):
            ynab_transaction.append(
                self.generate_yanb_transaction(transactions.loc[i]))

        # print(ynab_transaction)

        if len(transactions):
            try:
                ynab.TransactionsApi().bulk_create_transactions(
                    self.brim_ynab_budget_id, {"transactions": ynab_transaction})
                print("Brim Done")
            except ApiException as e:
                print(
                    "Exception when calling Secrets->bulk_create_transactions: %s\n" % e)
