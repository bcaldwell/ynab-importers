from subprocess import run, PIPE
import json
import os


class Secrets:
    def __init__(self, filename):
        secret_filename = os.environ.get(
            "YNAB_IMPORTER_EJSON_SECRET_KEY", None)
        if secret_filename:
            file = open(secret_filename, "r")
            key = file.read()

            p = run(['ejson', 'decrypt', '--key-from-stdin', filename], stdout=PIPE, stderr=PIPE,
                    input=key, encoding='ascii')
        else:
            p = run(['ejson', 'decrypt', filename], stdout=PIPE, stderr=PIPE,
                    encoding='ascii')
        self.secrets = json.loads(p.stdout)

    def getSecret(self, name, d=None):
        if d is None:
            d = self.secrets

        if "." in name:
            key, rest = name.split(".", 1)
            return self.getSecret(rest, d[key])
        else:
            return d[name]
