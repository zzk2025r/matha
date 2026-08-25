#!/usr/bin/env python3
"""Test auth hash generation."""
import sys
sys.path.insert(0, '.')

for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

from src.auth.password import hash_password, verify_password, _b64url_encode
import hashlib, os, base64

# Test 1: verify _b64url_encode for 32 bytes
dk = hashlib.pbkdf2_hmac('sha256', b'test', os.urandom(16), 12)
enc = _b64url_encode(dk)
print(f'_b64url_encode(32 bytes) -> {len(enc)} chars')
print(f'  value: {enc!r}')
print(f'  has $: {chr(36) in enc}')

# Test 2: generate hash and check
h = hash_password('MyPass123')
print(f'\nhash: {h!r}')
print(f'hash len: {len(h)}')

salt_b64, dk_b64 = h.split('.')
print(f'salt_b64: {salt_b64!r} len={len(salt_b64)}')
print(f'dk_b64:   {dk_b64!r} len={len(dk_b64)}')

# Test 3: what is the first char of dk_b64?
print(f'\ndk_b64 first char: {dk_b64[0]!r} ord={ord(dk_b64[0])}')

# Test 4: can we decode dk_b64?
import base64 as b64mod
std = dk_b64.replace('-', '+').replace('_', '/')
pad = (4 - len(dk_b64) % 4) % 4
print(f'\nstd: {std!r} len={len(std)} pad={pad}')
if pad:
    std += '=' * pad
try:
    decoded = b64mod.b64decode(std)
    print(f'decoded: {len(decoded)} bytes')
except Exception as e:
    print(f'decode FAIL: {e}')

# Test 5: verify_password
print(f'\nverify_password: {verify_password("MyPass123", h)}')
