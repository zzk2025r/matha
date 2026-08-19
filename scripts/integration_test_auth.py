#!/usr/bin/env python3
"""
Matha 认证模块集成测试。

模拟完整的用户注册 -> 登录 -> Token 刷新 -> 登出流程，
以及基于角色的权限控制（RBAC）端到端验证。

用法:
    python scripts/integration_test_auth.py [--verbose]
"""
from __future__ import annotations
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("integration_test")


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def assert_true(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(f"断言失败: {msg}")
    print(f"  ✓ {msg}")


def assert_raises(exc_type: type, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
        raise AssertionError(f"应抛出 {exc_type.__name__} 但未抛出")
    except exc_type:
        print(f"  ✓ 正确抛出 {exc_type.__name__}")


# ============================================================
# 集成测试
# ============================================================

def test_full_auth_flow() -> None:
    """完整认证流程：注册 → 登录 → Token 验证 → 刷新 → 登出。"""
    section("完整认证流程测试")

    from src.auth import SessionManager, decode_token
    from src.auth.exceptions import AuthenticationError, TokenError

    mgr = SessionManager()

    # 1. 注册
    print("\n[1] 注册新用户")
    user = mgr.register("alice", "alice@example.com", "Alice1234", roles=["viewer"])
    assert_true(user.username == "alice", "用户名正确")
    assert_true(user.roles == ["viewer"], "角色正确")
    assert_true(mgr.count_users() == 1, "用户计数为1")
    print(f"      用户: {user.username} | 邮箱: {user.email} | 角色: {user.roles}")

    # 2. 登录
    print("\n[2] 用户登录")
    session = mgr.login("alice", "Alice1234")
    assert_true(session.username == "alice", "会话用户正确")
    assert_true(len(session.token) > 50, "access token 有效")
    assert_true(len(session.refresh_token) > 50, "refresh token 有效")
    assert_true(mgr.get_active_session_count("alice") == 1, "活跃会话数为1")
    print(f"      session_id: {session.session_id}")
    print(f"      access token:  {session.token[:40]}...")
    print(f"      refresh token: {session.refresh_token[:40]}...")

    # 3. 验证 access token
    print("\n[3] 验证 access token")
    payload = mgr.verify_access_token(session.token)
    assert_true(payload is not None, "token 有效")
    assert_true(payload["sub"] == "alice", "token 用户正确")
    assert_true(payload["roles"] == ["viewer"], "token 角色正确")
    print(f"      payload: sub={payload['sub']}, roles={payload['roles']}")

    # 4. 查询用户
    print("\n[4] 查询用户信息")
    user2 = mgr.get_user("alice")
    assert_true(user2 is not None, "用户存在")
    assert_true(user2.email == "alice@example.com", "邮箱正确")
    assert_true(user2.last_login is not None, "最后登录时间已设置")
    print(f"      last_login: {time.ctime(user2.last_login)}")

    # 5. 令牌刷新
    print("\n[5] 刷新令牌")
    new_access, new_refresh = mgr.refresh_token(session.refresh_token)
    assert_true(len(new_access) > 50, "新 access token 有效")
    assert_true(len(new_refresh) > 50, "新 refresh token 有效")
    assert_true(new_access != session.token, "新 token 与原 token 不同")

    # 旧 refresh token 应失效
    assert_raises(TokenError, mgr.refresh_token, session.refresh_token)
    print("      旧 refresh token 已失效 ✓")

    # 新 token 可验证
    new_payload = mgr.verify_access_token(new_access)
    assert_true(new_payload is not None, "新 access token 可验证")
    print(f"      新 payload: sub={new_payload['sub']}")

    # 6. 多会话
    print("\n[6] 多设备登录")
    session2 = mgr.login("alice", "Alice1234")
    assert_true(mgr.get_active_session_count("alice") == 2, "活跃会话数为2")
    print(f"      设备1: {session.session_id[:8]}...")
    print(f"      设备2: {session2.session_id[:8]}...")

    # 7. 登出
    print("\n[7] 登出设备1")
    assert_true(mgr.logout(session.session_id), "登出成功")
    assert_true(mgr.get_active_session_count("alice") == 1, "登出后会话数为1")
    assert_true(mgr.get_session(session.session_id) is None, "已登出会活已失效")
    print(f"      设备1 已登出，设备2 仍活跃")

    # 8. 登出设备2
    print("\n[8] 登出设备2")
    assert_true(mgr.logout(session2.session_id), "登出成功")
    assert_true(mgr.get_active_session_count("alice") == 0, "所有会话已登出")
    print("      所有设备已登出")

    print("\n  ✓ 完整认证流程测试通过")


def test_error_cases() -> None:
    """异常场景测试。"""
    section("异常场景测试")

    from src.auth import SessionManager
    from src.auth.exceptions import AuthenticationError, RegistrationError

    mgr = SessionManager()

    # 1. 重复注册
    print("\n[1] 重复注册")
    mgr.register("bob", "bob@test.com", "BobPass1")
    assert_raises(RegistrationError, mgr.register, "bob", "bob2@test.com", "BobPass1")
    print("      重复用户名被拒绝 ✓")

    # 2. 弱密码
    print("\n[2] 弱密码注册")
    assert_raises(RegistrationError, mgr.register, "charlie", "c@test.com", "weak")
    assert_raises(RegistrationError, mgr.register, "charlie", "c@test.com", "12345678")
    print("      弱密码被拒绝 ✓")

    # 3. 错误密码登录
    print("\n[3] 错误密码登录")
    assert_raises(AuthenticationError, mgr.login, "bob", "WrongPass")
    print("      错误密码被拒绝 ✓")

    # 4. 不存在的用户登录
    print("\n[4] 不存在的用户登录")
    assert_raises(AuthenticationError, mgr.login, "nobody", "AnyPass1")
    print("      不存在用户被拒绝 ✓")

    # 5. 大小写不敏感
    print("\n[5] 用户名大小写不敏感")
    session = mgr.login("BOB", "BobPass1")
    assert_true(session.username == "bob", "用户名已标准化为小写")
    print("      大小写不敏感 ✓")

    # 6. 禁用账号
    print("\n[6] 禁用账号")
    mgr.register("dave", "dave@test.com", "DavePass1")
    dave = mgr.get_user("dave")
    dave.is_active = False
    assert_raises(AuthenticationError, mgr.login, "dave", "DavePass1")
    print("      禁用账号无法登录 ✓")

    # 7. 踢出所有会话
    print("\n[7] 踢出所有会话")
    mgr.register("eve", "eve@test.com", "EvePass1")
    s1 = mgr.login("eve", "EvePass1")
    s2 = mgr.login("eve", "EvePass1")
    count = mgr.invalidate_all_sessions("eve")
    assert_true(count == 2, "踢出2个会话")
    assert_true(mgr.get_active_session_count("eve") == 0, "无活跃会话")
    print(f"      踢出 {count} 个会话 ✓")

    print("\n  ✓ 异常场景测试通过")


def test_rbac_integration() -> None:
    """RBAC 权限控制集成测试。"""
    section("RBAC 权限集成测试")

    from src.auth import SessionManager
    from src.auth.rbac import RBACMiddleware, Permission, AuthorizationError

    mgr = SessionManager()
    rbac = RBACMiddleware()

    # 注册不同角色的用户
    admin = mgr.register("admin_user", "admin@test.com", "AdminPass1", roles=["admin"])
    editor = mgr.register("editor_user", "editor@test.com", "EditorPass1", roles=["editor"])
    viewer = mgr.register("viewer_user", "viewer@test.com", "ViewerPass1", roles=["viewer"])
    guest = mgr.register("guest_user", "guest@test.com", "GuestPass1", roles=["guest"])

    users = {
        "admin":  admin,
        "editor": editor,
        "viewer": viewer,
        "guest":  guest,
    }

    # 权限矩阵测试
    tests = [
        # (user_role, permission, should_pass)
        ("admin",  "doc:read",    True),
        ("admin",  "doc:write",   True),
        ("admin",  "doc:delete",  True),
        ("admin",  "user:manage", True),
        ("editor", "doc:read",    True),
        ("editor", "doc:write",   True),
        ("editor", "doc:delete",  False),
        ("editor", "user:manage", False),
        ("viewer", "doc:read",    True),
        ("viewer", "doc:write",   False),
        ("viewer", "code:run",    True),
        ("viewer", "user:manage", False),
        ("guest",  "doc:read",    True),
        ("guest",  "doc:write",   False),
        ("guest",  "code:run",    False),
    ]

    passed = 0
    failed = 0
    for role, perm, expected in tests:
        user = users[role]
        result = rbac.has_permission(user.roles, perm)
        if result == expected:
            passed += 1
            status = "✓"
        else:
            failed += 1
            status = "✗"
        print(f"  {status} {role:8s} → {perm:12s} expected={expected} got={result}")

    # 授权检查
    print("\n[授权检查]")
    rbac.authorize(admin.roles, "user:manage")
    print("  ✓ admin 可执行 user:manage")

    try:
        rbac.authorize(viewer.roles, "doc:write")
        print("  ✗ viewer 不应可执行 doc:write")
        failed += 1
    except AuthorizationError:
        print("  ✓ viewer 不能执行 doc:write（正确拒绝）")
        passed += 1

    # 装饰器用法
    print("\n[装饰器用法]")
    @rbac.require_permission("doc:write")
    def create_document(user):
        return f"Created doc for {user['username']}"

    admin_session = mgr.login("admin_user", "AdminPass1")
    viewer_session = mgr.login("viewer_user", "ViewerPass1")

    admin_payload = mgr.verify_access_token(admin_session.token)
    viewer_payload = mgr.verify_access_token(viewer_session.token)

    result = create_document({"roles": admin_payload["roles"], "username": "admin"})
    print(f"  ✓ admin 创建文档: {result}")

    try:
        create_document({"roles": viewer_payload["roles"], "username": "viewer"})
        print("  ✗ viewer 不应能创建文档")
        failed += 1
    except AuthorizationError:
        print("  ✓ viewer 不能创建文档（正确拒绝）")
        passed += 1

    print(f"\n  RBAC 测试结果: {passed} 通过, {failed} 失败")
    assert_true(failed == 0, f"RBAC 测试全部通过 ({passed} passed)")


def test_permissions_class() -> None:
    """Permission 常量测试。"""
    section("Permission 常量测试")

    from src.auth.rbac import Permission

    perms = [
        ("doc:read",    Permission.DOC_READ),
        ("doc:write",   Permission.DOC_WRITE),
        ("doc:delete",  Permission.DOC_DELETE),
        ("user:read",   Permission.USER_READ),
        ("user:write",  Permission.USER_WRITE),
        ("user:delete", Permission.USER_DELETE),
        ("user:manage", Permission.USER_MANAGE),
        ("code:run",    Permission.RUN_CODE),
        ("code:debug",  Permission.DEBUG_RUN),
    ]

    for expected, factory in perms:
        p = factory()
        assert_true(p.value == expected, f"{expected} 常量正确")

    print(f"\n  ✓ 全部 {len(perms)} 个 Permission 常量正确")


def test_token_lifecycle() -> None:
    """Token 生命周期测试。"""
    section("Token 生命周期测试")

    from src.auth import SessionManager, decode_token

    mgr = SessionManager()
    mgr.register("life", "life@test.com", "LifePass1")
    session = mgr.login("life", "LifePass1")

    # 1. Access token 解码
    print("\n[1] Access Token 结构")
    payload = decode_token(session.token)
    assert_true(payload["type"] == "access", "type=access")
    assert_true(payload["sub"] == "life", "sub=life")
    assert_true("roles" in payload, "包含 roles 字段")
    assert_true("jti" in payload, "包含 jti 唯一标识")
    assert_true("iat" in payload, "包含 iat 签发时间")
    assert_true("exp" in payload, "包含 exp 过期时间")
    print(f"      jti: {payload['jti']}")
    print(f"      iat: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['iat']))}")
    print(f"      exp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['exp']))}")

    # 2. Refresh Token 解码
    print("\n[2] Refresh Token 结构")
    refresh_payload = decode_token(session.refresh_token)
    assert_true(refresh_payload["type"] == "refresh", "type=refresh")
    assert_true(refresh_payload["sub"] == "life", "sub=life")
    print(f"      jti: {refresh_payload['jti']}")
    print(f"      有效期: {refresh_payload['exp'] - refresh_payload['iat']} 秒")

    # 3. Token 唯一性
    print("\n[3] Token 唯一性")
    session2 = mgr.login("life", "LifePass1")
    assert_true(session.token != session2.token, "不同会话 token 不同")
    assert_true(session.refresh_token != session2.refresh_token, "不同会话 refresh token 不同")
    assert_true(session.token != session2.token, "access tokens 不同")
    print("  ✓ 每个会话生成唯一的 token 对")

    mgr.logout(session.session_id)
    mgr.logout(session2.session_id)

    print("\n  ✓ Token 生命周期测试通过")


# ============================================================
# 主入口
# ============================================================

def main() -> None:
    verbose = "--verbose" in sys.argv
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("\n" + "=" * 60)
    print("  Matha 认证模块集成测试")
    print("=" * 60)

    tests = [
        ("完整认证流程", test_full_auth_flow),
        ("异常场景", test_error_cases),
        ("RBAC 权限控制", test_rbac_integration),
        ("Permission 常量", test_permissions_class),
        ("Token 生命周期", test_token_lifecycle),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  ✗ {name} 失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"  集成测试结果: {passed}/{passed + failed} 通过")
    if failed == 0:
        print("  ✓ 全部通过")
    else:
        print(f"  ✗ {failed} 项失败")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
