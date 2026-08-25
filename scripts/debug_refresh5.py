#!/usr/bin/env python3
"""Debug refresh token - trace the method."""
import sys
sys.path.insert(0, '.')

for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

# Monkey-patch to trace
from src.auth import service as svc
orig_refresh = svc.SessionManager.refresh_token

def traced_refresh(self, refresh_token):
    print(f'  [trace] refresh_token called')
    print(f'  [trace] input token: {refresh_token[:50]}...')
    print(f'  [trace] _user_tokens before: {dict(self._user_tokens)}')

    # Call original
    result = orig_refresh(self, refresh_token)

    print(f'  [trace] _user_tokens after: {dict(self._user_tokens)}')
    print(f'  [trace] returned new_refresh: {result[1][:50]}...')
    return result

svc.SessionManager.refresh_token = traced_refresh

from src.auth.service import SessionManager

mgr = SessionManager()
mgr.register('test', 'test@test.com', 'Test1234')
session = mgr.login('test', 'Test1234')
print(f'Initial refresh_token: {session.refresh_token[:50]}...')
print()
new_access, new_refresh = mgr.refresh_token(session.refresh_token)
print()
print(f'After refresh:')
print(f'  same token: {session.refresh_token == new_refresh}')
