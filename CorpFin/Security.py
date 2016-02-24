

class Security:
    def __init__(self, label='', par=0., val=0.):
        self.name = label
        self.par = par
        self.val = val

    def __repr__(self):
        if self.name:
            s = ' "%s"' % self.name
        else:
            s = ''
        return 'Security' + s + ': Par = %.3g, Val = %.3g' % (self.par, self.val)


DOLLAR = Security(label='$', par=1., val=1.)
