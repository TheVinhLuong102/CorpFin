

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
