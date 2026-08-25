#!/usr/bin/env python3
"""Debug refresh token - why same token?"""
import sys
sys.path.insert(0, '.')

for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

from src.auth.jwt import encode_token, encode_refresh_token, decode_token
import time

# Test: do encode_token calls produce different tokens?
t1 = encode_token({"sub": "test", "type": "refresh"})
t2 = encode_token({"sub": "test", "type": "refresh"})
print(f't1: {t1[:60]}...')
print(f't2: {t2[:60]}...')
print(f'same: {t1 == t2}')

# Decode both
p1 = decode_token(t1)
p2 = decode_token(t2)
print(f'p1 iat={p1["iat"]} exp={p1["exp"]}')
print(f'p2 iat={p2["iat"]} exp={p2["exp"]}')
print(f'same iat: {p1["iat"] == p2["iat"]}')

# Test with time.sleep
time.sleep(1.1)
t3 = encode_token({"sub": "test", "type": "refresh"})
p3 = decode_token(t3)
print(f't3 iat={p3["iat"]} (after sleep)')
print(f't2 == t3: {t2 == t3}')
