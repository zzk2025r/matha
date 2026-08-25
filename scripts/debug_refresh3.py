#!/usr/bin/env python3
"""Debug refresh token removal."""
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
print(f'old_token id: {id(old_token)}')
print(f'old_token[:50]: {old_token[:50]}')

# Check membership
tokens = mgr._user_tokens.get('iris', [])
print(f'tokens list: {len(tokens)} items')
print(f'old_token in tokens: {old_token in tokens}')

# Compare element by element
for i, t in enumerate(tokens):
    print(f'  token[{i}]: {t[:50]}...')
    print(f'  == old_token: {t == old_token}')
    print(f'  id match: {id(t) == id(old_token)}')

# Now call refresh_token with detailed tracing
print('\nCalling refresh_token...')
result = mgr.refresh_token(old_token)
print(f'result: {result}')

# Check after
tokens_after = mgr._user_tokens.get('iris', [])
print(f'tokens after: {len(tokens_after)} items')
for i, t in enumerate(tokens_after):
    print(f'  token[{i}]: {t[:50]}... same as old: {t == old_token}')
