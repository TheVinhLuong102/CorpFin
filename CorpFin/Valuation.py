from __future__ import absolute_import, division, print_function
from datetime import datetime
from numpy import nan, isnan
from pandas import DataFrame
from sympy import And, Eq, Expr, Piecewise, Symbol, symbols
from sympy.printing.theanocode import theano_function
from HelpyFuncs.SymPy import sympy_eval_by_theano


def terminal_value(
        terminal_cash_flow=0.,
        long_term_discount_rate=.01,
        long_term_growth_rate=0.):
    return (1 + long_term_growth_rate) * terminal_cash_flow / (long_term_discount_rate - long_term_growth_rate)


def present_value(amount=0., discount_rate=0., nb_periods=0.):
    return amount / ((1 + discount_rate) ** nb_periods)


def net_present_value(
        cash_flows=(0,),
        discount_rate=0.):
    return reduce(
        lambda x, y: x + y,
        [cash_flows[i] / ((1 + discount_rate) ** i)
         for i in range(len(cash_flows))])


class ValModel:   # base class for UnlevValModel & LevValModel below
    def __init__(self, venture_name='', year_0=0, nb_pro_forma_years_excl_0=1, compile=True):

        # set Venture Name and corresponding variable prefixes
        self.venture_name = venture_name
        if venture_name:
            self.venture_name_prefix = '%s___' % venture_name
        else:
            self.venture_name_prefix = ''

        # set pro forma period timeline
        self.year_0 = year_0
        self.nb_pro_forma_years_excl_0 = nb_pro_forma_years_excl_0
        self.nb_pro_forma_years_incl_0 = nb_pro_forma_years_excl_0 + 1
        self.final_pro_forma_year = year_0 + nb_pro_forma_years_excl_0
        self.index_range = range(self.nb_pro_forma_years_incl_0)
        self.index_range_from_1 = range(1, self.nb_pro_forma_years_incl_0)

        # list all Input & Output attributes & symbols, and set model structure
        self.input_attrs = []
        self.output_attrs = []
        self.set_model_structure()

        # gather all Input symbols and set their default values
        self.input_symbols = []
        self.input_defaults = {}
        for input_attr in self.input_attrs:
            a = getattr(self, '%s___input' % input_attr)
            if isinstance(a, (list, tuple)):
                if (not isinstance(a[0], Symbol)) and isnan(a[0]):
                    for i in self.index_range_from_1:
                        self.input_symbols.append(a[i])
                        self.input_defaults[a[i].name] = -1.
                else:
                    for i in self.index_range:
                        self.input_symbols.append(a[i])
                        self.input_defaults[a[i].name] = 0.
            else:
                self.input_symbols.append(a)
                self.input_defaults[a.name] = 0.

        # compile Outputs if so required
        self.compile = compile
        if compile:

            def format_time_delta(time_delta):
                time_delta_str = str(time_delta)
                return time_delta_str[:time_delta_str.index('.')]

            print('Compiling:')
            tic_0 = datetime.now()
            for output in self.output_attrs:
                print('    %s... ' % output, end='')
                a = getattr(self, output)
                tic = datetime.now()
                if isinstance(a, (list, tuple)):
                    if (not isinstance(a[0], Expr)) and isnan(a[0]):
                        setattr(
                            self, output,
                            [nan] + [theano_function(self.input_symbols, [a[i]]) for i in self.index_range_from_1])
                    else:
                        setattr(
                            self, output,
                            [theano_function(self.input_symbols, [a[i]]) for i in self.index_range])
                else:
                    setattr(self, output, theano_function(self.input_symbols, [a]))
                toc = datetime.now()
                print('done after %s (%s so far)' % (format_time_delta(toc - tic), format_time_delta(toc - tic_0)))
            print('done after %s' % format_time_delta(toc - tic_0))

    def set_model_structure(self):
        pass

    def __call__(self, outputs=None, append_to_results_data_frame=None, **kwargs):

        if not outputs:
            outputs = self.output_attrs

        inputs = self.input_defaults.copy()
        for k, v in kwargs.items():
            attr = '%s___input' % k
            if hasattr(self, attr):
                a = getattr(self, attr)
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
        if isinstance(append_to_results_data_frame, DataFrame):
            df = append_to_results_data_frame
        else:
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
                    if output in ('TV', 'TV_RevenueMultiple', 'TV_EBITMultiple', 'ITS_TV'):
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


class UnlevValModel(ValModel):
    def __init__(self, venture_name='', year_0=0, nb_pro_forma_years_excl_0=1, val_all_years=False, compile=True):
        self.val_all_years = val_all_years
        ValModel.__init__(
            self,
            venture_name=venture_name,
            year_0=year_0,
            nb_pro_forma_years_excl_0=nb_pro_forma_years_excl_0,
            compile=compile)

    def set_model_structure(self):

        # model Revenue
        self.Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'Revenue___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.RevenueGrowth___input = \
            (nan,) + \
            symbols(
                self.venture_name_prefix +
                'RevenueGrowth___%d:%d' % (self.year_0 + 1, self.final_pro_forma_year + 1))

        self.Revenue = [self.Revenue___input[0]]
        for i in self.index_range_from_1:
            self.Revenue.append(
                Piecewise(
                    ((1. + self.RevenueGrowth___input[i]) * self.Revenue[-1],
                     Eq(self.Revenue___input[i], 0.)),
                    (self.Revenue___input[i],
                     True)))

        self.RevenueChange = \
            [nan] + \
            [self.Revenue[i] - self.Revenue[i - 1]
             for i in self.index_range_from_1]

        self.RevenueGrowth = \
            [nan] + \
            [Piecewise(
                (self.RevenueChange[i] / self.Revenue[i - 1] - 1.,
                 And(self.Revenue[i - 1] > 0., self.Revenue[i] > 0.)),
                (And(self.Revenue[i - 1] > 0., self.Revenue[i] > 0.),
                 True))
             for i in self.index_range_from_1]

        # model OpEx
        self.OpEx___input = \
            symbols(
                self.venture_name_prefix +
                'OpEx___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.OpEx = self.OpEx___input

        self.OpEx_over_Revenue = \
            [self.OpEx[i] / self.Revenue[i]
             for i in self.index_range]

        self.OpExGrowth = \
            [nan] + \
            [Piecewise(
                (self.OpEx[i] / self.OpEx[i - 1] - 1.,
                 And(self.OpEx[i - 1] > 0., self.OpEx[i] > 0.)),
                (And(self.OpEx[i - 1] > 0., self.OpEx[i] > 0.),
                 True))
             for i in self.index_range_from_1]

        # model EBIT
        self.EBIT___input = \
            symbols(
                self.venture_name_prefix +
                'EBIT___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.EBITMargin___input = \
            symbols(
                self.venture_name_prefix +
                'EBITMargin___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.EBIT = \
            [Piecewise(
                (Piecewise(
                    (self.EBITMargin___input[i] * self.Revenue[i],
                     Eq(self.OpEx[i], 0.)),
                    (self.Revenue[i] - self.OpEx[i],
                     True)),
                 Eq(self.EBIT___input[i], 0.)),
                (self.EBIT___input[i],
                 True))
             for i in self.index_range]

        self.EBITMargin = \
            [self.EBIT[i] / self.Revenue[i]
             for i in self.index_range]

        self.EBITGrowth = \
            [nan] + \
            [Piecewise(
                (self.EBIT[i] / self.EBIT[i - 1] - 1.,
                 And(self.EBIT[i - 1] > 0., self.EBIT[i] > 0.)),
                (And(self.EBIT[i - 1] > 0., self.EBIT[i] > 0.),
                 True))
             for i in self.index_range_from_1]

        # model EBIAT
        self.CorpTaxRate___input = \
            Symbol(
                self.venture_name_prefix +
                'CorpTaxRate')

        self.EBIAT = \
            map(lambda x:
                Piecewise(
                    ((1. - self.CorpTaxRate___input) * x,
                     x > 0),
                    (x,
                     True)),
                self.EBIT)

        # model CLOSING Fixed Assets NET of cumulative Depreciation
        self.FA___input = \
            symbols(
                self.venture_name_prefix +
                'FA___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.FA_over_Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'FA_over_Revenue___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.FAGrowth___input = \
            (nan,) + \
            symbols(
                self.venture_name_prefix +
                'FAGrowth___%d:%d' % (self.year_0 + 1, self.final_pro_forma_year + 1))

        self.FA = [self.FA___input[0]]
        for i in self.index_range_from_1:
            self.FA.append(
                Piecewise(
                    (Piecewise(
                        ((1. + self.FAGrowth___input[i]) * self.FA[-1],
                         Eq(self.FA_over_Revenue___input[i], 0.)),
                        (self.FA_over_Revenue___input[i] * self.Revenue[i],
                         True)),
                     Eq(self.FA___input[i], 0.)),
                    (self.FA___input[i],
                     True)))

        self.FA_over_Revenue = \
            [self.FA[i] / self.Revenue[i]
             for i in self.index_range]

        self.FAGrowth = \
            [nan] + \
            [Piecewise(
                (self.FA[i] / self.FA[i - 1] - 1.,
                 And(self.FA[i - 1] > 0., self.FA[i] > 0.)),
                (And(self.FA[i - 1] > 0., self.FA[i] > 0.),
                 True))
             for i in self.index_range_from_1]

        # model Depreciation
        self.Depreciation___input = \
            symbols(
                self.venture_name_prefix +
                'Depreciation___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.Depreciation_over_prevFA___input = \
            Symbol(
                self.venture_name_prefix +
                'Depreciation_over_prevFA')

        self.Depreciation = \
            [self.Depreciation___input[0]] + \
            [Piecewise(
                (self.Depreciation_over_prevFA___input * self.FA[i - 1],
                 Eq(self.Depreciation___input[i], 0.)),
                (self.Depreciation___input[i],
                 True))
             for i in self.index_range_from_1]

        self.Depreciation_over_prevFA = \
            [nan] + \
            [self.Depreciation[i] / self.FA[i - 1]
             for i in self.index_range_from_1]

        # model Capital Expenditure
        self.CapEx___input = \
            symbols(
                self.venture_name_prefix +
                'CapEx___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.CapEx_over_Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'CapEx_over_Revenue___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.CapEx_over_RevenueChange___input = \
            Symbol(
                self.venture_name_prefix +
                'CapEx_over_RevenueChange')

        self.CapExGrowth___input = \
            (nan,) + \
            symbols(
                self.venture_name_prefix +
                'CapExGrowth___%d:%d' % (self.year_0 + 1, self.final_pro_forma_year + 1))

        self.CapEx = [self.CapEx___input[0]]
        for i in self.index_range_from_1:
            self.CapEx.append(
                Piecewise(
                    (Piecewise(
                        (Piecewise(
                            (Piecewise(
                                (self.FA[i] + self.Depreciation[i] - self.FA[i - 1],
                                 Eq(self.CapExGrowth___input[i], -1.)),
                                ((1. + self.CapExGrowth___input[i]) * self.CapEx[-1],
                                 True)),
                             Eq(self.CapEx_over_RevenueChange___input, 0.)),
                            (self.CapEx_over_RevenueChange___input * self.RevenueChange[i],
                             True)),
                         Eq(self.CapEx_over_Revenue___input[i], 0.)),
                        (self.CapEx_over_Revenue___input[i] * self.Revenue[i],
                         True)),
                     Eq(self.CapEx___input[i], 0.)),
                    (self.CapEx___input[i],
                     True)))

        self.CapEx_over_Revenue = \
            [self.CapEx[i] / self.Revenue[i]
             for i in self.index_range]

        self.CapEx_over_RevenueChange = \
            [nan] + \
            [self.CapEx[i] / self.RevenueChange[i]
             for i in self.index_range_from_1]

        self.CapExGrowth = \
            [nan] + \
            [Piecewise(
                (self.CapEx[i] / self.CapEx[i - 1] - 1.,
                 And(self.CapEx[i - 1] > 0., self.CapEx[i] > 0.)),
                (And(self.CapEx[i - 1] > 0., self.CapEx[i] > 0.),
                 True))
             for i in self.index_range_from_1]

        # model Net Working Capital and its change
        self.NWC___input = \
            symbols(
                self.venture_name_prefix +
                'NWC___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.NWC_over_Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'NWC_over_Revenue___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.NWCGrowth___input = \
            (nan,) + \
            symbols(
                self.venture_name_prefix +
                'NWCGrowth___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.NWC = [self.NWC___input[0]]
        for i in self.index_range_from_1:
            self.NWC.append(
                Piecewise(
                    (Piecewise(
                        ((1. + self.NWCGrowth___input[i]) * self.NWC[-1],
                         Eq(self.NWC_over_Revenue___input[i], 0.)),
                        (self.NWC_over_Revenue___input[i] * self.Revenue[i], True)),
                     Eq(self.NWC___input[i], 0.)),
                    (self.NWC___input[i],
                     True)))

        self.NWC_over_Revenue = \
            [self.NWC[i] / self.Revenue[i]
             for i in self.index_range]

        self.NWCGrowth = \
            [nan] + \
            [Piecewise(
                (self.NWC[i] / self.NWC[i - 1] - 1.,
                 And(self.NWC[i - 1] > 0., self.NWC[i] > 0.)),
                (And(self.NWC[i - 1] > 0., self.NWC[i] > 0.),
                 True))
             for i in self.index_range_from_1]

        self.NWCChange___input = \
            symbols(
                self.venture_name_prefix +
                'NWCChange___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.NWCChange_over_Revenue___input = \
            symbols(
                self.venture_name_prefix +
                'NWCChange_over_Revenue___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.NWCChange_over_RevenueChange___input = \
            Symbol(
                self.venture_name_prefix +
                'NWCChange_over_RevenueChange')

        self.NWCChange = [self.NWCChange___input[0]]
        for i in self.index_range_from_1:
            self.NWCChange.append(
                Piecewise(
                    (Piecewise(
                        (Piecewise(
                            (self.NWC[i] - self.NWC[i - 1],
                             Eq(self.NWCChange_over_RevenueChange___input, 0.)),
                            (self.NWCChange_over_RevenueChange___input * self.RevenueChange[i],
                             True)),
                         Eq(self.NWCChange_over_Revenue___input[i], 0.)),
                        (self.NWCChange_over_Revenue___input[i] * self.Revenue[i],
                         True)),
                     Eq(self.NWCChange___input[i], 0.)),
                    (self.NWCChange___input[i],
                     True)))

        self.NWCChange_over_Revenue = \
            [self.NWCChange[i] / self.Revenue[i]
             for i in self.index_range]

        self.NWCChange_over_RevenueChange = \
            [nan] + \
            [self.NWCChange[i] / self.RevenueChange[i]
             for i in self.index_range_from_1]

        # model Free Cash Flows before Terminal Value
        self.FCF = \
            [self.EBIAT[i] + self.Depreciation[i] - self.CapEx[i] - self.NWCChange[i]
             for i in self.index_range]

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

        self.PublicMarketPremium___expr = \
            Piecewise(
                (self.PublicMarketReturn___input - self.RiskFreeRate___input,
                 Eq(self.PublicMarketPremium___input, 0.)),
                (self.PublicMarketPremium___input,
                 True))
        self.PublicMarketPremium = self.PublicMarketPremium___expr

        self.InvestmentManagerFeePremium___input = \
            Symbol(
                self.venture_name_prefix +
                'InvestmentManagerFeePremium')

        self.ProFormaPeriodBeta___input = \
            Symbol(
                self.venture_name_prefix +
                'ProFormaPeriodBeta')

        self.ProFormaPeriodAssetDiscountRate___input = \
            Symbol(
                self.venture_name_prefix +
                'ProFormaPeriodAssetDiscountRate')

        self.ProFormaPeriodAssetDiscountRate___expr = \
            Piecewise(
                (self.RiskFreeRate___input + self.ProFormaPeriodBeta___input * self.PublicMarketPremium,
                 Eq(self.ProFormaPeriodAssetDiscountRate___input, 0.)),
                (self.ProFormaPeriodAssetDiscountRate___input,
                 True))
        self.ProFormaPeriodAssetDiscountRate = self.ProFormaPeriodAssetDiscountRate___expr

        self.ProFormaPeriodDiscountRate___input = \
            Symbol(
                self.venture_name_prefix +
                'ProFormaPeriodDiscountRate')

        self.ProFormaPeriodDiscountRate = \
            Piecewise(
                (self.ProFormaPeriodAssetDiscountRate + self.InvestmentManagerFeePremium___input,
                 Eq(self.ProFormaPeriodDiscountRate___input, 0.)),
                (self.ProFormaPeriodDiscountRate___input,
                 True))

        self.StabilizedBeta___input = \
            Symbol(
                self.venture_name_prefix +
                'StabilizedBeta')

        self.StabilizedDiscountRate___input = \
            Symbol(
                self.venture_name_prefix +
                'StabilizedDiscountRate')

        self.StabilizedDiscountRate___expr = \
            Piecewise(
                (Piecewise(
                    (self.ProFormaPeriodDiscountRate,
                     Eq(self.StabilizedBeta___input, 0.)),
                    (self.RiskFreeRate___input + self.StabilizedBeta___input * self.PublicMarketPremium,
                     True)),
                 Eq(self.StabilizedDiscountRate___input, 0.)),
                (self.StabilizedDiscountRate___input,
                 True))
        self.StabilizedDiscountRate = self.StabilizedDiscountRate___expr


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
            Piecewise(
                (terminal_value(
                    terminal_cash_flow=self.FCF[-1],
                    long_term_discount_rate=self.StabilizedDiscountRate,
                    long_term_growth_rate=self.LongTermGrowthRate___input),
                 Eq(self.TV_RevenueMultiple___input, 0.)),
                (self.TV_RevenueMultiple___input * self.Revenue[-1],
                 True))

        self.TV_RevenueMultiple = \
            self.TV / self.Revenue[-1]

        self.TV_EBITMultiple = \
            Piecewise(
                (self.TV / self.EBIT[-1], self.EBIT[-1] > 0),
                (0., True))

        # model Unlevered Valuation
        FCF = [0.] + self.FCF[1:]

        if self.val_all_years:

            self.Val_of_FCF = \
                [net_present_value(
                    cash_flows=FCF[i:],
                    discount_rate=self.ProFormaPeriodDiscountRate)
                 for i in self.index_range]

            self.Val_of_TV = \
                [present_value(
                    amount=self.TV,
                    discount_rate=self.StabilizedDiscountRate,
                    nb_periods=self.nb_pro_forma_years_excl_0 - i)
                 for i in self.index_range]

            self.Unlev_Val = \
                [self.Val_of_FCF[i] + self.Val_of_TV[i]
                 for i in self.index_range]

        else:

            self.Val_of_FCF = \
                net_present_value(
                    cash_flows=FCF,
                    discount_rate=self.ProFormaPeriodDiscountRate)

            self.Val_of_TV = \
                present_value(
                    amount=self.TV,
                    discount_rate=self.StabilizedDiscountRate,
                    nb_periods=self.nb_pro_forma_years_excl_0)

            self.Unlev_Val = self.Val_of_FCF + self.Val_of_TV

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
             'RiskFreeRate', 'PublicMarketReturn', 'PublicMarketPremium', 'InvestmentManagerFeePremium',
             'ProFormaPeriodBeta', 'ProFormaPeriodAssetDiscountRate', 'ProFormaPeriodDiscountRate',
             'StabilizedBeta', 'StabilizedDiscountRate',
             'LongTermGrowthRate',
             'TV_RevenueMultiple']

        self.output_attrs = \
            ['PublicMarketPremium',
             'ProFormaPeriodAssetDiscountRate', 'ProFormaPeriodDiscountRate', 'StabilizedDiscountRate',
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
             'TV', 'TV_RevenueMultiple', 'TV_EBITMultiple',
             'Unlev_Val'   # skipping Val_of_FCF & Val_of_TV to save compilation time
             ]


class LevValModel(ValModel):
    def __init__(self, unlev_val_model):
        self.unlev_val_model = unlev_val_model
        ValModel.__init__(
            self,
            venture_name=unlev_val_model.venture_name,
            year_0=unlev_val_model.year_0,
            nb_pro_forma_years_excl_0=unlev_val_model.nb_pro_forma_years_excl_0,
            compile=unlev_val_model.compile)

    def set_model_structure(self):

        # get certain Input symbols from the Unlevered Valuation Model
        self.CorpTaxRate___input = self.unlev_val_model.CorpTaxRate___input
        self.RiskFreeRate___input = self.unlev_val_model.RiskFreeRate___input
        self.PublicMarketReturn___input = self.unlev_val_model.PublicMarketReturn___input
        self.PublicMarketPremium___input = self.unlev_val_model.PublicMarketPremium___input
        self.InvestmentManagerFeePremium___input = self.unlev_val_model.InvestmentManagerFeePremium___input
        self.ProFormaPeriodBeta___input = self.unlev_val_model.ProFormaPeriodBeta___input
        self.ProFormaPeriodAssetDiscountRate___input = self.unlev_val_model.ProFormaPeriodAssetDiscountRate___input
        self.ProFormaPeriodDiscountRate___input = self.unlev_val_model.ProFormaPeriodDiscountRate___input
        self.StabilizedBeta___input = self.unlev_val_model.StabilizedBeta___input
        self.StabilizedDiscountRate___input = self.unlev_val_model.StabilizedDiscountRate___input

        # model Unlevered Valuation
        if self.unlev_val_model.val_all_years:
            self.Unlev_Val___input = \
                symbols(
                    'Unlev_Val___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))
        else:
            self.Unlev_Val___input = \
                Symbol('Unlev_Val')

        self.Unlev_Val = self.Unlev_Val___input

        # model Debt-to-Equity ("D / E") Ratios
        self.DERatio___input = \
            Symbol(
                self.venture_name_prefix +
                'DERatio')

        self.ProFormaPeriodDERatio___input = \
            Symbol(
                self.venture_name_prefix +
                'ProFormaPeriodDERatio')

        pro_forma_period_d_e_ratio = \
            Piecewise(
                (self.DERatio___input,
                 Eq(self.ProFormaPeriodDERatio___input, 0.)),
                (self.ProFormaPeriodDERatio___input,
                 True))

        self.DERatios = \
            self.nb_pro_forma_years_excl_0 * [pro_forma_period_d_e_ratio] + [self.DERatio___input]

        # model Debt
        self.Debt___input = \
            symbols(
                self.venture_name_prefix +
                'Debt___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        if self.unlev_val_model.val_all_years:
            self.Debt = \
                [Piecewise(
                    ((1. - 1. / (1. + self.DERatios[i])) * self.Unlev_Val[i],
                     Eq(self.Debt___input[i], 0.)),
                    (self.Debt___input[i],
                     True))
                 for i in self.index_range]
        else:
            self.Debt = self.Debt___input

        # model Interest Rates
        self.InterestRate___input = \
            Symbol(
                self.venture_name_prefix +
                'InterestRate')

        self.ProFormaPeriodInterestRate___input = \
            Symbol(
                self.venture_name_prefix +
                'ProFormaPeriodInterestRate')

        pro_forma_period_interest_rate = \
            Piecewise(
                (self.InterestRate___input,
                 Eq(self.ProFormaPeriodInterestRate___input, 0.)),
                (self.ProFormaPeriodInterestRate___input,
                 True))

        self.InterestRates = \
            self.nb_pro_forma_years_excl_0 * [pro_forma_period_interest_rate] + [self.InterestRate___input]

        self.InterestRates___input = \
            symbols(
                self.venture_name_prefix +
                'InterestRates___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.InterestRates = \
            [Piecewise(
                (self.InterestRates[i],
                 Eq(self.InterestRates___input[i], 0.)),
                (self.InterestRates___input[i],
                 True))
             for i in self.index_range]

        # model Interest Expense & InterestTaxShield
        self.InterestExpense___input = \
            symbols(
                self.venture_name_prefix +
                'InterestExpense___%d:%d' % (self.year_0, self.final_pro_forma_year + 1))

        self.InterestExpense = \
            [Piecewise(
                (self.InterestRates[i] * self.Debt[i],
                 Eq(self.InterestExpense___input[i], 0.)),
                (self.InterestExpense___input[i],
                 True))
             for i in self.index_range]

        self.ITS = \
            map(lambda x: self.CorpTaxRate___input * x,
                self.InterestExpense)

        # model Interest Tax Shield (ITS) Discount Rate
        self.DebtBeta___input = \
            Symbol(
                self.venture_name_prefix +
                'DebtBeta')

        self.DebtDiscountRate___input = \
            Symbol(
                self.venture_name_prefix +
                'DebtDiscountRate')

        self.DebtDiscountRate = \
            Piecewise(
                (Piecewise(
                    (self.DebtBeta___input + self.DebtDiscountRate___input,
                        # use this expression because '0.' throws SymPy / Theano bug
                     Eq(self.DebtBeta___input, 0.)),
                    (self.RiskFreeRate___input +
                        self.DebtBeta___input * self.unlev_val_model.PublicMarketPremium___expr,
                     True)),
                 Eq(self.DebtDiscountRate___input, 0.)),
                (self.DebtDiscountRate___input,
                 True))

        self.ProFormaPeriodITSDiscountRate = \
            Piecewise(
                (self.unlev_val_model.ProFormaPeriodAssetDiscountRate___expr,
                 Eq(self.DebtDiscountRate, 0.)),
                (self.DebtDiscountRate,
                 True))

        self.StabilizedITSDiscountRate = \
            Piecewise(
                (self.unlev_val_model.StabilizedDiscountRate___expr,
                 Eq(self.DebtDiscountRate, 0.)),
                (self.DebtDiscountRate,
                 True))

        # model Terminal Value of Interest Tax Shield
        self.ITS_TV = \
            terminal_value(
                terminal_cash_flow=self.ITS[-1],
                long_term_discount_rate=self.StabilizedITSDiscountRate,
                long_term_growth_rate=0.)

        # model Valuation of Interest Tax Shield, and Levered Valuation
        ITS = [0.] + self.ITS[1:]

        if self.unlev_val_model.val_all_years:

            self.Val_of_ITS = \
                [net_present_value(
                    cash_flows=ITS[i:],
                    discount_rate=self.ProFormaPeriodITSDiscountRate)
                 for i in self.index_range]

            self.Val_of_ITS_TV = \
                [present_value(
                    amount=self.ITS_TV,
                    discount_rate=self.StabilizedITSDiscountRate,
                    nb_periods=self.nb_pro_forma_years_excl_0 - i)
                 for i in self.index_range]

            self.Val_of_ITS_incl_TV = \
                [self.Val_of_ITS[i] + self.Val_of_ITS_TV[i]
                 for i in self.index_range]

            self.Lev_Val = \
                [self.Unlev_Val[i] + self.Val_of_ITS_incl_TV[i]
                 for i in self.index_range]

        else:

            self.Val_of_ITS = \
                net_present_value(
                    cash_flows=ITS,
                    discount_rate=self.ProFormaPeriodITSDiscountRate)

            self.Val_of_ITS_TV = \
                present_value(
                    amount=self.ITS_TV,
                    discount_rate=self.StabilizedITSDiscountRate,
                    nb_periods=self.nb_pro_forma_years_excl_0)

            self.Val_of_ITS_incl_TV = self.Val_of_ITS + self.Val_of_ITS_TV

            self.Lev_Val = self.Unlev_Val + self.Val_of_ITS_incl_TV

        self.input_attrs = \
            ['Unlev_Val',
             'CorpTaxRate',
             'RiskFreeRate', 'PublicMarketReturn', 'PublicMarketPremium', 'InvestmentManagerFeePremium',
             'ProFormaPeriodBeta', 'ProFormaPeriodAssetDiscountRate', 'ProFormaPeriodDiscountRate',
             'StabilizedBeta', 'StabilizedDiscountRate',
             'DERatio', 'ProFormaPeriodDERatio', 'Debt',
             'InterestRate', 'ProFormaPeriodInterestRate', 'InterestRates',
             'InterestExpense',
             'DebtBeta', 'DebtDiscountRate']

        self.output_attrs = \
            ['ProFormaPeriodITSDiscountRate', 'StabilizedITSDiscountRate',
             'Unlev_Val',
             'DERatios', 'Debt',
             'InterestRates',
             'InterestExpense', 'ITS',
             'ITS_TV',
             'Val_of_ITS_incl_TV',   # skipping Val_of_ITS & Val_of_ITS_TV to save compilation time
             'Lev_Val']
