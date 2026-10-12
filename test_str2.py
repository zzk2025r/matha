# -*- coding: utf-8 -*-
from src.symbolic import Var, Mul, Num, Add, Pow

# Test complex expression
m = Var('m')
a = Var('a')
v = Var('v')
expr = Add(Mul(Var('m'), Var('a')), Mul(Mul(Var('m'), Num(0.5)), Pow(Var('v'), Num(2))))
print('Complex:', expr)

# Test with Chinese variables
radius = Var('半径')
mul2 = Mul(Num(2), radius)
print('Chinese mul2:', mul2)
add = Add(Mul(Mul(Num(0.5), Pow(radius, Num(2))), Mul(Num(2), radius)), radius)
print('Chinese:', add)