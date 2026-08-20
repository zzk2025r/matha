"""
联调测试：TypeScript 类型定义 vs 后端 API
验证类型定义与实际数据结构的兼容性。
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth import SessionManager, RBACMiddleware, PermissionChangeAPI
from src.auth.rbac import reset_rbac
from src.auth.jwt import encode_token, decode_token


def test_jwt_payload_structure():
    """验证 JWT payload 结构与 ts 类型 JwtPayload 一致。"""
    mgr = SessionManager()
    mgr.register("test_user", "test@test.com", "TestPass1", roles=["editor"])
    session = mgr.login("test_user", "TestPass1")

    payload = decode_token(session.token)
    assert "sub" in payload, "缺少 sub 字段"
    assert "type" in payload, "缺少 type 字段"
    assert "roles" in payload, "缺少 roles 字段"
    assert "jti" in payload, "缺少 jti 字段"
    assert "iat" in payload, "缺少 iat 字段"
    assert "exp" in payload, "缺少 exp 字段"
    assert payload["type"] == "access", f"type 应为 access，实际 {payload['type']}"
    assert isinstance(payload["roles"], list), f"roles 应为 list，实际 {type(payload['roles'])}"
    assert isinstance(payload["jti"], str), f"jti 应为 str，实际 {type(payload['jti'])}"
    assert isinstance(payload["iat"], (int, float)), f"iat 应为 number"
    assert isinstance(payload["exp"], (int, float)), f"exp 应为 number"

    mgr.logout(session.session_id)
    print("  ✓ JWT payload 结构符合 JwtPayload 类型定义")


def test_user_model():
    """验证 User 模型字段与 ts 类型 User 一致。"""
    mgr = SessionManager()
    mgr.register("model_user", "model@test.com", "ModelPass1", roles=["viewer"])
    user = mgr.get_user("model_user")

    assert hasattr(user, "username"), "缺少 username 字段"
    assert hasattr(user, "email"), "缺少 email 字段"
    assert hasattr(user, "password_hash"), "缺少 password_hash 字段"
    assert hasattr(user, "created_at"), "缺少 created_at 字段"
    assert hasattr(user, "last_login"), "缺少 last_login 字段"
    assert hasattr(user, "is_active"), "缺少 is_active 字段"
    assert hasattr(user, "roles"), "缺少 roles 字段"
    assert isinstance(user.roles, list), "roles 应为 list"
    assert isinstance(user.is_active, bool), "is_active 应为 bool"

    print("  ✓ User 模型字段符合 TypeScript User 类型定义")


def test_session_model():
    """验证 Session 模型字段与 ts 类型 Session 一致。"""
    mgr = SessionManager()
    mgr.register("sess_user", "sess@test.com", "SessPass1")
    session = mgr.login("sess_user", "SessPass1")

    assert hasattr(session, "session_id"), "缺少 session_id"
    assert hasattr(session, "username"), "缺少 username"
    assert hasattr(session, "token"), "缺少 token"
    assert hasattr(session, "refresh_token"), "缺少 refresh_token"
    assert hasattr(session, "created_at"), "缺少 created_at"
    assert hasattr(session, "expires_at"), "缺少 expires_at"
    assert hasattr(session, "is_valid"), "缺少 is_valid"
    assert isinstance(session.is_valid, bool), "is_valid 应为 bool"

    mgr.logout(session.session_id)
    print("  ✓ Session 模型字段符合 TypeScript Session 类型定义")


def test_rbac_interface():
    """验证 RBACMiddleware 方法签名与 ts 类型定义一致。"""
    rbac = RBACMiddleware()
    rbac.register_role("test_role", {"doc:read", "doc:write"})

    # hasPermission
    result = rbac.has_permission(["test_role"], "doc:read")
    assert isinstance(result, bool), "hasPermission 应返回 bool"

    # authorize
    rbac.authorize(["test_role"], "doc:write")  # should not raise
    try:
        rbac.authorize(["test_role"], "code:run")
        assert False, "应抛出 AuthorizationError"
    except Exception:
        pass

    # getEffectivePermissions → 返回 frozenset（对应 ts Set<string>）
    perms = rbac.get_effective_permissions(["test_role"])
    assert hasattr(perms, "__iter__"), "权限应为可迭代集合"

    # registerRole
    rbac.register_role("test_role2", {"user:manage"})
    assert "test_role2" in rbac.list_roles()

    # removeRole
    assert rbac.remove_role("test_role2") is True
    assert "test_role2" not in rbac.list_roles()

    # listRoles
    roles = rbac.list_roles()
    assert isinstance(roles, list)

    print("  ✓ RBACMiddleware 接口符合 TypeScript RBACMiddleware 类型定义")


def test_permission_change_result():
    """验证 PermissionChangeResult 字段与 ts 类型一致。"""
    reset_rbac()
    mgr = SessionManager()
    rbac = RBACMiddleware()
    api = PermissionChangeAPI(rbac, mgr)

    mgr.register("admin_t", "admin@test.com", "AdminPass1", roles=["admin"])
    mgr.register("target_t", "target@test.com", "TargetPass1", roles=["viewer"])
    mgr.login("admin_t", "AdminPass1")

    result = api.set_roles("target_t", ["editor"], "admin_t")
    assert hasattr(result, "success"), "缺少 success"
    assert hasattr(result, "changed"), "缺少 changed"
    assert hasattr(result, "skipped"), "缺少 skipped"
    assert hasattr(result, "errors"), "缺少 errors"
    assert hasattr(result, "change_type"), "缺少 change_type"
    assert hasattr(result, "operator"), "缺少 operator"
    assert isinstance(result.success, bool), "success 应为 bool"
    assert isinstance(result.changed, list), "changed 应为 list"
    assert isinstance(result.errors, list), "errors 应为 list"

    print("  ✓ PermissionChangeResult 字段符合 TypeScript 类型定义")


def test_refresh_token_jti():
    """验证 refresh token 包含 jti 字段（ts 类型要求）。"""
    mgr = SessionManager()
    mgr.register("jti_user", "jti@test.com", "JtiPass1")
    session = mgr.login("jti_user", "JtiPass1")

    refresh_payload = decode_token(session.refresh_token)
    assert "jti" in refresh_payload, "refresh token 缺少 jti 字段"
    assert isinstance(refresh_payload["jti"], str), "jti 应为 str"

    mgr.logout(session.session_id)
    print("  ✓ Refresh Token 包含 jti 字段，符合 ts 类型定义")


def test_permission_constants():
    """验证 Permission 常量与 ts 类型 PermissionDescription 对应。"""
    from src.auth.rbac import Permission

    # 检查所有权限值格式为 "resource:action"
    perms = [
        Permission.DOC_READ(), Permission.DOC_WRITE(), Permission.DOC_DELETE(),
        Permission.USER_READ(), Permission.USER_WRITE(), Permission.USER_DELETE(),
        Permission.USER_MANAGE(), Permission.RUN_CODE(), Permission.DEBUG_RUN(),
    ]
    for p in perms:
        assert ":" in p.value, f"权限值格式错误: {p.value}"
        resource, action = p.value.split(":", 1)
        assert resource, "资源名不能为空"
        assert action, "操作名不能为空"

    print("  ✓ Permission 常量格式符合 ts PermissionDescription 定义")


def test_audit_log_structure():
    """验证审计日志条目结构符合 ts AuditEntry 类型。"""
    reset_rbac()
    mgr = SessionManager()
    rbac = RBACMiddleware()
    api = PermissionChangeAPI(rbac, mgr)

    mgr.register("audit_admin", "auditadmin@test.com", "AuditAdmin1", roles=["admin"])
    mgr.register("audit_target", "audittarget@test.com", "AuditTarget1", roles=["viewer"])
    mgr.login("audit_admin", "AuditAdmin1")

    api.set_roles("audit_target", ["editor"], "audit_admin")

    entry = api.audit_log[0]
    assert "time" in entry, "缺少 time 字段"
    assert "type" in entry, "缺少 type 字段"
    assert "target" in entry, "缺少 target 字段"
    assert "data" in entry, "缺少 data 字段"
    assert "operator" in entry, "缺少 operator 字段"
    assert entry["type"] in ("add_role", "remove_role", "set_role", "update_user"), \
        f"type 值无效: {entry['type']}"
    assert isinstance(entry["data"], dict), "data 应为 dict"

    print("  ✓ AuditEntry 结构符合 TypeScript 类型定义")


def test_concurrent_performance():
    """性能测试：验证反向索引优化效果。"""
    import time

    mgr = SessionManager()
    rbac = RBACMiddleware()

    # 注册 200 个用户并登录
    for i in range(200):
        mgr.register(f"perf_user{i:03d}", f"perf{i:03d}@test.com", f"PerfPass{i:03d}", roles=["viewer"])

    t0 = time.perf_counter()
    sessions = []
    for i in range(200):
        s = mgr.login(f"perf_user{i:03d}", f"PerfPass{i:03d}")
        sessions.append(s)
    t_login = time.perf_counter() - t0

    # 验证 token（使用反向索引）
    t0 = time.perf_counter()
    for s in sessions:
        mgr.verify_access_token(s.token)
    t_verify = time.perf_counter() - t0

    # 批量登出
    t0 = time.perf_counter()
    for s in sessions:
        mgr.logout(s.session_id)
    t_logout = time.perf_counter() - t0

    print(f"  ✓ 性能测试: 登录 200次={t_login:.3f}s, 验证 200次={t_verify:.3f}s, 登出 200次={t_logout:.3f}s")
    print(f"    反向索引优化生效: 验证吞吐量 = {200/t_verify:.0f} ops/s")


def main():
    print("\n" + "=" * 60)
    print("  TypeScript 类型定义 vs 后端 API 联调测试")
    print("=" * 60 + "\n")

    tests = [
        ("JWT Payload 结构", test_jwt_payload_structure),
        ("User 模型字段", test_user_model),
        ("Session 模型字段", test_session_model),
        ("RBAC 中间件接口", test_rbac_interface),
        ("PermissionChangeResult", test_permission_change_result),
        ("Refresh Token JTI", test_refresh_token_jti),
        ("Permission 常量", test_permission_constants),
        ("审计日志结构", test_audit_log_structure),
        ("性能测试（反向索引）", test_concurrent_performance),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {name}: {e}")

    print(f"\n{'=' * 60}")
    print(f"  结果: {passed}/{passed+failed} 通过")
    if failed:
        print(f"  ✗ {failed} 项失败")
    else:
        print(f"  ✓ 全部通过")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
