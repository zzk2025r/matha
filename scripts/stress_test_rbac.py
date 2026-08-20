#!/usr/bin/env python3
"""
RBAC 高并发压力测试 v2 — 精准测量各优化点性能
"""
from __future__ import annotations
import sys
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth import SessionManager, RBACMiddleware
from src.auth.rbac import reset_rbac
from src.auth.exceptions import AuthorizationError


SIZES = [50, 200, 500, 1000, 2000]
ROUNDS = 5  # 每规模重复次数


def bench_token_verify(mgr: SessionManager, n_users: int, rounds: int) -> dict:
    """测量 Token 验证延迟（微秒/次）。"""
    # 预热：登录所有用户
    for i in range(n_users):
        mgr.register(f"v{i:05d}", f"v{i:05d}@t.com", f"V{i:05d}Pass", roles=["viewer"])
    sessions = []
    for i in range(n_users):
        s = mgr.login(f"v{i:05d}", f"V{i:05d}Pass")
        sessions.append(s)

    # 基准测试
    total_ops = 0
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for s in sessions:
            payload = mgr.verify_access_token(s.token)
            if payload is not None:
                total_ops += 1
        dt = time.perf_counter() - t0
        times.append(dt)

    # 清理
    for s in sessions:
        mgr.logout(s.session_id)

    avg_ms = (sum(times) / len(times) / n_users) * 1000
    return {"users": n_users, "rounds": rounds, "total_ops": total_ops,
            "avg_ms_per_op": avg_ms, "ops_per_sec": total_ops / sum(times) if times else 0}


def bench_rbac_check(rbac: RBACMiddleware, n_checks: int, rounds: int) -> dict:
    """测量 RBAC 权限检查延迟。"""
    role_sets = [
        ["viewer"],
        ["editor"],
        ["viewer", "editor"],
        ["guest", "viewer", "editor"],
    ]
    total = 0
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for i in range(n_checks):
            roles = role_sets[i % len(role_sets)]
            rbac.has_permission(roles, "doc:read")
            rbac.has_permission(roles, "code:run")
            total += 2
        dt = time.perf_counter() - t0
        times.append(dt)

    avg_us = (sum(times) / len(times) / total) * 1_000_000
    return {"checks": n_checks, "rounds": rounds, "total_ops": total,
            "avg_us_per_op": avg_us, "ops_per_sec": total / sum(times) if times else 0}


def bench_concurrent_login(n_users: int, workers: int, rounds: int = 1) -> dict:
    """并发登录吞吐测试。"""
    mgr = SessionManager()

    def worker(i: int) -> bool:
        mgr.register(f"cl{i:05d}", f"cl{i:05d}@t.com", f"CL{i:05d}Pass", roles=["viewer"])
        try:
            s = mgr.login(f"cl{i:05d}", f"CL{i:05d}Pass")
            mgr.logout(s.session_id)
            return True
        except Exception:
            return False

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, i) for i in range(n_users)]
        results = [f.result() for f in as_completed(futures)]
    dt = time.perf_counter() - t0
    passed = sum(results)
    return {"users": n_users, "workers": workers, "passed": passed,
            "elapsed_s": dt, "ops_per_sec": passed / dt if dt > 0 else 0}


def bench_concurrent_refresh(n_users: int, workers: int) -> dict:
    """并发 Refresh Token 刷新测试。"""
    mgr = SessionManager()

    def worker(i: int) -> bool:
        mgr.register(f"cr{i:05d}", f"cr{i:05d}@t.com", f"CR{i:05d}Pass")
        try:
            s = mgr.login(f"cr{i:05d}", f"CR{i:05d}Pass")
            session_id = s.session_id
            refresh_token = s.refresh_token
            # 连续刷新 3 次
            for _ in range(3):
                _, refresh_token = mgr.refresh_token(refresh_token)
            mgr.logout(session_id)
            return True
        except Exception:
            return False

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, i) for i in range(n_users)]
        results = [f.result() for f in as_completed(futures)]
    dt = time.perf_counter() - t0
    passed = sum(results)
    return {"users": n_users, "workers": workers, "passed": passed,
            "elapsed_s": dt, "ops_per_sec": passed / dt if dt > 0 else 0}


def bench_concurrent_rbac(n_requests: int, workers: int) -> dict:
    """并发 RBAC 授权检查测试。"""
    rbac = RBACMiddleware()
    role_sets = [["viewer"], ["editor"], ["viewer", "editor"], ["guest", "editor"]]

    def worker(i: int) -> bool:
        roles = role_sets[i % len(role_sets)]
        try:
            rbac.authorize(roles, "doc:read")
            return True
        except AuthorizationError:
            return False

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, i) for i in range(n_requests)]
        results = [f.result() for f in as_completed(futures)]
    dt = time.perf_counter() - t0
    passed = sum(results)
    return {"requests": n_requests, "workers": workers, "passed": passed,
            "elapsed_s": dt, "ops_per_sec": passed / dt if dt > 0 else 0}


def bench_reverse_index(n_users: int) -> dict:
    """反向索引查找性能。"""
    mgr = SessionManager()
    for i in range(n_users):
        mgr.register(f"ri{i:05d}", f"ri{i:05d}@t.com", f"RI{i:05d}Pass", roles=["viewer"])
    sessions = []
    for i in range(n_users):
        s = mgr.login(f"ri{i:05d}", f"RI{i:05d}Pass")
        sessions.append(s)

    # 测试反向索引查找
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        for s in sessions:
            _ = mgr._user_sessions.get(s.username, [])
        dt = time.perf_counter() - t0
        times.append(dt)

    for s in sessions:
        mgr.logout(s.session_id)

    avg_us = (sum(times) / len(times) / n_users) * 1_000_000
    return {"users": n_users, "avg_us_per_lookup": avg_us}


def main():
    print("\n" + "=" * 60)
    print("  RBAC 高并发压力测试 v2 — 精准测量")
    print("=" * 60)

    results = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "versions": {}}

    # ---- Token 验证 ----
    print("\n[Token 验证延迟]")
    token_data = []
    for n in SIZES:
        r = bench_token_verify(SessionManager(), n, ROUNDS)
        token_data.append(r)
        print(f"  n={n:>5d}: {r['avg_ms_per_op']:>8.3f} ms/op  {r['ops_per_sec']:>8.0f} ops/s")
    results["versions"]["token_verify"] = token_data

    # ---- RBAC 权限检查 ----
    print("\n[RBAC 权限检查延迟]")
    rbac_data = []
    for n in [500, 2000, 10000, 50000]:
        r = bench_rbac_check(RBACMiddleware(), n, ROUNDS)
        rbac_data.append(r)
        print(f"  n={n:>6d}: {r['avg_us_per_op']:>8.3f} µs/op  {r['ops_per_sec']:>10.0f} ops/s")
    results["versions"]["rbac_check"] = rbac_data

    # ---- 并发登录 ----
    print("\n[并发登录吞吐]")
    login_data = []
    for n in SIZES:
        r = bench_concurrent_login(n, min(n, 50))
        login_data.append(r)
        print(f"  n={n:>5d}: {r['ops_per_sec']:>8.0f} ops/s  {r['elapsed_s']:.3f}s  {r['passed']}/{r['users']}")
    results["versions"]["concurrent_login"] = login_data

    # ---- 并发刷新 ----
    print("\n[并发 Refresh Token 刷新]")
    refresh_data = []
    for n in SIZES:
        r = bench_concurrent_refresh(n, min(n, 50))
        refresh_data.append(r)
        print(f"  n={n:>5d}: {r['ops_per_sec']:>8.0f} ops/s  {r['elapsed_s']:.3f}s  {r['passed']}/{r['users']}")
    results["versions"]["concurrent_refresh"] = refresh_data

    # ---- 并发 RBAC ----
    print("\n[并发 RBAC 授权检查]")
    rbac_perf_data = []
    for n in [500, 2000, 5000, 10000]:
        r = bench_concurrent_rbac(n, min(n, 50))
        rbac_perf_data.append(r)
        print(f"  n={n:>6d}: {r['ops_per_sec']:>8.0f} ops/s  {r['elapsed_s']:.3f}s  {r['passed']}/{r['requests']}")
    results["versions"]["concurrent_rbac"] = rbac_perf_data

    # ---- 反向索引 ----
    print("\n[反向索引查找延迟]")
    index_data = []
    for n in SIZES:
        r = bench_reverse_index(n)
        index_data.append(r)
        print(f"  n={n:>5d}: {r['avg_us_per_lookup']:>8.3f} µs/lookup")
    results["versions"]["reverse_index"] = index_data

    # 保存 JSON
    out = Path(__file__).parent.parent / "docs" / "benchmark_data_v2.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✓ 数据已保存: {out}")
    print()
    return results


if __name__ == "__main__":
    main()
