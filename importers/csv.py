from io import StringIO
import pandas as pd


class CSVImporter:
    def __init__():
        pass

    def readString(self, s):
        self.df = transactions = pd.read_csv(StringIO(s), sep=",", header=0)

    def apply(self, fn):
        pass

    def run(self):
        pass
