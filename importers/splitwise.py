from splitwise import Splitwise
import ynab
from ynab.rest import ApiException
import logging


class SplitwiseImporter:
    def __init__(self, Secrets):
        self.ynab_budget_id = Secrets.getSecret(
            'splitwise.ynab_budget_id').strip()
        self.ynab_splitwise_account_id = Secrets.getSecret(
            'splitwise.ynab_splitwise_account_id').strip()
        self.splitwise_group_name = Secrets.getSecret(
            'splitwise.splitwise_group_name').strip()

        consumer_key = Secrets.getSecret(
            'splitwise.consumer_key').strip()
        consumer_secret = Secrets.getSecret(
            'splitwise.consumer_secret').strip()
        oauth_token = Secrets.getSecret(
            'splitwise.oauth_token').strip()
        oauth_token_secret = Secrets.getSecret(
            'splitwise.oauth_token_secret').strip()

        self.logger = logging.getLogger('splitwise')

        self.splitwise = Splitwise(
            consumer_key, consumer_secret)
        access_token = {'oauth_token': oauth_token,
                        'oauth_token_secret': oauth_token_secret}
        self.splitwise.setAccessToken(access_token)

        self.currentUserId = self.splitwise.getCurrentUser().getId()

        if self.splitwise_group_name:
            groups = self.splitwise.getGroups()
            for g in groups:
                if g.getName() == self.splitwise_group_name:
                    self.logger.info("Found splitwise group")
                    self.splitwise_group_id = g.getId()

            if not self.splitwise_group_id:
                self.logger.error("Couldnt find group %s",
                                  self.splitwise_group_name)

    def generate_ynab_transaction(self, e):
        user = None
        for u in e.getUsers():
            if u.getId() == self.currentUserId:
                user = u
        if not user:
            return {}

        return {
            "account_id": self.ynab_splitwise_account_id,
            "date": e.getDate(),
            "amount": int(float(user.getNetBalance()) * 1000),
            "payee_name": e.getDescription() if float(user.getNetBalance()) < 0 else "Splitwise Contribution",
            "memo": "eur-may19" + ((", " + e.getDescription()) if float(user.getNetBalance()) > 0 else ""),
            "cleared": "cleared",
            "approved": False,
            "import_id": e.getId()
        }

    def run(self):
        expenses = self.splitwise.getExpenses(group_id=self.splitwise_group_id)
        transactions = []

        delta = 0
        for e in expenses:
            transaction = self.generate_ynab_transaction(e)
            if transaction == {}:
                self.logger.warning(“Got empty transaction for “ + e.getDescription())
                continue
            transactions.append(transaction)
            print(e, transaction)
            delta += float(transaction["amount"])

#         transactions.append({
#             "account_id": self.ynab_splitwise_account_id,
#             "date": "2019-04-18",
#             "amount": int(delta) * -1,
#             "payee_name": "Splitwise Reimbursement",
#             "cleared": "cleared",
#             "approved": False,
#             "memo": "Splitwise reimbursement for {}".format(self.splitwise_group_name),
#             "import_id": "splitwise-reimbursement-{}".format(self.splitwise_group_id)
#         })

        if len(transactions):
            try:
                ynab.TransactionsApi().bulk_create_transactions(
                    self.ynab_budget_id, {"transactions": transactions})
                self.logger.info("splitwise done")
            except ApiException as e:
                self.logger.error(
                    "Exception when creating transactions: %s\n" % e)
