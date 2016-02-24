from pandas import DataFrame
from .Security import Security


def val(asset):
    if isinstance(asset, Security):
        return asset.val
    else:
        return asset.val()


class Portfolio:
    def __init__(self, name, *n_assets):
        self.name = name
        self.c = [(x[0], x[1]) if isinstance(x, (list, tuple)) else (1, x)
                  for x in n_assets]

    def val(self):
        return reduce(lambda x, y: x + y, map(lambda x: x[0] * val(x[1]), self.c))

    def __repr__(self):
        df = DataFrame(columns=['n', 'asset', 'val'])
        df.loc[''] = ['', 'TOTAL', self.val()]
        for i in range(len(self.c)):
            n, asset = self.c[i]
            v = val(asset)
            if isinstance(asset, Portfolio):
                if asset.name:
                    s = ' "%s"' % asset.name
                else:
                    s = ''
                asset = 'Portfolio' + s + ': Val = %.3g' % v
            else:
                asset = repr(asset)
            df.loc[i] = [n, asset, n * v]
        return repr(df)
