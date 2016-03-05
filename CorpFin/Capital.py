from __future__ import absolute_import, division, print_function
from copy import copy, deepcopy
from frozendict import frozendict
from namedlist import namedlist
from numpy import allclose, float64, nan
from pandas import DataFrame
from sympy import Min, Piecewise, Symbol
from HelpyFuncs.SymPy import sympy_theanify
from .Security import Security


def parse_security_info_set(security_info_set):
    if isinstance(security_info_set, dict):
        return security_info_set
    elif isinstance(security_info_set, (list, tuple)):
        if len(security_info_set) == 2:
            if isinstance(security_info_set[0], Security) and isinstance(security_info_set[1], (int, float)):
                return security_info_set
            elif isinstance(security_info_set[0], str) and isinstance(security_info_set[1], (int, float)):
                return {security_info_set[0]: security_info_set[1]}
            elif isinstance(security_info_set[0], (int, float)) and isinstance(security_info_set[1], str):
                return {security_info_set[1]: security_info_set[0]}
        elif len(security_info_set) == 1:
            return parse_security_info_set(security_info_set[0])
    elif isinstance(security_info_set, str):
        return {security_info_set: 1}
    elif isinstance(security_info_set, Security):
        return security_info_set, None


def parse_security_info_sets(security_info_sets):
    if isinstance(security_info_sets, dict):
        return security_info_sets
    elif isinstance(security_info_sets, (list, tuple)):
        s = parse_security_info_set(security_info_sets[0])
        if isinstance(s, dict):
            for security_info_set in security_info_sets[1:]:
                s.update(parse_security_info_set(security_info_set))
        elif isinstance(s, (list, tuple)):
            s = [s]
            for security_info_set in security_info_sets[1:]:
                s.append(parse_security_info_set(security_info_set))
        return s
    elif isinstance(security_info_sets, str):
        return {security_info_sets: 1}
    elif isinstance(security_info_sets, Security):
        return (security_info_sets, None),


n_security_factory = namedlist('N_Security', ['n', 'security'])


class CapitalStructure:
    def __init__(self, *securities_and_optional_conversion_ratios):
        self.outstanding = {}
        self.lifo_liquidation_order = []
        self.optional_conversion_ratios = {}
        self.ownerships = {}
        for securities_and_optional_conversion_ratio in securities_and_optional_conversion_ratios:
            self.create_securities(securities_and_optional_conversion_ratio)
        self.common_share_label = self[0][0]

    def __contains__(self, item):
        return item in self.outstanding

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.outstanding[item]
        elif isinstance(item, int):
            return self.lifo_liquidation_order[item]

    def __iter__(self):
        return iter(self.lifo_liquidation_order)

    def __len__(self):
        return len(self.lifo_liquidation_order)

    def copy(self, deep=True):
        if deep:   # to deep-copy; this is the safest option
            return deepcopy(self)
        else:   # to shallow-copy; NOTE: this can be unclear & unsafe
            capital_structure = CapitalStructure()
            capital_structure.outstanding = self.outstanding.copy()
            capital_structure.lifo_liquidation_order = copy(self.lifo_liquidation_order)
            capital_structure.optional_conversion_ratios = self.optional_conversion_ratios.copy()
            capital_structure.ownerships = self.ownerships.copy()
            capital_structure.waterfall()
            return capital_structure

    def show(self, ownerships=False):
        if ownerships:
            df = DataFrame(columns=['Owner', 'Security', 'Quantity'])
            i = 0
            for owner, holdings in self.ownerships.items():
                for security_label, quantity in holdings.items():
                    df.loc[i] = owner, security_label, quantity
                    i += 1
            df.Quantity = df.Quantity.astype(float)
        else:
            df = DataFrame(columns=['Liquidation Order (LIFO)', 'Outstanding', 'Conversion Ratio'])
            for i in range(len(self)):
                security_labels = self[i]
                for security_label in security_labels:
                    n, security = self[security_label]
                    optional_conversion_ratio = self.optional_conversion_ratios.get(security_label)
                    df.loc[security_label] = i, n, optional_conversion_ratio
            df['Liquidation Order (LIFO)'] = df['Liquidation Order (LIFO)'].astype(int)
        return df

    def __repr__(self):
        return str(self.show())

    def create_securities(self, securities, liquidation_order=None, insert=False, inplace=True, deep=True):
        if inplace:
            capital_structure = self
        else:
            capital_structure = self.copy(deep=deep)

        securities_and_optional_common_share_conversion_ratios = parse_security_info_sets(securities)
        if len(securities_and_optional_common_share_conversion_ratios) > 1:
            liquidation_order = None

        for security, optional_common_share_conversion_ratio in securities_and_optional_common_share_conversion_ratios:

            capital_structure.outstanding[security.label] = n_security_factory(n=0, security=security)

            if (liquidation_order is None) or liquidation_order >= len(self):
                capital_structure.lifo_liquidation_order.append([security.label])
            elif insert:
                capital_structure.lifo_liquidation_order.insert(liquidation_order, [security.label])
            else:
                capital_structure.lifo_liquidation_order[liquidation_order].append(security.label)

            if optional_common_share_conversion_ratio is not None:
                capital_structure.optional_conversion_ratios[security.label] = optional_common_share_conversion_ratio

        if not inplace:
            return capital_structure

    def waterfall(self):
        v = Symbol('enterprise_val')
        for lifo_liquidation_order in reversed(range(len(self))):
            security_labels = self[lifo_liquidation_order]
            if lifo_liquidation_order:
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
                            (claimable,
                             True))
                    security.val = sympy_theanify(security.val_expr)
                v -= claimable
            else:
                n, common_share = self[security_labels[0]]
                common_share.val_expr = v / n
                common_share.val = sympy_theanify(common_share.val_expr)

    def issue(self, owner='', securities=None, inplace=True, deep=True):
        if inplace:
            capital_structure = self
        else:
            capital_structure = self.copy(deep=deep)

        if securities is not None:

            security_labels_and_quantities = parse_security_info_sets(securities)

            for security_label, quantity in security_labels_and_quantities.items():

                capital_structure[security_label].n += quantity

                if owner in capital_structure.ownerships:
                    if security_label in capital_structure.ownerships[owner]:
                        capital_structure.ownerships[owner][security_label] += quantity
                    else:
                        capital_structure.ownerships[owner][security_label] = quantity
                else:
                    capital_structure.ownerships[owner] = {security_label: quantity}

            capital_structure.waterfall()

        if not inplace:
            return capital_structure

    def transfer(self, from_owner='', to_owner='', securities=None, inplace=True, deep=True):
        if inplace:
            capital_structure = self
        else:
            capital_structure = self.copy(deep=deep)

        if securities is None:
            security_labels_and_quantities = capital_structure.ownerships[from_owner]
        else:
            security_labels_and_quantities = parse_security_info_sets(securities)

        for security_label, quantity in security_labels_and_quantities.items():

            transferred_quantity = min(capital_structure.ownerships[from_owner][security_label], quantity)

            capital_structure.ownerships[from_owner][security_label] -= transferred_quantity
            if allclose(capital_structure.ownerships[from_owner][security_label], 0.):
                del capital_structure.ownerships[from_owner][security_label]
            if not capital_structure.ownerships[from_owner]:
                del capital_structure.ownerships[from_owner]

            if to_owner in capital_structure.ownerships:
                if security_label in capital_structure.ownerships[to_owner]:
                    capital_structure.ownerships[to_owner][security_label] += transferred_quantity
                else:
                    capital_structure.ownerships[to_owner][security_label] = transferred_quantity
            else:
                capital_structure.ownerships[to_owner] = {security_label: transferred_quantity}

        if not inplace:
            return capital_structure

    def redeem(self, owners=None, securities=None, inplace=True, deep=True):
        if inplace:
            capital_structure = self
        else:
            capital_structure = self.copy(deep=deep)

        if (owners is not None) or (securities is not None):

            owners_holdings_to_redeem = \
                capital_structure.parse_owners_securities_holdings(
                    owners=owners,
                    securities=securities)

            for owner, holdings_to_redeem in owners_holdings_to_redeem.items():
                for security_label, quantity in holdings_to_redeem.items():
                    capital_structure[security_label].n -= quantity
                    if allclose(capital_structure[security_label].n, 0.):
                        capital_structure[security_label].n = 0.
                    capital_structure.ownerships[owner][security_label] -= quantity
                    if allclose(capital_structure.ownerships[owner][security_label], 0.):
                        del capital_structure.ownerships[owner][security_label]
                    if not capital_structure.ownerships[owner]:
                        del capital_structure.ownerships[owner]

            capital_structure.waterfall()

        if not inplace:
            return capital_structure

    def convert_to_common(self, owners=None, securities=None, inplace=True, deep=True):
        if inplace:
            capital_structure = self
        else:
            capital_structure = self.copy(deep=deep)

        if (owners is not None) or (securities is not None):

            owners_holdings_to_convert = \
                capital_structure.parse_owners_securities_holdings(
                    owners=owners,
                    securities=securities)

            for owner, holdings_to_convert in owners_holdings_to_convert.items():
                for security_label, quantity in holdings_to_convert.items():
                    if security_label in capital_structure.optional_conversion_ratios:
                        conversion_ratio = capital_structure.optional_conversion_ratios[security_label]
                        capital_structure.redeem(
                            owners=owner,
                            securities={security_label: quantity})
                        capital_structure.issue(
                            owner=owner,
                            securities={capital_structure.common_share_label: quantity * conversion_ratio})

            capital_structure.waterfall()

        if not inplace:
            return capital_structure

    def conversion_scenarios(self, conversions_tried={}, conversions_to_try=None):

        convertibles = set(self.optional_conversion_ratios)
        conversion_possibilities = set()
        for owner, holdings in self.ownerships.items():
            for security_label in set(holdings) & convertibles:
                conversion_possibilities.add((owner, security_label))

        if conversions_to_try is None:
            conversions_to_try = conversion_possibilities
        else:
            conversions_to_try &= conversion_possibilities

        if conversions_to_try:

            owner, security_label = conversions_to_try.pop()

            conversions_tried_0 = conversions_tried.copy()
            if owner in conversions_tried_0:
                conversions_tried_0[owner][security_label] = False
            else:
                conversions_tried_0[owner] = {security_label: False}
            d = self.conversion_scenarios(
                conversions_tried=conversions_tried_0,
                conversions_to_try=conversions_to_try.copy())

            conversions_tried_1 = conversions_tried.copy()
            if owner in conversions_tried_1:
                conversions_tried_1[owner][security_label] = True
            else:
                conversions_tried_1[owner] = {security_label: True}
            d.update(
                self.convert_to_common(
                    owners=owner,
                    securities=security_label,
                    inplace=False)
                .conversion_scenarios(
                    conversions_tried=conversions_tried_1,
                    conversions_to_try=conversions_to_try.copy()))

            return d

        else:

            return {frozendict({owners: frozendict(conversions) for owners, conversions in conversions_tried.items()}):
                    self.copy()}

    def val(self, pareto_equil_conversions=False, **kwargs):

        if self.optional_conversion_ratios and pareto_equil_conversions:

            conversion_scenario_capital_structures = self.conversion_scenarios()
            conversion_scenarios = conversion_scenario_capital_structures.keys()

            conversion_scenario_val_results = \
                {conversion_scenario: capital_structure.val(pareto_equil_conversions=False, **kwargs)
                 for conversion_scenario, capital_structure in conversion_scenario_capital_structures.items()}

            conversion_scenario_ownership_vals = \
                {conversion_scenario: val_results['ownership_vals']
                 for conversion_scenario, val_results in conversion_scenario_val_results.items()}

            for conversion_scenario, ownership_vals in conversion_scenario_ownership_vals.items():

                pareto = True

                for owner, conversions in conversion_scenario.items():

                    for alternative_conversion_scenario in conversion_scenarios:

                        pareto_alternative = True

                        for another_owner, another_owner_conversions in alternative_conversion_scenario.items():
                            if another_owner != owner:
                                pareto_alternative &= \
                                    (conversion_scenario[another_owner] ==
                                     alternative_conversion_scenario[another_owner])
                                if not pareto_alternative:
                                    break

                        if pareto_alternative:
                            pareto &= \
                                (ownership_vals[owner] >=
                                 conversion_scenario_ownership_vals[alternative_conversion_scenario][owner])
                        else:
                            continue

                if pareto:
                    return dict(
                        conversion_scenario=conversion_scenario,
                        capital_structure=conversion_scenario_capital_structures[conversion_scenario],
                        security_vals=conversion_scenario_val_results[conversion_scenario]['security_vals'],
                        ownership_vals=ownership_vals)

        else:

            convertibles = set(self.optional_conversion_ratios)
            conversion_scenario = {}
            for owner, holdings in self.ownerships.items():
                for security_label in set(holdings) & convertibles:
                    if owner in conversion_scenario:
                        conversion_scenario[owner][security_label] = False
                    else:
                        conversion_scenario[owner] = {security_label: False}

            security_vals = \
                {security_label: float64(self[security_label].security.val(**kwargs))
                 for security_label in self.outstanding}

            ownership_vals = {}
            for owner, holdings in self.ownerships.items():
                ownership_vals[owner] = \
                    reduce(
                        lambda x, y: x + y,
                        map(lambda (security_label, quantity): quantity * security_vals[security_label],
                            holdings.items()))

            return dict(
                conversion_scenario=conversion_scenario,
                capital_structure=self.copy(),
                security_vals=security_vals,
                ownership_vals=ownership_vals)

    def __call__(self, pareto_equil_conversions=False, ownerships=False, **kwargs):
        val_results = self.val(pareto_equil_conversions=pareto_equil_conversions, **kwargs)
        capital_structure = val_results['capital_structure']
        security_vals = val_results['security_vals']
        if ownerships:
            df = DataFrame(columns=['Owner', 'Security', 'Val', 'Share'])
            common_share_val = self[self.common_share_label].n * security_vals[self.common_share_label]
            i = 0
            for owner, holdings in self.ownerships.items():
                for security_label, quantity in holdings.items():
                    security_val = quantity * security_vals[security_label]
                    if security_label == self.common_share_label:
                        share_in_common = security_val / common_share_val
                    else:
                        share_in_common = nan
                    df.loc[i] = owner, security_label, security_val, share_in_common
                    i += 1
            df.loc['TOTAL'] = 2 * ('',) + (df.Val.sum(), df.Share.sum())
        else:
            df = capital_structure.show()
            df['Val / Unit'] = [security_vals[security_label] for security_label in df.index]
            df['Val'] = df.Outstanding * df['Val / Unit']
            df.loc['TOTAL'] = 4 * [''] + [df.Val.sum()]
        return df

    def parse_owners_securities_holdings(self, owners=None, securities=None):

        if (owners is not None) or (securities is not None):

            d = {}

            if owners is None:

                if isinstance(securities, str):
                    securities = securities,

                for security_label in securities:
                    for owner, holdings in self.ownerships.items():
                        if security_label in holdings:
                            quantity = holdings[security_label]
                            if owner in d:
                                d[owner][security_label] = quantity
                            else:
                                d[owner] = {security_label: quantity}

            elif isinstance(owners, (list, tuple)):

                if isinstance(securities, str):
                    securities = securities,

                for security_label in securities:
                    for owner in owners:
                        holdings = self.ownerships[owner]
                        if security_label in holdings:
                            quantity = holdings[security_label]
                            if owner in d:
                                d[owner][security_label] = quantity
                            else:
                                d[owner] = {security_label: quantity}

            elif isinstance(owners, str):

                owner = owners
                d[owner] = {}

                if isinstance(securities, dict):

                    for security_label, quantity in securities.items():
                        if security_label in self.ownerships[owner]:
                            d[owner][security_label] = \
                                min(self.ownerships[owner][security_label], quantity)

                elif isinstance(securities, str):

                    security_label = securities

                    if security_label in self.ownerships[owner]:
                        d[owner][security_label] = \
                            self.ownerships[owner][security_label]

                elif isinstance(securities, (list, tuple)):

                    for security_info_set in securities:

                        if isinstance(security_info_set, (list, tuple)):

                            if isinstance(security_info_set[0], str) and \
                                    isinstance(security_info_set[1], (int, float)):
                                security_label, quantity = security_info_set
                            elif isinstance(security_info_set[0], (int, float)) and \
                                    isinstance(security_info_set[1], str):
                                quantity, security_label = security_info_set

                            if security_label in self.ownerships[owner]:
                                d[owner][security_label] = \
                                    min(self.ownerships[owner][security_label], quantity)

                        elif isinstance(security_info_set, str):

                            security_label = security_info_set

                            if security_label in self.ownerships[owner]:
                                d[owner][security_label] = \
                                    self.ownerships[owner][security_label]

            return d
