#!/usr/bin/env python3
"""Debug refresh token - detailed."""
import sys
sys.path.insert(0, '.')

for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

from src.auth.service import SessionManager

mgr = SessionManager()
mgr.register('iris', 'iris@test.com', 'Iris1234')
session = mgr.login('iris', 'Iris1234')

print(f'refresh_token: {session.refresh_token[:40]}...')
print(f'_user_tokens before refresh: {mgr._user_tokens}')

# Refresh
new_access, new_refresh = mgr.refresh_token(session.refresh_token)
print(f'new_refresh: {new_refresh[:40]}...')
print(f'_user_tokens after refresh: {mgr._user_tokens}')

# Check: are they the same?
print(f'same token: {session.refresh_token == new_refresh}')

# Try to use old token again
try:
    mgr.refresh_token(session.refresh_token)
    print('BUG: old token still works!')
except Exception as e:
    print(f'OK: old token rejected: {e}')
