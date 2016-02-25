from HelpyFuncs.SymPy import sympy_theanify


class Security:
    def __init__(self, label='', bs_val=0., val=0.):
        self.label = label

        self.bs_val_expr = bs_val
        self.bs_val = sympy_theanify(bs_val)

        self.val_expr = val
        self.val = sympy_theanify(val)

    def __call__(self, **kwargs):
        if self.label:
            s = ' "%s"' % self.label
        else:
            s = ''
        return 'Security' + s + ': BS Val = %.3g, Val = %.3g' % (self.bs_val(**kwargs), self.val(**kwargs))


DOLLAR = Security(label='$', bs_val=1., val=1.)
