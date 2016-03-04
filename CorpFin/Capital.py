from __future__ import absolute_import, print_function
from copy import deepcopy
from frozendict import frozendict
from namedlist import namedlist
from pandas import DataFrame
from sympy import Min, Piecewise, Symbol
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
        for i in range(len(n_security_option_tuples)):
            n, security, optional_common_share_conversion_ratio = parse_n_security_option(n_security_option_tuples[i])
            if not i:
                self.common_share_label = security.label
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
        return iter(self.lifo)

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

    def show(self):
        df = DataFrame(columns=['liq. priority (0=lowest)', 'outstanding', 'conversion ratio'])
        for i in range(len(self)):
            security_labels = self[i]
            for security_label in security_labels:
                n, security = self[security_label]
                optional_conversion_ratio = self.optional_conversion_ratios.get(security_label)
                df.loc[security_label] = i, n, optional_conversion_ratio
        df['liq. priority (0=lowest)'] = df['liq. priority (0=lowest)'].astype(int)
        return df

    def __repr__(self):
        return str(self.show())

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
                    security.val_expr = \
                        Piecewise(
                            ((claimable / total_claim_val_this_round) * security.claim_val_expr,
                             total_claim_val_this_round > 0),
                            (total_claim_val_this_round,
                             True))
                    security.val = sympy_theanify(security.val_expr)
                v -= claimable
            else:
                n, common_share = self[security_labels[0]]
                common_share.val_expr = v / n
                common_share.val = sympy_theanify(common_share.val_expr)

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
            if optional_common_share_conversion_ratio:
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
            if len(cap_struct[i]) > 1:
                cap_struct[i].remove(security_label)
            else:
                del cap_struct.lifo[i]
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
            n_security_common_shares = cap_struct[cap_struct[0][0]]
            r = cap_struct.optional_conversion_ratios[security_label]
            if n is None:
                n = n_security.n
            cap_struct.redeem(security_label=security_label, n=n)
            cap_struct.issue((r * n, n_security_common_shares.security.label))

        cap_struct.waterfall()

        if not inplace:
            return cap_struct

    def conversion_scenarios(self, securities_tried={}, securities_to_try=None):
        if securities_to_try is None:
            securities_to_try = set(self.optional_conversion_ratios)
        else:
            securities_to_try &= set(self.optional_conversion_ratios)
        if securities_to_try:
            security_label = securities_to_try.pop()
            securities_tried_0 = securities_tried.copy()
            securities_tried_0[security_label] = False
            d = self.conversion_scenarios(
                securities_tried=securities_tried_0,
                securities_to_try=securities_to_try.copy())
            securities_tried_1 = securities_tried.copy()
            securities_tried_1[security_label] = True
            d.update(
                self.convert_to_common(
                    security_label=security_label,
                    inplace=False)
                .conversion_scenarios(
                    securities_tried=securities_tried_1,
                    securities_to_try=securities_to_try.copy()))
            return d
        else:
            return {frozendict(securities_tried): self.copy()}

    def val(self, convert_in_money=True, **kwargs):
        if self.optional_conversion_ratios and convert_in_money:
            conversion_scenario_vals = \
                {conversion_scenario: cap_struct.val(convert_in_money=False, **kwargs)['vals']
                 for conversion_scenario, cap_struct in self.conversion_scenarios().items()}
            for conversion_scenario, vals in conversion_scenario_vals.items():
                for security_label, converted in conversion_scenario.items():
                    if converted:
                        vals[security_label] = \
                            self.optional_conversion_ratios[security_label] * vals[self.common_share_label]
            for conversion_scenario, vals in conversion_scenario_vals.items():
                pareto = True
                for security_label, converted in conversion_scenario.items():
                    alternative_conversion_scenario = dict(conversion_scenario)
                    alternative_conversion_scenario[security_label] = \
                        not alternative_conversion_scenario [security_label]
                    pareto &= \
                        (vals[security_label] >=
                         conversion_scenario_vals[frozendict(alternative_conversion_scenario)][security_label])
                if pareto:
                    return dict(conversion_scenario=conversion_scenario, vals=vals)
        else:
            return dict(
                conversion_scenario=dict.fromkeys(self.optional_conversion_ratios.keys(), False),
                vals={security_label: float(self[security_label].security.val(**kwargs))
                      for security_label in self.outstanding})

    def __call__(self, convert_in_money=True, **kwargs):
        df = self.show()
        val_results = self.val(convert_in_money=convert_in_money, **kwargs)
        df['converted'] = [val_results['conversion_scenario'].get(security_label) for security_label in df.index]
        df['val / unit'] = [val_results['vals'][security_label] for security_label in df.index]
        df['val'] = df.outstanding * df['val / unit']
        df.loc['TOTAL'] = 5 * [''] + [df.val.sum()]
        return df
