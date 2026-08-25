#!/usr/bin/env python3
"""Debug refresh token."""
import sys
sys.path.insert(0, '.')

for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

from src.auth.service import SessionManager
from src.auth.exceptions import TokenError

mgr = SessionManager()
mgr.register('iris', 'iris@test.com', 'Iris1234')
session = mgr.login('iris', 'Iris1234')

print(f'refresh_token: {session.refresh_token!r}')
print(f'refresh_token len: {len(session.refresh_token)}')

# Decode to check
from src.auth.jwt import decode_token
payload = decode_token(session.refresh_token)
print(f'decoded: {payload}')
print(f'type: {payload.get("type")}')

# Refresh
new_access, new_refresh = mgr.refresh_token(session.refresh_token)
print(f'new_access: {new_access!r}')
print(f'new_refresh: {new_refresh!r}')

# Check if old token still works
try:
    old_payload = decode_token(session.refresh_token)
    print(f'old token still valid: {old_payload}')
except Exception as e:
    print(f'old token invalid: {e}')

# Try to refresh with old token
try:
    mgr.refresh_token(session.refresh_token)
    print('OLD TOKEN STILL WORKS - BUG!')
except TokenError as e:
    print(f'OLD TOKEN REJECTED: {e}')
except Exception as e:
    print(f'OLD TOKEN ERROR: {type(e).__name__}: {e}')
