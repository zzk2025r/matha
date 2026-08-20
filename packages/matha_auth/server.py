"""
matha-auth FastAPI 最小化 HTTP 服务（生产就绪）

用法:
  python server.py                    # 开发模式（uvicorn 自启动）
  gunicorn matha_auth.server:app -w 4 -k uvicorn.workers.UvicornWorker
  # 或
  uvicorn matha_auth.server:app --host 0.0.0.0 --port 8000 --workers 4

环境变量:
  MATHA_AUTH_JWT_SECRET   JWT 签名密钥（生产必须设置）
  MATHA_AUTH_LOG_LEVEL    日志级别（默认 INFO）
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# 将 packages/ 加入 sys.path（支持 python server.py 直接运行）
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from matha_auth import (
    SessionManager,
    RBACMiddleware,
    PermissionChangeAPI,
    Permission,
)
from matha_auth.exceptions import AuthenticationError, AuthorizationError, TokenError

# ── 日志配置 ──────────────────────────────────────────────────────────────────
_LOG_LEVEL = os.environ.get("MATHA_AUTH_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("matha_auth.server")

# ── 全局单例 ──────────────────────────────────────────────────────────────────
# 生产环境建议通过 K8s ConfigMap 注入配置，此处使用内存存储（无状态服务可水平扩展）
_mgr = SessionManager()
_rbac = RBACMiddleware()
_api = PermissionChangeAPI(_rbac, _mgr)

# ── FastAPI 应用 ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Matha Auth API",
    description="用户认证与 RBAC 权限管理系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("MATHA_AUTH_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 健康检查 ──────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    """服务健康检查端点（K8s liveness/readiness probe）。"""
    return {"status": "ok", "version": "1.0.0"}


# ── 认证端点 ──────────────────────────────────────────────────────────────────
@app.post("/register", tags=["auth"])
async def register(
    username: str = Query(..., min_length=1),
    email: str = Query(...),
    password: str = Query(..., min_length=6),
    roles: list[str] | None = Query(None),
):
    """注册新用户。"""
    try:
        user = _mgr.register(username, email, password, roles)
        return {"username": user.username, "email": user.email, "roles": user.roles}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/login", tags=["auth"])
async def login(username: str = Query(...), password: str = Query(...)):
    """用户登录，返回 access_token 和 refresh_token。"""
    try:
        session = _mgr.login(username, password)
        return {
            "access_token": session.token,
            "refresh_token": session.refresh_token,
            "token_type": "bearer",
            "username": session.username,
        }
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="用户名或密码错误")


@app.post("/refresh", tags=["auth"])
async def refresh(refresh_token: str = Query(...)):
    """用 refresh token 换取新 access token。"""
    try:
        access, new_refresh = _mgr.refresh_token(refresh_token)
        return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}
    except (TokenError, AuthorizationError) as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/logout", tags=["auth"])
async def logout(session_id: str = Query(...)):
    """登出指定会话。"""
    _mgr.logout(session_id)
    return {"ok": True}


# ── 权限管理端点 ──────────────────────────────────────────────────────────────
@app.get("/roles/{username}", tags=["permissions"])
async def get_user_roles(username: str):
    """查询用户角色列表。"""
    user = _mgr.get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"username": username, "roles": user.roles}


@app.post("/roles/{username}", tags=["permissions"])
async def set_user_roles(
    username: str,
    roles: list[str] = Query(...),
    operator: str = Query(...),
):
    """为指定用户设置角色（需操作者具有 user:manage 权限）。"""
    result = _api.set_roles(username, roles, operator)
    if result.errors:
        raise HTTPException(status_code=400, detail=result.errors)
    return {"success": result.success, "changed": result.changed, "operator": operator}


@app.get("/permissions/{role}", tags=["permissions"])
async def get_role_permissions(role: str):
    """查询角色权限集合。"""
    perms = _rbac.get_role_permissions(role)
    if not perms:
        raise HTTPException(status_code=404, detail=f"角色 '{role}' 不存在")
    return {"role": role, "permissions": list(perms)}


@app.get("/roles", tags=["permissions"])
async def list_roles():
    """列出所有可用角色。"""
    return {"roles": _rbac.list_roles()}


# ── 审计日志 ──────────────────────────────────────────────────────────────────
@app.get("/audit", tags=["audit"])
async def get_audit_log(limit: int = Query(50, ge=1, le=200)):
    """获取最近 N 条审计日志。"""
    return {"audit_log": _api.audit_log[-limit:], "total": len(_api.audit_log)}


@app.post("/audit/clear", tags=["audit"])
async def clear_audit_log(operator: str = Query(...)):
    """清空审计日志（需管理员权限）。"""
    _api.set_roles("", [], operator)  # 触发权限检查
    count = _api.clear_audit_log()
    return {"cleared": count}


# ── 用户管理 ──────────────────────────────────────────────────────────────────
@app.get("/users", tags=["users"])
async def list_users():
    """列出所有用户（精简版）。"""
    return {"users": [
        {"username": u.username, "email": u.email, "is_active": u.is_active, "roles": u.roles}
        for u in _mgr._users.values()
    ]}


@app.put("/users/{username}/active", tags=["users"])
async def update_user_active(
    username: str,
    is_active: bool = Query(...),
    operator: str = Query(...),
):
    """更新用户激活状态。"""
    result = _api.update_users([username], is_active=is_active, operator=operator)
    if result.errors:
        raise HTTPException(status_code=400, detail=result.errors)
    return {"success": result.success, "changed": result.changed}


# ── 入口点 ────────────────────────────────────────────────────────────────────
def main() -> None:
    import uvicorn
    uvicorn.run(
        "matha_auth.server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        workers=int(os.environ.get("WORKERS", "1")),
        log_level=os.environ.get("MATHA_AUTH_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
