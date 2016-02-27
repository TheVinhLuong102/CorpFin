from copy import deepcopy
from namedlist import namedlist
from sympy import Min, Symbol
from HelpyFuncs.SymPy import sympy_theanify


class CapitalStructure:
    def __init__(self, *n_securities):
        self.outstanding = {}
        self.lifo = []
        n_security_factory = namedlist('N_Security', ['n', 'security'])
        for x in n_securities:
            if isinstance(x, (list, tuple)):
                n, security = x
            else:
                n = 1
                security = x
            self.outstanding[security.label] = n_security_factory(n=n, security=security)
            self.lifo.append(security.label)

        # calculate & compile Waterfall structure
        self.waterfall()

    def __contains__(self, item):
        return item in self.outstanding

    def __getitem__(self, item):
        if isinstance(item, int):
            item = self.lifo[item]
        return self.outstanding[item]

    def __iter__(self):
        return self.outstanding.keys()

    def copy(self, deep=True):
        if deep:
            return deepcopy(self)
        else:
            cap_struct = CapitalStructure()
            cap_struct.outstanding = self.outstanding.copy()
            cap_struct.lifo = deepcopy(self.lifo)
            cap_struct.waterfall()
            return cap_struct

    def waterfall(self):
        v = Symbol('enterprise_val')
        print('Compiling Waterfall Structure:')
        for liquidation_order_high_to_low in reversed(range(len(self.lifo))):
            n, security = self[liquidation_order_high_to_low]
            print('    %s' % security.label)
            if liquidation_order_high_to_low:
                claimable = Min(n * security.claim_val_expr, v)
                security.val = sympy_theanify(claimable / n)
                v -= claimable
            else:
                security.val = sympy_theanify(v / n)
        print('done!')

    def __call__(self, **kwargs):
        return {security_label: self[security_label].security.val(**kwargs)
                for security_label in self}

    def issue(self, security='', n=1, liquidation_order=0, inplace=True, deep=True):
        if inplace:
            cap_struct = self
        else:
            cap_struct = self.copy(deep=deep)

        if isinstance(security, str) and security in cap_struct:
            n_security = cap_struct[security]
            n_security.n += n
        else:
            security_label = security.label
            n_security_factory = namedlist('N_Security', ['n', 'security'])
            cap_struct.outstanding[security_label] = n_security_factory(n=n, security=security)
            cap_struct.lifo.insert(liquidation_order, security_label)

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
            del n_security
            cap_struct.lifo.remove(security_label)
        else:
            n_security.n -= n

        cap_struct.waterfall()

        if not inplace:
            return cap_struct
