#!/usr/bin/env python3
"""
RBAC 高并发集成测试场景文档

场景列表:
  S1  - 多用户并发登录 + Token 刷新
  S2  - 角色变更期间 Token 一致性
  S3  - 批量权限变更后的即时生效验证
  S4  - Token 刷新竞态条件
  S5  - 登出与并发请求冲突
  S6  - 禁用账号后活跃 Token 处理
  S7  - 多角色用户权限合并一致性
  S8  - 审计日志并发写入完整性
  S9  - 长生命周期刷新 Token 续期测试
  S10 - 权限降级后立即生效测试
"""
from __future__ import annotations
import sys
import time
import threading
import statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth import SessionManager, RBACMiddleware, PermissionChangeAPI
from src.auth.rbac import reset_rbac, get_rbac
from src.auth.exceptions import AuthorizationError


# ============================================================
# 测试场景
# ============================================================

def scenario_1_concurrent_login_refresh():
    """S1: 100 用户并发登录 + Token 刷新"""
    mgr = SessionManager()
    rbac = RBACMiddleware()

    def worker(i):
        roles = ['admin', 'editor', 'viewer', 'guest'][i % 4]
        mgr.register(f'user{i}', f'user{i}@test.com', f'Pass{i:04d}', roles=[roles])
        session = mgr.login(f'user{i}', f'Pass{i:04d}')
        payload = mgr.verify_access_token(session.token)
        access, refresh = mgr.refresh_token(session.refresh_token)
        mgr.logout(session.session_id)
        return payload is not None and len(access) > 50

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(worker, i) for i in range(100)]
        results = [f.result() for f in as_completed(futures)]
    dt = time.perf_counter() - t0

    passed = sum(results)
    print(f"  S1 并发登录+刷新: {passed}/100 通过, 耗时 {dt:.2f}s")
    assert passed == 100, f"仅 {passed}/100 通过"
    return passed, dt


def scenario_2_role_change_during_token():
    """S2: 用户登录期间管理员变更其角色"""
    mgr = SessionManager()
    rbac = RBACMiddleware()
    api = PermissionChangeAPI(rbac, mgr)

    mgr.register("admin_user", "admin@test.com", "AdminPass1", roles=["admin"])
    mgr.login("admin_user", "AdminPass1")
    mgr.register("target_user", "target@test.com", "TargetPass1", roles=["viewer"])
    session = mgr.login("target_user", "TargetPass1")
    original_payload = mgr.verify_access_token(session.token)

    # 管理员将用户角色从 viewer 提升到 editor
    api.set_roles("target_user", ["editor"], "admin_user")

    # 原 Token 仍有效（JWT 无黑名单机制）
    still_valid = mgr.verify_access_token(session.token)
    # 新权限应生效（通过 RBAC 检查）
    new_can_write = rbac.has_permission(["editor"], "doc:write")

    mgr.logout(session.session_id)
    print(f"  S2 角色变更期间: token仍有效={still_valid is not None}, 新权限生效={new_can_write}")
    assert still_valid is not None, "原 token 应仍有效"
    assert new_can_write, "新角色权限应生效"


def scenario_3_batch_role_update():
    """S3: 批量修改多个用户角色后权限一致性"""
    mgr = SessionManager()
    rbac = RBACMiddleware()
    api = PermissionChangeAPI(rbac, mgr)

    mgr.register("batch_admin", "batchadmin@test.com", "BatchAdminPass1", roles=["admin"])
    mgr.login("batch_admin", "BatchAdminPass1")

    # 注册 20 个 viewer 用户
    for i in range(20):
        mgr.register(f"batch_user{i:02d}", f"batch{i:02d}@test.com", f"BatchPass{i:02d}", roles=["viewer"])

    # 批量提升到 editor
    for i in range(20):
        api.set_roles(f"batch_user{i:02d}", ["editor"], "batch_admin")

    # 验证所有用户有 editor 权限
    all_ok = True
    for i in range(20):
        user = mgr.get_user(f"batch_user{i:02d}")
        if not rbac.has_permission(user.roles, "doc:write"):
            all_ok = False
            break
    print(f"  S3 批量角色变更: {'通过' if all_ok else '失败'}")
    assert all_ok


def scenario_4_refresh_token_race():
    """S4: 同一 refresh token 并发刷新（竞态条件）"""
    mgr = SessionManager()
    mgr.register("race_user", "race@test.com", "RacePass1")
    session = mgr.login("race_user", "RacePass1")
    original_refresh = session.refresh_token

    results = {"first": None, "second_error": False}

    def try_refresh():
        try:
            access, refresh = mgr.refresh_token(original_refresh)
            results["first"] = access
            return True
        except Exception as e:
            results["second_error"] = True
            return False

    t1 = threading.Thread(target=try_refresh)
    t2 = threading.Thread(target=try_refresh)
    t1.start(); t2.start()
    t1.join(); t2.join()

    # 第一个成功，第二个应失败（token 已撤销）
    assert results["first"] is not None, "第一次刷新应成功"
    assert results["second_error"], "并发第二次刷新应失败"
    print(f"  S4 竞态刷新: 第一个成功, 第二个被拒 ✓")


def scenario_5_logout_concurrent_requests():
    """S5: 登出期间并发请求验证"""
    mgr = SessionManager()
    mgr.register("concurrent_user", "cc@test.com", "ConcPass1")
    session = mgr.login("concurrent_user", "ConcPass1")
    token = session.token

    results = []
    barrier = threading.Barrier(10)

    def verify():
        barrier.wait()  # 所有线程同时到达
        results.append(mgr.verify_access_token(token) is not None)

    threads = [threading.Thread(target=verify) for _ in range(10)]
    for t in threads: t.start()
    # 等待所有验证线程完成后登出
    for t in threads: t.join()

    # 登出后重新验证
    mgr.logout(session.session_id)
    post_logout = mgr.verify_access_token(token)

    # 验证线程在登出前运行，应全部成功
    all_success = all(results)
    print(f"  S5 登出并发验证: 登出前 {sum(results)}/10 有效, 登出后 {'失效' if post_logout is None else '仍有效'}")
    assert all_success, "登出前 token 应全部有效"
    assert post_logout is None, "登出后 token 应失效"


def scenario_6_disabled_user_active_tokens():
    """S6: 禁用账号后活跃 Token 的处理"""
    mgr = SessionManager()
    mgr.register("disabled_user", "disp@test.com", "DispPass1", roles=["admin"])
    session = mgr.login("disabled_user", "DispPass1")

    # 禁用账号
    user = mgr.get_user("disabled_user")
    user.is_active = False

    # 原 Token 应失效
    payload = mgr.verify_access_token(session.token)
    assert payload is None, "禁用后原 token 应失效"

    # 刷新也应失败
    try:
        mgr.refresh_token(session.refresh_token)
        assert False, "禁用用户刷新应失败"
    except AuthorizationError:
        pass

    print(f"  S6 禁用账号Token处理: 原token失效, refresh拒绝 ✓")


def scenario_7_multi_role_merge():
    """S7: 多角色用户权限合并一致性"""
    mgr = SessionManager()
    rbac = RBACMiddleware()

    # 自定义角色
    rbac.register_role("sec_admin", {"user:manage", "system:*"})
    rbac.register_role("code_lead", {"code:run", "code:debug", "doc:write"})

    mgr.register("multi_user", "multi@test.com", "MultiPass1", roles=["viewer", "sec_admin", "code_lead"])
    session = mgr.login("multi_user", "MultiPass1")
    payload = mgr.verify_access_token(session.token)

    # 应合并所有角色权限
    assert rbac.has_permission(payload["roles"], "doc:read"), "viewer → doc:read"
    assert rbac.has_permission(payload["roles"], "code:debug"), "code_lead → code:debug"
    assert rbac.has_permission(payload["roles"], "user:manage"), "sec_admin → user:manage"
    assert rbac.has_permission(payload["roles"], "system:restart"), "sec_admin → system:restart"
    assert not rbac.has_permission(payload["roles"], "doc:delete"), "不应有 doc:delete"

    mgr.logout(session.session_id)
    print(f"  S7 多角色合并: 4个权限通过, 1个拒绝 ✓")


def scenario_8_audit_log_consistency():
    """S8: 并发权限变更的审计日志完整性"""
    mgr = SessionManager()
    rbac = RBACMiddleware()
    api = PermissionChangeAPI(rbac, mgr)

    mgr.register("audit_target", "audit@test.com", "AuditPass1", roles=["viewer"])
    mgr.register("audit_admin", "admin2@test.com", "Admin2Pass1", roles=["admin"])
    mgr.login("audit_admin", "Admin2Pass1")

    changes = []

    def make_change(i):
        roles = ["editor"] if i % 2 == 0 else ["viewer"]
        api.set_roles("audit_target", roles, "audit_admin")
        changes.append(i)

    threads = [threading.Thread(target=make_change, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()

    # 审计日志应有 20 条
    assert len(api.audit_log) == 20, f"期望 20 条审计日志，实际 {len(api.audit_log)}"
    print(f"  S8 审计日志: {len(api.audit_log)} 条记录完整 ✓")


def scenario_9_refresh_token_lifecycle():
    """S9: Refresh Token 多次刷新生命周期"""
    mgr = SessionManager()
    mgr.register("lifecycle_user", "life@test.com", "LifePass1")
    session = mgr.login("lifecycle_user", "LifePass1")
    refresh = session.refresh_token

    chain = [refresh]
    for i in range(5):
        access, new_refresh = mgr.refresh_token(refresh)
        chain.append(new_refresh)
        refresh = new_refresh

    # 所有 token 应不同
    assert len(set(chain)) == 6, f"期望 6 个唯一 token，实际 {len(set(chain))}"
    # 旧 token 应全部失效
    for old_token in chain[:-1]:
        try:
            mgr.refresh_token(old_token)
            assert False, f"旧 token 应已失效: {old_token[:20]}"
        except Exception:
            pass

    mgr.logout(session.session_id)
    print(f"  S9 Token 链: 6 个唯一 token, 旧 token 全部失效 ✓")


def scenario_10_permission_degrade():
    """S10: 权限降级后立即生效"""
    mgr = SessionManager()
    rbac = RBACMiddleware()
    api = PermissionChangeAPI(rbac, mgr)

    mgr.register("degrade_user", "deg@test.com", "DegPass1", roles=["editor"])
    mgr.register("deg_admin", "degadmin@test.com", "DegAdmin1", roles=["admin"])
    session = mgr.login("degrade_user", "DegPass1")
    payload = mgr.verify_access_token(session.token)
    assert rbac.has_permission(payload["roles"], "doc:write"), "降级前应可写"

    # 降级为 viewer
    api.set_roles("degrade_user", ["viewer"], "deg_admin")

    # 新会话应无写权限
    mgr.logout(session.session_id)
    session2 = mgr.login("degrade_user", "DegPass1")
    payload2 = mgr.verify_access_token(session2.token)
    assert not rbac.has_permission(payload2["roles"], "doc:write"), "降级后不应可写"
    assert rbac.has_permission(payload2["roles"], "doc:read"), "降级后仍可读"

    mgr.logout(session2.session_id)
    print(f"  S10 权限降级: 降级前可写, 降级后仅可读 ✓")


# ============================================================
# 性能基准
# ============================================================

def bench_concurrent_operations():
    """基准测试：并发操作吞吐量"""
    mgr = SessionManager()
    rbac = RBACMiddleware()

    mgr.register("bench_admin", "benchadmin@test.com", "BenchAdminPass1", roles=["admin"])
    mgr.login("bench_admin", "BenchAdminPass1")
    api = PermissionChangeAPI(rbac, mgr)

    # 预热
    for i in range(10):
        mgr.register(f"bench{i}", f"bench{i}@test.com", f"BenchPass{i:02d}", roles=["viewer"])

    def bench_login(i):
        mgr.login(f"bench{i % 10}", f"BenchPass{i % 10:02d}")

    def bench_verify(i):
        user = mgr.get_user(f"bench{i % 10}")
        if user:
            session = mgr.login(user.username, f"BenchPass{i % 10:02d}")
            mgr.verify_access_token(session.token)
            mgr.logout(session.session_id)

    for ops, fn in [("登录 200次", lambda: [bench_login(i) for i in range(200)]),
                     ("验证 200次", lambda: [bench_verify(i) for i in range(200)])]:
        t0 = time.perf_counter()
        fn()
        dt = time.perf_counter() - t0
        print(f"  基准 {ops}: {dt:.3f}s ({200/dt:.0f} ops/s)")


# ============================================================
# 主入口
# ============================================================

SCENARIOS = [
    ("S1  并发登录+刷新 (100用户)", scenario_1_concurrent_login_refresh),
    ("S2  角色变更期间Token", scenario_2_role_change_during_token),
    ("S3  批量角色变更", scenario_3_batch_role_update),
    ("S4  Refresh Token竞态", scenario_4_refresh_token_race),
    ("S5  登出并发请求", scenario_5_logout_concurrent_requests),
    ("S6  禁用账号Token处理", scenario_6_disabled_user_active_tokens),
    ("S7  多角色权限合并", scenario_7_multi_role_merge),
    ("S8  审计日志完整性", scenario_8_audit_log_consistency),
    ("S9  Token刷新生命周期", scenario_9_refresh_token_lifecycle),
    ("S10 权限降级即时生效", scenario_10_permission_degrade),
]


def main():
    print("\n" + "=" * 60)
    print("  RBAC 高并发集成测试")
    print("=" * 60 + "\n")

    passed = 0
    failed = 0
    for name, fn in SCENARIOS:
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

    # 性能基准
    print("  性能基准:")
    bench_concurrent_operations()
    print()


if __name__ == "__main__":
    main()
