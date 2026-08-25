#!/usr/bin/env python3
"""Debug auth module."""
import sys
sys.path.insert(0, '.')

# Clear cache
for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

from src.auth.password import hash_password, verify_password, _b64url_decode
import hashlib, hmac

h = hash_password('MyPass123')
print('hash repr:', repr(h))
print('hash len:', len(h))

salt_b64, dk_b64 = h.split('.')
print(f'salt_b64={salt_b64!r} len={len(salt_b64)}')
print(f'dk_b64={dk_b64!r} len={len(dk_b64)}')

# Decode manually
salt = _b64url_decode(salt_b64)
print(f'salt decoded: {len(salt)} bytes')

# Check dk decode
import base64
std = dk_b64.replace('-', '+').replace('_', '/')
padding = (4 - len(dk_b64) % 4) % 4
std_padded = std + '=' * padding
print(f'dk std: {std!r} pad={padding}')
try:
    dk_decoded = base64.b64decode(std_padded)
    print(f'dk decoded: {len(dk_decoded)} bytes')
except Exception as e:
    print(f'dk decode FAIL: {e}')

# Try module decode
try:
    dk_mod = _b64url_decode(dk_b64)
    print(f'dk module decode: {len(dk_mod)} bytes')
except Exception as e:
    print(f'dk module decode FAIL: {e}')

# Compute expected
dk_expected = hashlib.pbkdf2_hmac('sha256', b'MyPass123', salt, 12)
print(f'dk expected: {len(dk_expected)} bytes')
print(f'match: {dk_expected.hex()[:20]}...')
if 'dk_decoded' in dir():
    print(f'decoded match: {dk_decoded.hex()[:20]}...')

# Try verify
print(f'verify_password: {verify_password("MyPass123", h)}')
