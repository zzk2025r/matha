"""从 src/auth 重新生成 matha-auth 包，修正导入路径。"""
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
PKG = ROOT / "packages" / "matha_auth"
SRC = ROOT / "src" / "auth"

PKG.mkdir(parents=True, exist_ok=True)

MODULES = ["models.py", "jwt.py", "password.py", "exceptions.py", "rbac.py", "service.py", "api.py"]

for mod in MODULES:
    src = SRC / mod
    if src.exists():
        dst = PKG / mod
        content = src.read_text(encoding="utf-8")
        # 替换导入路径
        content = content.replace("from src.auth.", "from matha_auth.")
        content = content.replace("import src.auth.", "import matha_auth.")
        dst.write_text(content, encoding="utf-8")
        print(f"  ✓ {mod}")

# 写 __init__.py
init_content = '''"""
Matha Auth — 认证与 RBAC 权限包

提供：
  - SessionManager: 内存会话管理（注册/登录/登出/Token刷新）
  - RBACMiddleware: 基于角色的访问控制中间件（含权限缓存）
  - PermissionChangeAPI: 权限变更管理 API
  - JWT Token 签发与验证
  - PBKDF2 密码哈希
"""
from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Matha Team"
__email__ = "matha@example.com"

from matha_auth.models import User, Session
from matha_auth.jwt import (
    encode_token,
    decode_token,
    encode_refresh_token,
    decode_refresh_token,
    get_token_expiry,
)
from matha_auth.password import hash_password, verify_password, validate_password_strength
from matha_auth.service import SessionManager
from matha_auth.rbac import (
    RBACMiddleware,
    Permission,
    get_rbac,
    reset_rbac,
)
from matha_auth.api import (
    PermissionChangeAPI,
    PermissionChangeResult,
    ChangeType,
    ChangeTarget,
)
from matha_auth.exceptions import (
    AuthError,
    AuthenticationError,
    AuthorizationError,
    TokenError,
    RegistrationError,
)

__all__ = [
    "__version__",
    "User",
    "Session",
    "encode_token",
    "decode_token",
    "encode_refresh_token",
    "decode_refresh_token",
    "get_token_expiry",
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "SessionManager",
    "RBACMiddleware",
    "Permission",
    "get_rbac",
    "reset_rbac",
    "PermissionChangeAPI",
    "PermissionChangeResult",
    "ChangeType",
    "ChangeTarget",
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "RegistrationError",
]
'''
(PKG / "__init__.py").write_text(init_content, encoding="utf-8")
print("  ✓ __init__.py")

print("Done!")
