from sympy.matrices import Determinant, Matrix


def terminal_value(
        cash_flows=Matrix([0.]),
        long_term_discount_rate=0.,
        long_term_growth_rate=0.):
    m, n = cash_flows.shape
    if m == 1:
        filter_vector = Matrix((n - 1) * [0] + [1])
        tv = Determinant(cash_flows * filter_vector)
    elif n == 1:
        filter_vector = Matrix([(m - 1) * [0] + [1]])
        tv = Determinant(filter_vector * cash_flows)
    return (1 + long_term_growth_rate) * tv / (long_term_discount_rate - long_term_growth_rate)


def present_value(amount=0., discount_rate=0., nb_periods=0.):
    return amount / ((1 + discount_rate) ** nb_periods)


def net_present_value(
        cash_flows=Matrix([0.]),
        discount_rate=0.):
    m, n = cash_flows.shape
    discount_rate_plus_1 = discount_rate + 1
    if m == 1:
        discount_vector = Matrix([discount_rate_plus_1 ** -i for i in range(n)])
        return Determinant(cash_flows * discount_vector)
    elif n == 1:
        discount_vector = Matrix([[discount_rate_plus_1 ** -i for i in range(m)]])
        return Determinant(discount_vector * cash_flows)
