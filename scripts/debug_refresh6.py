#!/usr/bin/env python3
"""Debug refresh token - instrument the method."""
import sys
sys.path.insert(0, '.')

for mod in list(sys.modules.keys()):
    if 'auth' in mod:
        del sys.modules[mod]

# Read and patch service.py source
import src.auth.service as svc_module
import inspect

# Print the actual source of refresh_token
print("=== Service.refresh_token source ===")
print(inspect.getsource(svc_module.SessionManager.refresh_token))
