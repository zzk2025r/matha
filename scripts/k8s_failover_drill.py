"""
matha-auth Kubernetes 高可用故障转移演练脚本

用途: 在生产或测试集群中模拟 Pod 故障，验证 HA 配置的正确性。

用法:
  python k8s_failover_drill.py --namespace matha-auth --replicas 3 --dry-run
  python k8s_failover_drill.py --namespace matha-auth --replicas 3

前置要求:
  - kubectl 已配置并可访问目标集群
  - helm 已安装
  - namespace 已创建：kubectl create ns matha-auth
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ── 配置 ──────────────────────────────────────────────────────────────────────

DRILL_CONFIG = {
    # 每次故障模拟的 Pod 数量
    "crash_count": 1,
    # 每次崩溃后等待 Pod 恢复的时间（秒）
    "recovery_wait": 15,
    # 健康检查间隔（秒）
    "health_interval": 3,
    # 演练最大重试次数
    "max_retries": 5,
    # 演练完成后自动删除演练标记 Pod
    "cleanup": True,
}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def run(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """执行 shell 命令并返回结果。"""
    flags = {"capture_output": capture, "text": True}
    result = subprocess.run(cmd, check=False, **flags)
    if check and result.returncode != 0:
        print(f"  ✗ 命令失败: {' '.join(cmd)}")
        print(f"    stderr: {result.stderr[:200]}")
    return result


def kubectl_get(kind: str, name: str = "", ns: str = "", extra: str = "") -> str:
    """获取 K8s 资源信息。"""
    cmd = ["kubectl", "get", kind]
    if name:
        cmd.append(name)
    if ns:
        cmd += ["-n", ns]
    if extra:
        cmd.append(extra)
    result = run(cmd)
    return result.stdout if result.returncode == 0 else ""


def kubectl_exec(pod: str, cmd: list[str], ns: str = "") -> str:
    """在 Pod 内执行命令。"""
    args = ["kubectl", "exec", pod, "--", *cmd]
    if ns:
        args.insert(2, "-n")
        args.insert(3, ns)
    result = run(args)
    return result.stdout if result.returncode == 0 else ""


def kubectl_delete(kind: str, name: str, ns: str = "") -> bool:
    """删除 K8s 资源。"""
    cmd = ["kubectl", "delete", kind, name]
    if ns:
        cmd += ["-n", ns]
    result = run(cmd, check=False)
    return result.returncode == 0


# ── 演练步骤 ──────────────────────────────────────────────────────────────────

class FailoverDrill:
    """Kubernetes 高可用故障转移演练器。"""

    def __init__(self, namespace: str, replicas: int, dry_run: bool):
        self.ns = namespace
        self.replicas = replicas
        self.dry_run = dry_run
        self.results: list[dict] = []
        self.start_time = datetime.now()

    def log(self, msg: str, status: str = "INFO") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] [{status:>6}] {msg}")

    # ── 前置检查 ──────────────────────────────────────────────────────────────

    def check_prerequisites(self) -> bool:
        """检查前置条件。"""
        self.log("检查前置条件...")
        checks = [
            ("kubectl", ["kubectl", "version", "--client", "-o", "json"], "kubectl 已安装"),
            ("namespace", ["kubectl", "get", "ns", self.ns], f"namespace '{self.ns}' 存在"),
            ("deployment", ["kubectl", "get", "deployment", "matha-auth", "-n", self.ns], "Deployment 存在"),
        ]
        ok = True
        for name, cmd, desc in checks:
            result = run(cmd, check=False)
            if result.returncode == 0:
                self.log(f"  ✓ {desc}")
            else:
                self.log(f"  ✗ {desc} — 跳过后续检查", "WARN")
                ok = False
        return ok

    # ── 滚动崩溃演练 ──────────────────────────────────────────────────────────

    def run_crash_loop(self, rounds: int = 3) -> list[dict]:
        """对 Pod 进行滚动崩溃演练。"""
        outcomes = []
        self.log(f"开始滚动崩溃演练：{rounds} 轮")

        for round_i in range(1, rounds + 1):
            self.log(f"  ── 第 {round_i}/{rounds} 轮 ──")

            # 获取当前 Pod 列表
            pods_out = kubectl_get("pods", extra="-l app=matha-auth", ns=self.ns)
            pods = [line.split()[0] for line in pods_out.splitlines()
                    if line.strip() and "matha-auth" in line and "Running" in line]

            if not pods:
                self.log("  无可用 Pod，跳过本轮", "WARN")
                outcomes.append({"round": round_i, "status": "skip_no_pods"})
                continue

            # 选择要崩溃的 Pod（轮询策略）
            target = pods[(round_i - 1) % len(pods)]
            self.log(f"  目标 Pod: {target} ({len(pods)} 个 Pod 可用)")

            if self.dry_run:
                self.log(f"  [DRY-RUN] 将执行: kubectl delete pod {target}", "DRY")
                outcomes.append({"round": round_i, "target": target, "status": "dry_run"})
                continue

            # 执行崩溃
            deleted = kubectl_delete("pod", target, ns=self.ns)
            if not deleted:
                self.log(f"  删除 Pod {target} 失败", "ERROR")
                outcomes.append({"round": round_i, "target": target, "status": "delete_failed"})
                continue

            self.log(f"  Pod {target} 已删除，等待恢复...")

            # 等待 Pod 恢复
            for attempt in range(DRILL_CONFIG["max_retries"]):
                time.sleep(DRILL_CONFIG["recovery_wait"])
                new_pods = kubectl_get("pods", extra="-l app=matha-auth", ns=self.ns)
                running = [l for l in new_pods.splitlines()
                           if "Running" in l and target not in l]
                if len(running) >= max(1, self.replicas - 1):
                    self.log(f"  Pod 已恢复（剩余 {len(running)} 个 Running）")
                    outcomes.append({"round": round_i, "target": target, "status": "recovered"})
                    break
            else:
                self.log(f"  Pod 未在 {DRILL_CONFIG['max_retries']} 次尝试内恢复", "ERROR")
                outcomes.append({"round": round_i, "target": target, "status": "timeout"})

        return outcomes

    # ── 健康检查 ──────────────────────────────────────────────────────────────

    def check_service_health(self) -> dict:
        """检查服务整体健康状态。"""
        self.log("执行服务健康检查...")

        # 1. Pod 状态
        pods_out = kubectl_get("pods", extra="-l app=matha-auth", ns=self.ns)
        lines = [l for l in pods_out.splitlines() if l.strip()]
        pod_status = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                pod_status[parts[0]] = parts[2]  # name → status

        running = sum(1 for s in pod_status.values() if s == "Running")
        total = len(pod_status)

        # 2. Deployment 副本数
        deploy_out = kubectl_get("deployment", "matha-auth", ns=self.ns)
        deploy_ok = any("2/2" in l or "3/3" in l for l in deploy_out.splitlines())

        # 3. Service 端点
        eps_out = kubectl_get("endpoints", "matha-auth", ns=self.ns)
        eps_ok = len(eps_out.strip()) > 0 and "no endpoints" not in eps_out.lower()

        healthy = running == total and deploy_ok and eps_ok
        return {
            "timestamp": datetime.now().isoformat(),
            "healthy": healthy,
            "running_pods": running,
            "total_pods": total,
            "pod_statuses": pod_status,
            "deployment_ok": deploy_ok,
            "endpoints_ok": eps_ok,
        }

    # ── 压力测试 ──────────────────────────────────────────────────────────────

    def run_load_test(self, duration: int = 30) -> dict:
        """在故障恢复期间发送 HTTP 请求压力测试。"""
        self.log(f"启动 {duration}s 压力测试...")

        # 获取 Service 域名
        svc_host = f"matha-auth.{self.ns}.svc.cluster.local"
        self.log(f"  目标: http://{svc_host}/health")

        if self.dry_run:
            self.log(f"  [DRY-RUN] 将执行: curl -s http://{svc_host}/health")
            return {"status": "dry_run", "requests": 0, "success": 0, "failed": 0}

        # 使用 kubectl port-forward 或 curl 并发请求
        # 这里用简单的并行 curl 模拟
        results = {"total": 0, "success": 0, "failed": 0, "latencies": []}
        start = time.time()

        while time.time() - start < duration:
            # 并发发送 10 个健康检查请求
            for _ in range(10):
                results["total"] += 1
                proc = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code},%{time_total}",
                            "--connect-timeout", "5", f"http://{svc_host}/health"], check=False)
                if proc.returncode == 0:
                    parts = proc.stdout.strip().split(",")
                    code = parts[0] if parts else "0"
                    lat = float(parts[1]) if len(parts) > 1 and parts[1] else 0
                    if code == "200":
                        results["success"] += 1
                    else:
                        results["failed"] += 1
                    results["latencies"].append(lat)
            time.sleep(0.1)

        avg_lat = sum(results["latencies"]) / len(results["latencies"]) if results["latencies"] else 0
        results["avg_latency_s"] = round(avg_lat, 4)
        results["success_rate"] = (
            round(results["success"] / results["total"] * 100, 1)
            if results["total"] else 0
        )
        self.log(f"  压力测试完成: 成功={results['success']}/{results['total']} "
                 f"成功率={results['success_rate']}% 平均延迟={avg_lat:.3f}s")
        return results

    # ── 演练报告 ──────────────────────────────────────────────────────────────

    def print_report(self, crash_results: list, health: dict, load: dict) -> None:
        """打印演练报告。"""
        print("\n" + "=" * 60)
        print("  matha-auth Kubernetes 故障转移演练报告")
        print("=" * 60)

        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"\n  演练时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} "
              f"（持续 {int(elapsed)}s）")
        print(f"  环境: namespace={self.ns} replicas={self.replicas} "
              f"{'[DRY-RUN]' if self.dry_run else ''}")

        # 崩溃演练结果
        print("\n  [崩溃演练]")
        for r in crash_results:
            icon = "✓" if r.get("status") == "recovered" else ("⊘" if r.get("status") == "dry_run" else "✗")
            print(f"    {icon} 第 {r['round']} 轮: pod={r.get('target', 'N/A')} "
                  f"status={r['status']}")

        # 健康检查结果
        print(f"\n  [健康检查]")
        print(f"    运行 Pod: {health['running_pods']}/{health['total_pods']}")
        print(f"    Deployment: {'✓ 正常' if health['deployment_ok'] else '✗ 异常'}")
        print(f"    Endpoints:  {'✓ 正常' if health['endpoints_ok'] else '✗ 异常'}")
        print(f"    整体状态:   {'✓ 健康' if health['healthy'] else '✗ 异常'}")

        # 压力测试结果
        print(f"\n  [压力测试]")
        print(f"    总请求:    {load.get('total', 0)}")
        print(f"    成功:      {load.get('success', 0)}")
        print(f"    失败:      {load.get('failed', 0)}")
        print(f"    成功率:    {load.get('success_rate', 0)}%")
        print(f"    平均延迟:  {load.get('avg_latency_s', 0)}s")

        # 结论
        print("\n  [结论]")
        passed = all(
            r.get("status") in ("recovered", "dry_run") for r in crash_results
        ) and health["healthy"] and load.get("success_rate", 0) >= 95
        if passed:
            print("  ✓ 演练通过：故障转移正常，服务可用性满足 SLA")
        else:
            print("  ✗ 演练未通过：请检查 Pod 恢复时间和 Service 端点配置")

        print("=" * 60)

    def save_report(self, crash_results: list, health: dict, load: dict) -> Path:
        """将报告保存到文件。"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "namespace": self.ns,
            "replicas": self.replicas,
            "dry_run": self.dry_run,
            "crash_results": crash_results,
            "health_check": health,
            "load_test": load,
        }
        out = Path(__file__).parent / "failover_drill_report.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  报告已保存: {out}")
        return out


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="matha-auth Kubernetes 高可用故障转移演练脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
          示例:
            python k8s_failover_drill.py --namespace matha-auth --replicas 3 --dry-run
            python k8s_failover_drill.py --namespace matha-auth --replicas 3
            python k8s_failover_drill.py --namespace matha-auth --replicas 3 --rounds 5
        """),
    )
    parser.add_argument("--namespace", default="matha-auth", help="K8s namespace")
    parser.add_argument("--replicas", type=int, default=3, help="Deployment 副本数")
    parser.add_argument("--rounds", type=int, default=3, help="崩溃演练轮数")
    parser.add_argument("--load-duration", type=int, default=30, help="压力测试时长（秒）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印操作计划")
    args = parser.parse_args()

    print("=" * 60)
    print("  matha-auth K8s 故障转移演练")
    print("=" * 60)
    print(f"  Namespace : {args.namespace}")
    print(f"  Replicas  : {args.replicas}")
    print(f"  Rounds    : {args.rounds}")
    print(f"  Load test : {args.load_duration}s")
    print(f"  Dry run   : {args.dry_run}")

    drill = FailoverDrill(args.namespace, args.replicas, args.dry_run)

    # 1. 前置检查
    if not drill.check_prerequisites():
        print("\n  ✗ 前置检查未通过，请确认 kubectl 配置和 namespace")
        sys.exit(1)

    # 2. 滚动崩溃演练
    crash_results = drill.run_crash_loop(rounds=args.rounds)

    # 3. 健康检查
    health = drill.check_service_health()

    # 4. 压力测试
    load = drill.run_load_test(duration=args.load_duration)

    # 5. 生成报告
    drill.print_report(crash_results, health, load)
    drill.save_report(crash_results, health, load)

    # 6. 结论
    passed = (
        all(r.get("status") in ("recovered", "dry_run") for r in crash_results)
        and health["healthy"]
        and load.get("success_rate", 0) >= 95
    )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
