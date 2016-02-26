from HelpyFuncs.SymPy import sympy_theanify


class Security:
    def __init__(self, label='', claim_val=0., val=0.):
        self.label = label

        self.claim_val_expr = claim_val
        self.claim_val = sympy_theanify(claim_val)

        self.val_expr = val
        self.val = sympy_theanify(val)

    def __call__(self, **kwargs):
        if self.label:
            s = ' "%s"' % self.label
        else:
            s = ''
        return 'Security' + s + ': Claim Val = %.3g, Val = %.3g' % (self.claim_val(**kwargs), self.val(**kwargs))


DOLLAR = Security(label='$', claim_val=1., val=1.)
