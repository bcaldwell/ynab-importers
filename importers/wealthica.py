import boto3
from warrant import Cognito, AWSSRP, aws_srp
import pyotp
import base64
import os
import datetime
import ynab
from ynab.rest import ApiException
import time
import requests
import logging


class WealthicaImporter:
    def __init__(self, Secrets):
        self.wealthica_password = Secrets.getSecret(
            'wealthica.password').strip()
        self.wealthica_username = Secrets.getSecret(
            'wealthica.username').strip()
        self.wealthica_opt_secret = Secrets.getSecret(
            'wealthica.opt_secret').strip()
        self.ynab_budget_id = Secrets.getSecret(
            "wealthica.ynab_budget_id").strip()
        self.account_mapping = Secrets.getSecret("wealthica.accountMapping")

        self.totp = pyotp.TOTP(self.wealthica_opt_secret)

        self.logger = logging.getLogger('wealthica')

    def generate_hash_device(self, device_group_key, device_key):
        # source: https://github.com/amazon-archives/amazon-cognito-identity-js/blob/6b87f1a30a998072b4d98facb49dcaf8780d15b0/src/AuthenticationHelper.js#L137

        # random device password, which will be used for DEVICE_SRP_AUTH flow
        device_password = base64.standard_b64encode(
            os.urandom(40)).decode('utf-8')

        combined_string = '%s%s:%s' % (
            device_group_key, device_key, device_password)
        combined_string_hash = aws_srp.hash_sha256(
            combined_string.encode('utf-8'))
        salt = aws_srp.pad_hex(aws_srp.get_random(16))

        x_value = aws_srp.hex_to_long(
            aws_srp.hex_hash(salt + combined_string_hash))
        g = aws_srp.hex_to_long(aws_srp.g_hex)
        big_n = aws_srp.hex_to_long(aws_srp.n_hex)
        verifier_device_not_padded = pow(g, x_value, big_n)
        verifier = aws_srp.pad_hex(verifier_device_not_padded)

        device_secret_verifier_config = {
            "PasswordVerifier": base64.standard_b64encode(bytearray.fromhex(verifier)).decode('utf-8'),
            "Salt": base64.standard_b64encode(bytearray.fromhex(salt)).decode('utf-8')
        }
        return device_password, device_secret_verifier_config

    def login(self):
        mfa_code = self.totp.now()

        client_id = '3ismpgna2lcmrbvamqv8a3h79m'
        client = boto3.client('cognito-idp', **{'region_name': 'us-east-1',
                                                'aws_access_key_id': 'dummy_not_used', 'aws_secret_access_key': 'dummy_not_used'})

        aws = AWSSRP(username=self.wealthica_username, password=self.wealthica_password, pool_id='us-east-1_jm1wExvHt',
                     client_id=client_id, client=client,
                     client_secret=None)
        tokens = aws.authenticate_user()

        auth_params = aws.get_auth_params()
        challenge_response = {
            'USERNAME': auth_params['USERNAME'],
            'SMS_MFA_CODE': mfa_code,
            'SOFTWARE_TOKEN_MFA_CODE': mfa_code
        }

        tokens = client.respond_to_auth_challenge(
            ClientId=client_id,
            ChallengeName='SOFTWARE_TOKEN_MFA',
            Session=tokens['Session'],
            ChallengeResponses=challenge_response)

        device_key = tokens['AuthenticationResult']['NewDeviceMetadata']['DeviceKey']
        device_group_key = tokens['AuthenticationResult']['NewDeviceMetadata']['DeviceGroupKey']
        device_password, device_secret_verifier_config = self.generate_hash_device(
            device_group_key, device_key)

        response = client.confirm_device(
            AccessToken=tokens['AuthenticationResult']['AccessToken'],
            DeviceKey=device_key,
            DeviceSecretVerifierConfig=device_secret_verifier_config,
            DeviceName='Jupyter'
        )
        self.bearer = "Bearer {}".format(
            tokens['AuthenticationResult']['IdToken'])

    def refresh_data(self):
        try:
            r = requests.post(
                "https://app.wealthica.com/api/institutions/sync", headers={"Authorization": self.bearer})
            time.sleep(10)
        except:
            self.logger.error(
                "Exception when calling app.wealthica.com/api/institutions\n")

    def get_from_account_mapping(self, id):
        for i in self.account_mapping:
            if i["ynab_account"] == id:
                return i
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
            wealthicaInstitutions = requests.get(
                "https://app.wealthica.com/api/institutions", headers={"Authorization": self.bearer})
            wealthicaInstitutions = wealthicaInstitutions.json()
        except:
            self.logger.error(
                "Exception when calling app.wealthica.com/api/institutions\n")
            return

        transactions = []
        dateString = datetime.datetime.now().strftime("%Y-%m-%d")
        for a in ynabAccounts.data.accounts:
            account_mapping = self.get_from_account_mapping(a.id)
            if account_mapping:
                for i in wealthicaInstitutions:
                    if i['id'] == account_mapping['institutionID']:
                        if "accountID" in account_mapping:
                            currentValue = [investment['value'] for investment in i['investments']
                                            if investment['id'] == account_mapping['accountID']][0]
                        else:
                            currentValue = i['value']
                        delta = round(currentValue - a.balance / 1000, 2)
                        self.logger.info("[{}] current: {} last: {} delta: {}".format(a.name,
                                                                                      currentValue, a.balance / 1000, delta))

                        if delta != 0:
                            transactions.append({
                                "account_id": a.id,
                                "date": dateString,
                                "amount": int(delta * 1000),
                                "payee_name": "Investment Return",
                                "cleared": "cleared",
                                "approved": True,
                            })

        if len(transactions):
            try:
                ynab.TransactionsApi().bulk_create_transactions(
                    self.ynab_budget_id, {"transactions": transactions})
                self.logger.info("wealthica done")
            except ApiException as e:
                self.logger.error(
                    "Exception when calling AccountsApi->get_accounts: %s\n" % e)

    def run(self):
        self.login()
        self.refresh_data()
        self.update_ynab()
