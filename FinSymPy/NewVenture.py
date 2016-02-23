from __future__ import absolute_import, division, print_function
from numpy import nan, isnan
from pandas import DataFrame
from sympy import Expr, Symbol, symbols
from sympy.printing.theanocode import theano_function
from HelpyFuncs.SymPy import sympy_eval_by_theano
from .Valuation import net_present_value, present_value, terminal_value


class NewVentureValuationModel:

    def __init__(self, venture_name='', year_0=0, nb_pro_forma_years_excl_0=1, compile=True):

        # set Venture Name and corresponding variable prefixes
        self.venture_name = venture_name
        if venture_name:
            self.venture_name_prefix = '%s___' % venture_name
        else:
            self.venture_name_prefix = ''

        # set pro forma period timeline
        self.year_0 = year_0
        nb_pro_forma_years_incl_0 = nb_pro_forma_years_excl_0 + 1
        self.nb_pro_forma_years_excl_0 = nb_pro_forma_years_excl_0
        self.final_pro_forma_year = year_0 + nb_pro_forma_years_excl_0
        index_range = range(nb_pro_forma_years_incl_0)
        index_range_from_1 = range(1, nb_pro_forma_years_incl_0)

        # model Revenue
        self.Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'Revenue___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.RevenueGrowth___input = \
            (nan,) + \
            symbols(
                self.venture_name_prefix +
                'RevenueGrowth___%d:%d' % (year_0 + 1, self.final_pro_forma_year + 1))

        self.Revenue = [self.Revenue___input[0]]
        for i in index_range_from_1:
            self.Revenue.append(
                self.Revenue___input[i] +
                (self.Revenue___input[i] <= 0.) * (1. + self.RevenueGrowth___input[i]) * self.Revenue[-1])

        self.RevenueChange = \
            [nan] + \
            [self.Revenue[i] - self.Revenue[i - 1]
             for i in index_range_from_1]

        self.RevenueGrowth = \
            [nan] + \
            [self.RevenueChange[i] / self.Revenue[i - 1]
             for i in index_range_from_1]

        # model OpEx
        self.OpEx___input = \
            symbols(
                self.venture_name_prefix +
                'OpEx___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.OpEx = self.OpEx___input

        self.OpEx_over_Revenue = \
            [self.OpEx[i] / self.Revenue[i]
             for i in index_range]

        self.OpExGrowth = \
            [nan] + \
            [self.OpEx[i] / self.OpEx[i - 1] - 1.
             for i in index_range_from_1]

        # model EBIT
        self.EBIT___input = \
            symbols(
                self.venture_name_prefix +
                'EBIT___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.EBITMargin___input = \
            symbols(
                self.venture_name_prefix +
                'EBITMargin___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.EBIT = \
            [self.EBIT___input[i] +
             (self.EBIT___input[i] <= 0.) *
             ((self.OpEx[i] > 0.) * (self.Revenue[i] - self.OpEx[i]) +
              (self.OpEx[i] <= 0.) * (self.EBITMargin___input[i] * self.Revenue[i]))
             for i in index_range]

        self.EBITMargin = \
            [self.EBIT[i] / self.Revenue[i]
             for i in index_range]

        self.EBITGrowth = \
            [nan] + \
            [self.EBIT[i] / self.EBIT[i - 1] - 1.
             for i in index_range_from_1]

        # model EBIAT
        self.CorpTaxRate___input = \
            Symbol(
                self.venture_name_prefix +
                'CorpTaxRate')

        one_minus_corp_tax_rate = 1. - self.CorpTaxRate___input

        self.EBIAT = \
            map(lambda x: one_minus_corp_tax_rate * x,
                self.EBIT)

        # model CLOSING Fixed Assets NET of cumulative Depreciation
        self.FA___input = \
            symbols(
                self.venture_name_prefix +
                'FA___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.FA_over_Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'FA_over_Revenue___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.FAGrowth___input = \
            (nan,) + \
            symbols(
                self.venture_name_prefix +
                'FAGrowth___%d:%d' % (year_0 + 1, self.final_pro_forma_year + 1))

        self.FA = [self.FA___input[0]]
        for i in index_range_from_1:
            self.FA.append(
                self.FA___input[i] +
                (self.FA___input[i] <= 0.) *
                (self.FA_over_Revenue___input[i] * self.Revenue[i] +
                 (1. + self.FAGrowth___input[i]) * self.FA[-1]))

        self.FA_over_Revenue = \
            [self.FA[i] / self.Revenue[i]
             for i in index_range]

        self.FAGrowth = \
            [nan] + \
            [self.FA[i] / self.FA[i - 1] - 1.
             for i in index_range_from_1]

        # model Depreciation
        self.Depreciation___input = \
            symbols(
                self.venture_name_prefix +
                'Depreciation___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.Depreciation_over_prevFA___input = \
            Symbol(
                self.venture_name_prefix + \
                'Depreciation_over_prevFA')

        self.Depreciation = \
            [self.Depreciation___input[0]] + \
            [self.Depreciation___input[i] +
             (self.Depreciation___input[i] <= 0.) *
             self.Depreciation_over_prevFA___input * self.FA[i - 1]
             for i in index_range_from_1]

        self.Depreciation_over_prevFA = \
            [nan] + \
            [self.Depreciation[i] / self.FA[i - 1]
             for i in index_range_from_1]

        # model Capital Expenditure
        self.CapEx___input = \
            symbols(
                self.venture_name_prefix +
                'CapEx___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.CapEx_over_Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'CapEx_over_Revenue___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.CapEx_over_RevenueChange___input = \
            Symbol(
                self.venture_name_prefix +
                'CapEx_over_RevenueChange')

        self.CapExGrowth___input = \
            (nan,) + \
            symbols(
                self.venture_name_prefix +
                'CapExGrowth___%d:%d' % (year_0 + 1, self.final_pro_forma_year + 1))

        self.CapEx = [self.CapEx___input[0]]
        for i in index_range_from_1:
            self.CapEx.append(
                self.CapEx___input[i] +
                (self.CapEx___input[i] <= 0.) *
                (self.FA[i] + self.Depreciation[i] - self.FA[i - 1] +
                 self.CapEx_over_Revenue___input[i] * self.Revenue[i] +
                 self.CapEx_over_RevenueChange___input * self.RevenueChange[i] +
                 (1. + self.CapExGrowth___input[i]) * self.CapEx[-1]))

        self.CapEx_over_Revenue = \
            [self.CapEx[i] / self.Revenue[i]
             for i in index_range]

        self.CapEx_over_RevenueChange = \
            [nan] + \
            [self.CapEx[i] / self.RevenueChange[i]
             for i in index_range_from_1]

        self.CapExGrowth = \
            [nan] + \
            [self.CapEx[i] / self.CapEx[i - 1] - 1.
             for i in index_range_from_1]

        # model Net Working Capital and its change
        self.NWC___input = \
            symbols(
                self.venture_name_prefix +
                'NWC___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.NWC_over_Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'NWC_over_Revenue___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.NWCGrowth___input = \
            (nan,) + \
            symbols(
                self.venture_name_prefix +
                'NWCGrowth___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.NWC = [self.NWC___input[0]]
        for i in index_range_from_1:
            self.NWC.append(
                self.NWC___input[i] +
                (self.NWC___input[i] <= 0.) *
                (self.NWC_over_Revenue___input[i] * self.Revenue[i] +
                 (1. + self.NWCGrowth___input[i]) * self.NWC[-1]))

        self.NWC_over_Revenue = \
            [self.NWC[i] / self.Revenue[i]
             for i in index_range]

        self.NWCGrowth = \
            [nan] + \
            [self.NWC[i] / self.NWC[i - 1] - 1.
             for i in index_range_from_1]

        self.NWCChange___input = \
            symbols(
                self.venture_name_prefix +
                'NWCChange___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.NWCChange_over_Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'NWCChange_over_Revenue___%d:%d' % (year_0, self.final_pro_forma_year + 1))

        self.NWCChange_over_RevenueChange___input = \
            Symbol(
                self.venture_name_prefix +
                'NWCChange_over_RevenueChange')

        self.NWCChange = [self.NWCChange___input[0]]
        for i in index_range_from_1:
            self.NWCChange.append(
                self.NWCChange___input[i] +
                (self.NWCChange___input[i] <= 0.) *
                (self.NWC[i] - self.NWC[i - 1] +
                 self.NWCChange_over_Revenue___input[i] * self.Revenue[i] +
                 self.NWCChange_over_RevenueChange___input * self.RevenueChange[i]))

        self.NWCChange_over_Revenue = \
            [self.NWCChange[i] / self.Revenue[i]
             for i in index_range]

        self.NWCChange_over_RevenueChange = \
            [nan] + \
            [self.NWCChange[i] / self.RevenueChange[i]
             for i in index_range_from_1]

        # model Free Cash Flows before Terminal Value
        self.FCF = \
            [self.EBIAT[i] + self.Depreciation[i] - self.CapEx[i] - self.NWCChange[i]
             for i in index_range]

        # model Discount Rates
        self.RiskFreeRate___input = \
            Symbol(
                self.venture_name_prefix +
                'RiskFreeRate')

        self.PublicMarketReturn___input = \
            Symbol(
                self.venture_name_prefix +
                'PublicMarketReturn')

        self.PublicMarketPremium___input = \
            Symbol(
                self.venture_name_prefix +
                'PublicMarketPremium')

        self.PublicMarketPremium = \
            self.PublicMarketPremium___input + \
            (self.PublicMarketPremium___input <= 0.) * (self.PublicMarketReturn___input - self.RiskFreeRate___input)

        self.ProFormaPeriodBeta___input = \
            Symbol(
                self.venture_name_prefix +
                'ProFormaPeriodBeta')

        self.ProFormaPeriodDiscountRate___input = \
            Symbol(
                self.venture_name_prefix +
                'ProFormaPeriodDiscountRate')

        self.ProFormaPeriodDiscountRate = \
            self.ProFormaPeriodDiscountRate___input + \
            (self.ProFormaPeriodDiscountRate___input <= 0.) * \
            (self.RiskFreeRate___input + self.ProFormaPeriodBeta___input * self.PublicMarketPremium)

        self.StabilizedBeta___input = \
            Symbol(
                self.venture_name_prefix +
                'StabilizedBeta')

        self.StabilizedDiscountRate___input = \
            Symbol(
                self.venture_name_prefix +
                'StabilizedDiscountRate')

        self.StabilizedDiscountRate = \
            self.StabilizedDiscountRate___input + \
            (self.StabilizedDiscountRate___input <= 0.) * \
            (self.RiskFreeRate___input + self.StabilizedBeta___input * self.PublicMarketPremium)

        # model Long-Term Growth Rate
        self.LongTermGrowthRate___input = \
            Symbol(
                self.venture_name_prefix +
                'LongTermGrowthRate')

        # model Terminal Value
        self.TV_RevenueMultiple___input = \
            Symbol(
                self.venture_name_prefix +
                'TV_RevenueMultiple')

        self.TV = \
            self.TV_RevenueMultiple___input * self.Revenue[-1] + \
            (self.TV_RevenueMultiple___input <= 0.) * \
            terminal_value(
                terminal_cash_flow=self.FCF[-1],
                long_term_discount_rate=self.StabilizedDiscountRate,
                long_term_growth_rate=self.LongTermGrowthRate___input)

        self.TV_RevenueMultiple = \
            self.TV / self.Revenue[-1]

        # model Valuation
        self.Val_of_FCF = \
            net_present_value(
                cash_flows=[0.] + self.FCF[1:],
                discount_rate=self.ProFormaPeriodDiscountRate)

        self.Val_of_TV = \
            present_value(
                amount=self.TV,
                discount_rate=self.StabilizedDiscountRate,
                nb_periods=nb_pro_forma_years_excl_0)

        self.Val = self.Val_of_FCF + self.Val_of_TV

        # list all Input attributes & symbols
        self.input_attrs = \
            ['Revenue', 'RevenueGrowth',
             'OpEx',
             'EBIT', 'EBITMargin',
             'CorpTaxRate',
             'FA', 'FA_over_Revenue', 'FAGrowth',
             'Depreciation', 'Depreciation_over_prevFA',
             'CapEx', 'CapEx_over_Revenue', 'CapEx_over_RevenueChange', 'CapExGrowth',
             'NWC', 'NWC_over_Revenue', 'NWCGrowth',
             'NWCChange',
             'NWCChange_over_Revenue', 'NWCChange_over_RevenueChange',
             'RiskFreeRate', 'PublicMarketReturn', 'PublicMarketPremium',
             'ProFormaPeriodBeta', 'ProFormaPeriodDiscountRate',
             'StabilizedBeta', 'StabilizedDiscountRate',
             'LongTermGrowthRate',
             'TV_RevenueMultiple']

        # gather all Input symbols and set their default values
        self.input_symbols = []
        self.input_defaults = {}
        for input_attr in self.input_attrs:
            a = getattr(self, '%s___input' % input_attr)
            if isinstance(a, (list, tuple)):
                if (not isinstance(a[0], Symbol)) and isnan(a[0]):
                    for i in index_range_from_1:
                        self.input_symbols.append(a[i])
                        self.input_defaults[a[i].name] = -1.
                else:
                    for i in index_range:
                        self.input_symbols.append(a[i])
                        self.input_defaults[a[i].name] = 0.
            else:
                self.input_symbols.append(a)
                self.input_defaults[a.name] = 0.

        # list all Output attributes
        self.output_attrs = \
            ['PublicMarketPremium', 'ProFormaPeriodDiscountRate', 'StabilizedDiscountRate',
             'Revenue', 'RevenueChange', 'RevenueGrowth',
             'OpEx', 'OpEx_over_Revenue', 'OpExGrowth',
             'EBIT', 'EBITMargin', 'EBITGrowth',
             'EBIAT',
             'FA', 'FA_over_Revenue', 'FAGrowth',
             'Depreciation', 'Depreciation_over_prevFA',
             'CapEx', 'CapEx_over_Revenue', 'CapEx_over_RevenueChange', 'CapExGrowth',
             'NWC', 'NWC_over_Revenue', 'NWCGrowth',
             'NWCChange', 'NWCChange_over_Revenue',
             'NWCChange_over_RevenueChange',
             'FCF',
             'TV',
             'Val_of_FCF', 'Val_of_TV', 'Val']

        # compile Outputs if so required
        if compile:
            print('Compiling:')
            for output in self.output_attrs:
                print('    %s' % output)
                a = getattr(self, output)
                if isinstance(a, (list, tuple)):
                    if (not isinstance(a[0], Expr)) and isnan(a[0]):
                        setattr(
                            self, output,
                            [nan] + [theano_function(self.input_symbols, [a[i]]) for i in index_range_from_1])
                    else:
                        setattr(
                            self, output,
                            [theano_function(self.input_symbols, [a[i]]) for i in index_range])
                else:
                    setattr(self, output, theano_function(self.input_symbols, [a]))
            print('done!')
            self.compiled = True
        else:
            self.compiled = False

    def __call__(self, outputs=None, **kwargs):

        if not outputs:
            outputs=self.output_attrs

        inputs = self.input_defaults.copy()
        for k, v in kwargs.items():
            a = getattr(self, '%s___input' % k)
            if isinstance(a, (list, tuple)):
                for i in range(len(v)):
                    if isinstance(a[i], Symbol) and not isnan(v[i]):
                        inputs[a[i].name] = v[i]
            else:
                inputs[a.name] = v

        def calc(x):
            if isinstance(x, (list, tuple)):
                return [calc(i) for i in x]
            elif callable(x):
                return float(x(**inputs))
            elif (not isinstance(x, Expr)) and isnan(x):
                return nan
            else:
                return float(sympy_eval_by_theano(sympy_expr=x, symbols=self.input_symbols, **inputs))

        results = {}
        df = DataFrame(index=['Year 0'] + range(self.year_0 + 1, self.final_pro_forma_year + 1))
        print('Calculating:')
        for output in outputs:
            if output in self.output_attrs:
                print('    %s' % output)
                result = calc(getattr(self, output))
                results[output] = result
                if isinstance(result, (list, tuple)):
                    df[output] = result
                else:
                    df[output] = ''
                    if output in ('TV', 'TV_RevenueMultiple'):
                        df.loc[self.final_pro_forma_year, output] = result
                    else:
                        df.loc['Year 0', output] = result
            else:
                df[output] = ''
                if output in kwargs:
                    v = kwargs[output]
                    if isinstance(v, (list, tuple)):
                        df.ix[range(len(v)), output] = v
                    elif output in ('LongTermGrowthRate', 'TV_RevenueMultiple'):
                        df.loc[self.final_pro_forma_year, output] = v
                    else:
                        df.loc['Year 0', output] = v
        print('done!')
        results['data_frame'] = df

        return results
