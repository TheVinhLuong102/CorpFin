from __future__ import absolute_import, print_function
from copy import deepcopy
from namedlist import namedlist
from pandas import DataFrame
from sympy import Min, Symbol
from HelpyFuncs.SymPy import sympy_theanify
from .Security import Security


def parse_n_security_option(n_security_option_tuple):
    if isinstance(n_security_option_tuple, (list, tuple)):
        if len(n_security_option_tuple) == 3:
            return n_security_option_tuple
        elif len(n_security_option_tuple) == 2:
            if isinstance(n_security_option_tuple[0], (int, float)):
                return tuple(n_security_option_tuple) + (None,)
            elif isinstance(n_security_option_tuple[0], (str, Security)):
                return (1,) + tuple(n_security_option_tuple)
        elif len(n_security_option_tuple) == 1:
            security, = n_security_option_tuple
            return 1, security, None
    else:
        return 1, n_security_option_tuple, None


class CapitalStructure:
    def __init__(self, *n_security_option_tuples):
        self.outstanding = {}
        self.lifo = []
        self.optional_conversion_ratios = {}
        n_security_factory = namedlist('N_Security', ['n', 'security'])
        for n_security_option in n_security_option_tuples:
            n, security, optional_common_share_conversion_ratio = parse_n_security_option(n_security_option)
            self.outstanding[security.label] = n_security_factory(n=n, security=security)
            self.lifo.append([security.label])
            if optional_common_share_conversion_ratio:
                self.optional_conversion_ratios[security.label] = optional_common_share_conversion_ratio

        # calculate & compile Waterfall structure
        self.waterfall()

    def __contains__(self, item):
        return item in self.outstanding

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.outstanding[item]
        elif isinstance(item, int):
            return self.lifo[item]

    def __iter__(self):
        return self.lifo

    def __len__(self):
        return len(self.lifo)

    def copy(self, deep=True):
        if deep:
            return deepcopy(self)
        else:
            cap_struct = CapitalStructure()
            cap_struct.outstanding = self.outstanding.copy()
            cap_struct.lifo = deepcopy(self.lifo)
            cap_struct.optional_conversion_ratios = self.optional_conversion_ratios.copy()
            cap_struct.waterfall()
            return cap_struct

    def issue(self, n_security_option_tuple='', liq_priority=None, insert=False, inplace=True, deep=True):
        if inplace:
            cap_struct = self
        else:
            cap_struct = self.copy(deep=deep)

        n, security, optional_common_share_conversion_ratio = parse_n_security_option(n_security_option_tuple)
        if isinstance(security, str) and security in cap_struct:
            n_security = cap_struct[security]
            n_security.n += n
        else:
            security_label = security.label
            n_security_factory = namedlist('N_Security', ['n', 'security'])
            cap_struct.outstanding[security_label] = n_security_factory(n=n, security=security)
            if (liq_priority is None) or (liq_priority >= len(cap_struct)):
                cap_struct.lifo.append([security_label])
            elif insert:
                cap_struct.lifo.insert(liq_priority, [security_label])
            else:
                cap_struct.lifo[liq_priority].append(security_label)
            cap_struct.optional_conversion_ratios[security_label] = optional_common_share_conversion_ratio

        cap_struct.waterfall()

        if not inplace:
            return cap_struct

    def redeem(self, security_label='', n=None, inplace=True, deep=True):
        if inplace:
            cap_struct = self
        else:
            cap_struct = self.copy(deep=deep)

        n_security = cap_struct[security_label]
        if n is None:
            n = n_security.n
        if n >= n_security.n:
            del cap_struct.outstanding[security_label]
            i = 0
            while not (security_label in cap_struct[i]):
                i += 1
            cap_struct[i].remove(security_label)
            del cap_struct.optional_conversion_ratios[security_label]
        else:
            n_security.n -= n

        cap_struct.waterfall()

        if not inplace:
            return cap_struct

    def convert_to_common(self, security_label='', n=None, inplace=True, deep=True):
        if inplace:
            cap_struct = self
        else:
            cap_struct = self.copy(deep=deep)

        if security_label in cap_struct.optional_conversion_ratios:
            n_security = cap_struct[security_label]
            n_security_common_shares = cap_struct[0]
            r = cap_struct.optional_conversion_ratios[security_label]
            if n is None:
                n = n_security.n
            cap_struct.redeem(security_label=security_label, n=n)
            cap_struct.issue((r * n, n_security_common_shares.security.label))

        cap_struct.waterfall()

        if not inplace:
            return cap_struct

    def waterfall(self):
        v = Symbol('enterprise_val')
        for liq_priority_high_to_low in reversed(range(len(self))):
            security_labels = self[liq_priority_high_to_low]
            if liq_priority_high_to_low:
                total_claim_val_this_round = \
                    reduce(
                        lambda x, y: x + y,
                        map(lambda x: x.n * x.security.claim_val_expr,
                            map(lambda x: self[x],
                                security_labels)))
                claimable = Min(total_claim_val_this_round, v)
                for security_label in security_labels:
                    n, security = self[security_label]
                    security.val_expr = (claimable / total_claim_val_this_round) * security.claim_val_expr
                    security.val = sympy_theanify(security.val_expr)
                v -= claimable
            else:
                n, common_share = self[security_labels[0]]
                common_share.val_expr = v / n
                common_share.val = sympy_theanify(common_share.val_expr)

    def val(self, **kwargs):
        return {security_label: self[security_label].security.val(**kwargs)
                for security_label in self}

    def __call__(self, **kwargs):
        df = DataFrame(columns=['liq. priority (0=lowest)', 'outstanding', 'val / unit', 'conversion ratio'])
        for i in range(len(self)):
            security_labels = self[i]
            for security_label in security_labels:
                n, security = self[security_label]
                optional_conversion_ratio = self.optional_conversion_ratios.get(security_label)
                df.loc[security_label] = i, n, security.val(**kwargs), optional_conversion_ratio
        df['liq. priority (0=lowest)'] = df['liq. priority (0=lowest)'].astype(int)
        return df
