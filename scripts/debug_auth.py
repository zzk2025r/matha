#!/usr/bin/env python3
"""Debug script for auth module."""
import sys
sys.path.insert(0, '.')

import base64, hashlib, hmac as hmac_mod, os

# Inline the exact function logic
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(s: str) -> bytes:
    std = s.replace("-", "+").replace("_", "/")
    padding = (4 - len(s) % 4) % 4
    if padding:
        std += "=" * padding
    return base64.b64decode(std)

def hash_password(password: str, rounds: int = 12) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"{_b64url_encode(salt)}.${_b64url_encode(dk)}"

def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_b64, dk_b64 = password_hash.split(".")
        salt = _b64url_decode(salt_b64)
        expected_dk = _b64url_decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 12)
        print(f"  salt_b64={salt_b64!r} len={len(salt_b64)}")
        print(f"  dk_b64={dk_b64!r} len={len(dk_b64)}")
        print(f"  salt decoded: {len(salt)} bytes")
        print(f"  expected_dk decoded: {len(expected_dk)} bytes")
        print(f"  dk computed: {len(dk)} bytes")
        print(f"  expected_dk hex: {expected_dk.hex()[:20]}...")
        print(f"  dk hex: {dk.hex()[:20]}...")
        print(f"  equal: {expected_dk == dk}")
        return hmac_mod.compare_digest(dk, expected_dk)
    except Exception as e:
        print(f"  Exception: {e}")
        return False

print("Test 1: inline functions")
h = hash_password("MyPass123")
r = verify_password("MyPass123", h)
print(f"  result: {r}")
print()

# Now test with the module
print("Test 2: module import")
for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

from src.auth.password import hash_password as mod_hash, verify_password as mod_verify
h2 = mod_hash("MyPass123")
r2 = mod_verify("MyPass123", h2)
print(f"  result: {r2}")
