#!/usr/bin/env python3
"""Debug hash format."""
import sys
sys.path.insert(0, '.')

for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

from src.auth.password import hash_password, _b64url_encode
import hashlib, os, base64

h = hash_password('MyPass123')
print(f'hash: {h!r}')
print(f'hash len: {len(h)}')

# The format is: salt.$dk where . is the separator
# salt is 22 chars, dk is 43 chars
# But we're seeing a $ at position 23

# Let's check: is the format actually salt + '.' + dk?
# Or is it salt + '.' + '$' + dk_without_dollar?
parts = h.split('.')
print(f'split on ".": {len(parts)} parts')
for i, p in enumerate(parts):
    print(f'  part[{i}] len={len(p)}: {p!r}')

# Expected: 22 chars salt, 43 chars dk (total 66 with dot)
# Actual: 22 chars salt, 44 chars dk (total 67 with dot)
# The extra char is $ at position 23

# Let's check: what if the format is actually:
# salt + '.' + dk where dk INCLUDES a $ at the start?
# That would mean _b64url_encode(dk) produces a string starting with $
# But we showed that _b64url_encode(32 bytes) does NOT produce $

# So the $ must be coming from somewhere else.
# Let's check the actual f-string:
# f"{_b64url_encode(salt)}.${_b64url_encode(dk)}"
# This produces: salt + '.' + dk
# The $ is part of the f-string syntax, not literal output!

# Wait - in an f-string, ${...} is NOT a special syntax in Python.
# Python f-strings use {expression} for interpolation.
# ${...} would be: literal $ followed by {expression}

# So f"{salt}.${dk}" = salt + "." + dk  (the $ is literal!)
# That means the format is: salt + "." + dk (where dot is literal)
# NOT: salt + "$." + dk

# So the hash should be: salt + '.' + dk = 22 + 1 + 43 = 66 chars
# But we see 67 chars with a $ after the dot.

# This means the f-string is producing: salt + '.' + '$' + dk
# Which means the f-string is: f"{_b64url_encode(salt)}.${_b64url_encode(dk)}"
# In Python f-strings: ${...} is NOT special, but let's check...

# Actually in Python 3.12+, f-strings have a new feature:
# ${expression} is the SAME as {expression} (both do interpolation)
# So f"${_b64url_encode(dk)}" = "$" + _b64url_encode(dk)

# That means: f"{salt}.${dk}" = salt + "." + "$" + dk = salt + ".$" + dk
# Which is 22 + 1 + 1 + 43 = 67 chars!
# And dk_b64 starts with $ because the $ is BEFORE dk in the f-string!

print('\n--- Analysis ---')
print('In Python 3.12+, ${expr} in f-strings is equivalent to {expr}')
print('So f"{salt}.${dk}" produces: salt + "." + "$" + dk')
print('The $ is literal text BEFORE dk, not part of dk!')
print()
print('Fix: change separator from ".$" to just "."')
print('Or change the f-string to avoid ${...} pattern')
