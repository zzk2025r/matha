"""matha-auth HTTP server 最小化示例（FastAPI）"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse

from matha_auth import SessionManager, RBACMiddleware, PermissionChangeAPI
from matha_auth.exceptions import AuthenticationError, AuthorizationError

app = FastAPI(title="Matha Auth API", version="1.0.0")

# 全局单例（生产环境应从配置加载）
mgr = SessionManager()
rbac = RBACMiddleware()
api = PermissionChangeAPI(rbac, mgr)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register")
def register(username: str, email: str, password: str, roles: list[str] | None = None):
    try:
        user = mgr.register(username, email, password, roles)
        return {"username": user.username, "roles": user.roles}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/login")
def login(username: str, password: str):
    try:
        session = mgr.login(username, password)
        return {
            "access_token": session.token,
            "refresh_token": session.refresh_token,
            "username": session.username,
        }
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="用户名或密码错误")


@app.post("/refresh")
def refresh(refresh_token: str):
    try:
        access, new_refresh = mgr.refresh_token(refresh_token)
        return {"access_token": access, "refresh_token": new_refresh}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/logout")
def logout(session_id: str):
    mgr.logout(session_id)
    return {"ok": True}


@app.post("/roles/{username}")
def set_roles(username: str, roles: list[str], operator: str):
    result = api.set_roles(username, roles, operator)
    if result.errors:
        raise HTTPException(status_code=400, detail=result.errors)
    return {"success": result.success, "changed": result.changed}


@app.get("/roles/{username}")
def get_roles(username: str):
    user = mgr.get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"username": username, "roles": user.roles}


@app.get("/audit")
def get_audit(limit: int = 50):
    return {"audit_log": api.audit_log[-limit:]}
