#!/usr/bin/env python3
"""Debug hash chars."""
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

# Show each char with index
print('\nChar-by-char:')
for i, c in enumerate(h):
    print(f'  [{i:2d}] {c!r} (ord={ord(c)})')

# Now test: encode exact 32 bytes and compare
dk = hashlib.pbkdf2_hmac('sha256', b'MyPass123', b'\x00' * 16, 12)
enc = _b64url_encode(dk)
print(f'\nencode(32 bytes) -> {len(enc)} chars: {enc!r}')

# Test: encode 32 zero bytes
dk2 = bytes(32)
enc2 = _b64url_encode(dk2)
print(f'encode(32 zeros) -> {len(enc2)} chars: {enc2!r}')
