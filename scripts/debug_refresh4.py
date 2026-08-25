#!/usr/bin/env python3
"""Debug refresh token removal - step by step."""
import sys
sys.path.insert(0, '.')

for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

from src.auth.service import SessionManager
from src.auth.jwt import decode_token

mgr = SessionManager()
mgr.register('iris', 'iris@test.com', 'Iris1234')
session = mgr.login('iris', 'Iris1234')

old_token = session.refresh_token
print(f'Before refresh:')
print(f'  _user_tokens[iris] = {mgr._user_tokens.get("iris", [])}')
print(f'  old_token in list: {old_token in mgr._user_tokens.get("iris", [])}')

# Manually do what refresh_token does
username = 'iris'
tokens = mgr._user_tokens.get(username, [])
print(f'\nManual check:')
print(f'  tokens = {tokens}')
print(f'  old_token in tokens: {old_token in tokens}')

# Remove
if old_token in tokens:
    tokens.remove(old_token)
    print(f'  After remove: {tokens}')
else:
    print(f'  NOT FOUND in tokens!')

print(f'\n_user_tokens after manual remove: {mgr._user_tokens.get("iris", [])}')

# Now test the actual method
mgr2 = SessionManager()
mgr2.register('test', 'test@test.com', 'Test1234')
s2 = mgr2.login('test', 'Test1234')
print(f'\n--- mgr2 ---')
print(f'Before: {mgr2._user_tokens}')
new_acc, new_ref = mgr2.refresh_token(s2.refresh_token)
print(f'After: {mgr2._user_tokens}')
print(f's2.refresh_token in list: {s2.refresh_token in mgr2._user_tokens.get("test", [])}')
print(f'new_ref in list: {new_ref in mgr2._user_tokens.get("test", [])}')
