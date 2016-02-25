

class Security:
    def __init__(
            self, label='',
            bs_val=lambda **kwargs: 0.,
            val=lambda **kwargs: 0.):
        self.label = label
        self.bs_val = bs_val
        self.val = val

    def __call__(self, **kwargs):
        if self.label:
            s = ' "%s"' % self.label
        else:
            s = ''
        return 'Security' + s + ': BS Val = %.3g, Val = %.3g' % (self.bs_val(**kwargs), self.val(**kwargs))


DOLLAR = \
    Security(
        label='$',
        bs_val=lambda **kwargs: 1.,
        val=lambda **kwargs: 1.)
