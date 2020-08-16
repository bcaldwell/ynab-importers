import base64
import os
import datetime
import ynab
from ynab.rest import ApiException
import time
import requests
import logging
from http.cookiejar import CookieJar
from lxml import html
import pyotp
import base64
import urllib.parse


class WealthfrontImporter:
    login_url = "https://www.wealthfront.com/login"
    login_post_url = "https://www.wealthfront.com/api/access/login"
    mfa_post_url = "https://www.wealthfront.com/api/access/mfa"
    all_accounts_url = "https://www.wealthfront.com/api/wealthfront_accounts/all-accounts"
    external_accounts_url = "https://www.wealthfront.com/api/external_accounts"

    def __init__(self, Secrets):
        self.wealthfront_username = Secrets.getSecret(
            'wealthfront.username').strip()
        self.wealthfront_password = Secrets.getSecret(
            'wealthfront.password').strip()
        self.wealthfront_opt_secret = Secrets.getSecret(
            'wealthfront.opt_secret').strip()

        self.ynab_budget_id = Secrets.getSecret(
            "wealthfront.ynab_budget_id").strip()

        self.account_mapping = Secrets.getSecret("wealthfront.account_mapping")

        self.totp = pyotp.TOTP(self.wealthfront_opt_secret.replace(" ", ""))

        self.logger = logging.getLogger('wealthfront')

        self.jar = CookieJar()
        self.session = requests.Session()

    def login(self):
        # get login screen to set token
        self.session.get(self.login_url)

        login_xsrf = urllib.parse.unquote(
            self.session.cookies.get_dict()["login_xsrf"])

        login_post = self.session.post(self.login_post_url, json={
            "username": self.wealthfront_username,
            "grantType": "password",
            "loginXsrf": login_xsrf,
            "password": self.wealthfront_password,
            "sessionType": "WEB",
        })

        self.logger.info(login_post.json())

        # todo: check if mfa is needed
        mfa_code = self.totp.now()
        # mfa_code = input()

        mfa_xsrf = urllib.parse.unquote(
            self.session.cookies.get_dict()["xsrf"])

        # mfa_page = self.session.get(self.mfa_url)
        mfa_post = self.session.post(self.mfa_post_url, json={
            "challengeResponse": mfa_code,
            "rememberDevice": "false",
            "xsrf": mfa_xsrf
        })

        # print(mfa_post.status_code)
        # self.logger.info(mfa_post.json())
        # print(login_tree.xpath('//div[@data-login-xsrf=*]'))

    def get_account_mapping_for_ynab_id(self, id):
        for i in self.account_mapping:
            if i["ynab_account"] == id:
                return i
        return None

    def create_transaction(self, dateString, currentValue,  a):
        delta = round(currentValue - a.cleared_balance / 1000, 2)
        self.logger.info("[{}] current: {} last: {} delta: {}".format(a.name,
                                                                      currentValue, a.balance / 1000, delta))

        if delta != 0:
            return {
                "account_id": a.id,
                "date": dateString,
                "amount": int(delta * 1000),
                "payee_name": "Investment Return",
                "cleared": "cleared",
                "approved": True,
                "import_id": "wealthfront-{}".format(dateString)
            }
        return None

    def update_ynab(self):
        try:
            # Account list
            ynabAccounts = ynab.AccountsApi().get_accounts(self.ynab_budget_id)
        except ApiException as e:
            self.logger.error(
                "Exception when calling AccountsApi->get_accounts: %s\n" % e)
            return

        try:
            all_accounts = self.session.get(self.all_accounts_url)
            all_accounts = all_accounts.json()
        except:
            self.logger.error(
                "Exception when calling " + self.all_accounts_url + "\n")
            return

        try:
            external_accounts = self.session.get(self.external_accounts_url)
            external_accounts = external_accounts.json()
        except:
            self.logger.error(
                "Exception when calling " + self.all_accounts_url + "\n")
            return

        transactions = []
        dateString = datetime.datetime.now().strftime("%Y-%m-%d")
        for a in ynabAccounts.data.accounts:
            account_mapping = self.get_account_mapping_for_ynab_id(a.id)
            if account_mapping:
                found = False
                for i in all_accounts:
                    if str(i['accountId']) == account_mapping['account_id']:
                        found = True

                        currentValue = i['accountValueSummary']["totalValue"]
                        transaction = self.create_transaction(
                            dateString, currentValue, a)
                        if transaction:
                            transactions.append(transaction)

                for linkStatus in external_accounts["linkStatuses"]:
                    for i in linkStatus["accounts"]:
                        if i['externalAccountId'] == account_mapping['account_id']:
                            found = True

                            currentValue = i['marketValue']
                            transaction = self.create_transaction(
                                dateString, currentValue, a)
                            if transaction:
                                transactions.append(transaction)

                if not found:
                    self.logger.warn(
                        "Failed to find wealthfront account for id %s\n" % account_mapping['account_id'])

        if len(transactions):
            try:
                ynab.TransactionsApi().bulk_create_transactions(
                    self.ynab_budget_id, {"transactions": transactions})
                self.logger.info("wealthica done")
            except ApiException as e:
                self.logger.error(
                    "Exception when creating transactions: %s\n" % e)

    def run(self):
        self.login()
        self.update_ynab()
