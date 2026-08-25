#!/usr/bin/env python3
"""Test f-string behavior with $."""
import sys
print(f'Python version: {sys.version}')

x = 'salt'
y = 'dk'

# Test different f-string patterns
print(f"f'{{x}}.${{y}}' = {f'{x}.${y}'!r}")
print(f"f'{{x}}.{{y}}' = {f'{x}.{y}'!r}")
print(f"'{x}.' + '{y}' = {(x + '.' + y)!r}")

# The bug: in Python 3.12+, ${...} in f-strings is parsed differently
# f'{x}.${y}' is interpreted as: {x} + '.' + ${y}
# But ${y} in f-strings is treated as a special syntax

# Let's verify
result = f'{x}.${y}'
print(f'\nResult: {result!r}')
print(f'Expected: "salt.dk"')
print(f'Match: {result == "salt.dk"}')

# Fix: use string concatenation or % formatting
fixed = f'{x}.{y}'
print(f'Fixed: {fixed!r}')
