from namedlist import namedlist
from pandas import DataFrame
from .Security import Security


def val(asset, **kwargs):
    if isinstance(asset, (Security, Portfolio)):
        return asset.val(**kwargs)
    else:
        return asset


class Portfolio:
    def __init__(self, label, *n_assets):
        self.label = label
        n_asset = namedlist('N_Asset', ['n', 'asset'])
        self.c = \
            [n_asset(n=x[0], asset=x[1]) if isinstance(x, (list, tuple))
             else n_asset(n=1, asset=x)
             for x in n_assets]

    def val(self, **kwargs):
        return reduce(lambda x, y: x + y, map(lambda x: x.n * val(x.asset, **kwargs), self.c))

    def __call__(self, **kwargs):
        df = DataFrame(columns=['n', 'asset', 'val'])
        df.loc[''] = ['', 'TOTAL', 0.]

        for i in range(len(self.c)):
            n, asset = self.c[i]
            v = val(asset, **kwargs)
            if isinstance(asset, Portfolio):
                if asset.label:
                    s = ' "%s"' % asset.label
                else:
                    s = ''
                asset_str = 'Portfolio' + s + ': Val = %.3g' % v
            elif isinstance(asset, Security):
                asset_str = asset(**kwargs)
            else:
                asset_str = str(asset)
            df.loc[i] = [n, asset_str, n * v]

        df.loc['', 'val'] = df.val.sum()
        return df
