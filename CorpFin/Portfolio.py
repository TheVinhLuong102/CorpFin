from numpy import nan
from pandas import DataFrame
from .Security import Security


def val(x):
    if isinstance(x, Security):
        return x.val
    else:
        return x.val()


class Portfolio:
    def __init__(self, *n_assets):
        self.c = [(na[0], na[1]) if isinstance(na, (list, tuple)) else (1, na)
                  for na in n_assets]

    def val(self):
        return reduce(lambda x, y: x + y, map(lambda x: x[0] * val(x[1]), self.c))

    def __repr__(self):
        df = DataFrame(columns=['n', 'asset', 'val'])
        df.loc['total'] = [nan, nan, self.val()]
        for i in range(len(self.c)):
            n, asset = self.c[i]
            df.loc[i] = [n, asset, n * val(asset)]
        return repr(df)
