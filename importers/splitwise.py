from splitwise import Splitwise
import ynab
from ynab.rest import ApiException
import logging
from slugify import slugify


class SplitwiseImporter:

    def __init__(self, Secrets):
        self.ynab_budget_id = Secrets.getSecret(
            'splitwise.ynab_budget_id').strip()
        self.ynab_splitwise_account_id = Secrets.getSecret(
            'splitwise.ynab_splitwise_account_id').strip()
        self.splitwise_group_names = Secrets.getSecret(
            'splitwise.splitwise_group_names')
        self.dated_after = Secrets.getSecret(
            'splitwise.import_dated_after') or None

        consumer_key = Secrets.getSecret('splitwise.consumer_key').strip()
        consumer_secret = Secrets.getSecret(
            'splitwise.consumer_secret').strip()
        oauth_token = Secrets.getSecret('splitwise.oauth_token').strip()
        oauth_token_secret = Secrets.getSecret(
            'splitwise.oauth_token_secret').strip()

        self.logger = logging.getLogger('splitwise')

        self.splitwise = Splitwise(consumer_key, consumer_secret)
        access_token = {
            'oauth_token': oauth_token,
            'oauth_token_secret': oauth_token_secret
        }
        self.splitwise.setAccessToken(access_token)

        self.currentUserId = self.splitwise.getCurrentUser().getId()

        self.spltiwise_group_double_map = {}
        groups = self.splitwise.getGroups()
        for g in groups:
            self.spltiwise_group_double_map[g.getId()] = g.getName()
            self.spltiwise_group_double_map[g.getName()] = g.getId()

        # if self.splitwise_group_name:
        #     groups = self.splitwise.getGroups()
        #     for g in groups:
        #         if g.getName() == self.splitwise_group_name:
        #             self.logger.info("Found splitwise group")
        #             self.splitwise_group_id = g.getId()

        #     if not self.splitwise_group_id:
        #         self.logger.error("Couldnt find group %s",
        #                           self.splitwise_group_name)

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
            "payee_name": (e.getDescription()
                           if float(user.getNetBalance()) < 0 else "Splitwise Contribution"),
            "memo": (e.getDescription() + ", "
                     if float(user.getNetBalance()) > 0 else "") + ("splitwise-" + slugify(self.spltiwise_group_double_map[e.getGroupId()]) if e.getGroupId() else ""),
            "cleared": "cleared",
            "approved": False,
            "import_id": e.getId()
        }

    def run(self):
        # expenses = self.splitwise.getExpenses(group_id=self.splitwise_group_id)
        transactions = []

        if not len(self.splitwise_group_names):
            self.splitwise_group_names = [None]

        for g in self.splitwise_group_names:
            # change group name to id
            if g:
                g = self.spltiwise_group_double_map[g]

            expenses = self.splitwise.getExpenses(
                dated_after=self.dated_after, group_id=g, limit=0)

            delta = 0
            for e in expenses:
                if e.getDeletedAt():
                    continue

                transaction = self.generate_ynab_transaction(e)
                if transaction == {}:
                    # self.logger.info("Got empty transaction for " +
                    #                  e.getDescription())
                    continue

                transactions.append(transaction)
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
