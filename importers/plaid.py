from ynab_sdk import YNAB
from ynab_sdk.api.models.requests.transaction import TransactionRequest

import plaid
import logging
import datetime

import os
import json


class PlaidImporter:
    def __init__(self, Secrets):
        self.plaid_client_id = Secrets.getSecret('plaid.client_id')
        self.plaid_secret = Secrets.getSecret('plaid.secret')
        self.plaid_env = Secrets.getSecret('plaid.env')
        self.plaid_tokens = Secrets.getSecret('plaid.access_tokens')
        self.account_mapping = Secrets.getSecret('plaid.account_mappings')

        self.ynab_token = Secrets.getSecret(
            "ynab_token").strip()
        self.ynab_budget_id = Secrets.getSecret(
            "plaid.ynab_budget_id").strip()

        self.logger = logging.getLogger('plaid')

        self.plaidClient = plaid.Client(client_id=self.plaid_client_id,
                                        secret=self.plaid_secret,
                                        environment=self.plaid_env)

        self.ynabClient = YNAB(self.ynab_token)

    def get_account_mapping_for_ynab_id(self, id):
        for i in self.account_mapping:
            if i["ynab_account"] == id:
                return i
        return None

    def create_transaction(self, dateString, currentValue,  ynab_account):
        delta = round(currentValue - ynab_account.cleared_balance / 1000, 2)
        self.logger.info("[{}] current: {} last: {} delta: {}".format(ynab_account.name,
                                                                      currentValue, ynab_account.balance / 1000, delta))

        if delta != 0:
            return TransactionRequest(
                ynab_account.id,
                dateString,
                int(delta * 1000),
                payee_name="Investment Return",
                cleared="cleared",
                approved=True,
                import_id="plaid-{}".format(dateString)
            )
        return None

    def get_plaid_balances(self):
        balances = {}
        for t in self.plaid_tokens:
            try:
                balance_response = self.plaidClient.Accounts.balance.get(
                    t["token"])
            except plaid.errors.PlaidError as e:
                pretty_print_response({'account': t["_name"], 'error': {
                    'display_message': e.display_message, 'error_code': e.code, 'error_type': e.type}})
                continue

            for account in balance_response["accounts"]:
                id = account["account_id"]
                balance = account["balances"]["current"]
                balances[id] = balance

        return balances

    def update_ynab(self):
        try:
            # Account list
            ynabAccounts = self.ynabClient.accounts.get_accounts(
                self.ynab_budget_id)
        except Exception as e:
            self.logger.error(
                "Exception when calling accounts->get_accounts: %s\n" % e)
            return

        balances = self.get_plaid_balances()

        transactions = []
        dateString = datetime.datetime.now().strftime("%Y-%m-%d")
        for a in ynabAccounts.data.accounts:
            account_mapping = self.get_account_mapping_for_ynab_id(a.id)
            if account_mapping is None:
                continue
            if account_mapping["account_id"] in balances:
                balance = balances[account_mapping["account_id"]]

                transaction = self.create_transaction(
                    dateString, balance, a)

                if transaction:
                    transactions.append(transaction)

        if len(transactions):
            try:
                self.ynabClient.transactions.create_transactions(
                    self.ynab_budget_id, transactions)
                self.logger.info("plaid done")
            except Exception as e:
                self.logger.error(
                    "Exception when creating transactions: %s\n" % e)
        else:
            self.logger.info("No new transactions to create")

    def run(self):
        # print(self.plaidClient.Item.remove(
        #     "access-development-4ac20c33-10b3-4ced-80ad-188b588d27be"))
        self.update_ynab()


def pretty_print_response(response):
    print(json.dumps(response, indent=2, sort_keys=True))
