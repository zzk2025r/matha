"""Matha 服务守护进程 — 自动启动 / 端口管理 / 健康检查 / 自动重启

解决问题：
  1. 无网/有网环境下自动独立运行（无需手动启动）
  2. 有网络时允许外部访问（自动添加防火墙规则）
  3. 端口因更新冲突时自动清理旧进程并同步端口注册表

用法：
  # 前台守护（推荐日常使用）
  python -m src.matha_daemon

  # 指定端口
  python -m src.matha_daemon --port 8787

  # 单次启动（不持续守护）
  python -m src.matha_daemon --once

端口注册表文件：~/.matha_port.json
  { "port": 8787, "host": "127.0.0.1", "pid": 12345, "updated": "2026-09-11T12:00:00" }
"""
from __future__ import annotations

import json
import os
import platform
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 常量 ──────────────────────────────────────────────────────────────────

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8787
HEALTH_CHECK_INTERVAL = 10  # 秒
HEALTH_CHECK_TIMEOUT = 3   # 秒
MAX_RESTART_BACKOFF = 60   # 最大重启退避秒数
PORT_REGISTRY = Path.home() / ".matha_port.json"

# 服务脚本路径
SERVER_MODULE = "src.openai_compat_server"


# ── 端口注册表 ──────────────────────────────────────────────────────────────

def write_port_registry(port: int, host: str, pid: int) -> None:
    """写入端口注册表，供 Trae / 其他工具读取当前服务端口。"""
    data = {
        "port": port,
        "host": host,
        "pid": pid,
        "updated": datetime.now().isoformat(),
        "url": f"http://localhost:{port}/v1",
        "model": "matha",
    }
    try:
        PORT_REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def read_port_registry() -> dict | None:
    """读取端口注册表。"""
    try:
        if PORT_REGISTRY.is_file():
            return json.loads(PORT_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def clear_port_registry() -> None:
    """清除端口注册表。"""
    try:
        if PORT_REGISTRY.is_file():
            PORT_REGISTRY.unlink()
    except Exception:
        pass


# ── 端口管理 ────────────────────────────────────────────────────────────────

def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """检查端口是否被占用。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_pid_on_port(port: int) -> int | None:
    """查找占用指定端口的进程 PID（Windows）。"""
    if platform.system() != "Windows":
        try:
            out = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            return int(out) if out else None
        except Exception:
            return None
    try:
        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and f":{port}" in parts[1] and "LISTENING" in line:
                try:
                    return int(parts[-1])
                except ValueError:
                    continue
    except Exception:
        pass
    return None


def kill_pid(pid: int) -> bool:
    """终止指定 PID 的进程。"""
    if pid <= 0:
        return False
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=5)
        else:
            os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        return True
    except Exception:
        return False


def free_port_if_stale(port: int) -> bool:
    """如果端口被占用但服务不健康，清理占用进程。"""
    pid = find_pid_on_port(port)
    if pid is None:
        return True  # 端口空闲

    # 检查占用进程是否健康
    if is_service_healthy(port):
        # 进程健康，不需要清理
        return True

    # 进程不健康（可能是更新后的旧进程），清理它
    print(f"[daemon] 端口 {port} 被不健康进程 PID={pid} 占用，正在清理...")
    kill_pid(pid)
    time.sleep(2)

    # 验证端口已释放
    if is_port_in_use(port):
        print(f"[daemon] 警告：端口 {port} 仍被占用")
        return False
    print(f"[daemon] 端口 {port} 已释放")
    return True


def find_available_port(start: int = DEFAULT_PORT, max_tries: int = 10) -> int:
    """自动查找可用端口。"""
    for i in range(max_tries):
        port = start + i
        if not is_port_in_use(port):
            return port
    # 如果连续 max_tries 个端口都被占用，强制清理起始端口
    free_port_if_stale(start)
    return start


# ── 健康检查 ────────────────────────────────────────────────────────────────

def is_service_healthy(port: int) -> bool:
    """检查服务是否健康（GET /v1/models）。"""
    try:
        import urllib.request
        url = f"http://localhost:{port}/v1/models"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return "data" in data and len(data["data"]) > 0
    except Exception:
        return False


# ── 防火墙规则（Windows）──────────────────────────────────────────────────

def ensure_firewall_rule(port: int) -> None:
    """确保 Windows 防火墙允许指定端口入站（需要管理员权限）。"""
    if platform.system() != "Windows":
        return
    rule_name = f"Matha Service Port {port}"
    try:
        # 检查规则是否已存在
        check = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if check.returncode == 0 and rule_name in check.stdout:
            return  # 规则已存在

        # 添加入站规则
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "add", "rule",
             f"name={rule_name}",
             "dir=in", "action=allow", "protocol=TCP",
             f"localport={port}"],
            capture_output=True, timeout=10,
        )
        print(f"[daemon] 已添加防火墙入站规则: {rule_name}")
    except Exception as e:
        print(f"[daemon] 防火墙规则添加失败（可能需要管理员权限）: {e}")


# ── 服务进程管理 ────────────────────────────────────────────────────────────

def start_server_process(port: int, host: str) -> subprocess.Popen | None:
    """启动 OpenAI 兼容服务子进程。"""
    cmd = [sys.executable, "-m", SERVER_MODULE, "--host", host, "--port", str(port)]
    try:
        # 使用项目根目录作为工作目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=project_root,
            # Windows 下创建新进程组，便于整组终止
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0,
        )
        print(f"[daemon] 服务进程已启动 PID={proc.pid}，端口={port}")
        write_port_registry(port, host, proc.pid)
        return proc
    except Exception as e:
        print(f"[daemon] 启动服务失败: {e}")
        return None


def stop_server_process(proc: subprocess.Popen) -> None:
    """停止服务子进程。"""
    if proc.poll() is not None:
        return  # 已退出
    try:
        if platform.system() == "Windows":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    print(f"[daemon] 服务进程已停止 PID={proc.pid}")


# ── 守护主循环 ──────────────────────────────────────────────────────────────

def run_daemon(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, once: bool = False) -> None:
    """守护主循环：启动 → 健康检查 → 自动重启。"""
    print("[daemon] Matha 服务守护启动")
    print(f"[daemon] 目标端口: {port}，守护模式: {'单次' if once else '持续'}")
    print(f"[daemon] 端口注册表: {PORT_REGISTRY}")

    # 1. 清理可能存在的旧进程（更新后残留）
    if is_port_in_use(port):
        if not is_service_healthy(port):
            print(f"[daemon] 检测到端口 {port} 被不健康进程占用（可能是更新残留），正在清理...")
            free_port_if_stale(port)
        else:
            print(f"[daemon] 端口 {port} 上已有健康服务运行，无需重复启动")
            write_port_registry(port, host, find_pid_on_port(port) or 0)
            if once:
                return
            # 进入健康监控模式
    else:
        # 2. 端口可用，启动服务
        ensure_firewall_rule(port)
        proc = start_server_process(port, host)
        if proc is None:
            print("[daemon] 启动失败，退出")
            return

        # 等待服务就绪
        ready = False
        for _ in range(15):
            time.sleep(1)
            if proc.poll() is not None:
                print(f"[daemon] 服务进程意外退出，代码={proc.returncode}")
                break
            if is_service_healthy(port):
                print(f"[daemon] 服务已就绪 http://localhost:{port}/v1")
                ready = True
                break
        if not ready and proc.poll() is not None:
            # 启动失败，尝试查找可用端口
            new_port = find_available_port(port + 1)
            if new_port != port:
                print(f"[daemon] 端口 {port} 不可用，切换到端口 {new_port}")
                port = new_port
                ensure_firewall_rule(port)
                proc = start_server_process(port, host)
                for _ in range(15):
                    time.sleep(1)
                    if is_service_healthy(port):
                        print(f"[daemon] 服务已就绪 http://localhost:{port}/v1")
                        break
        if once:
            return

    # 3. 持续守护模式
    proc_holder: dict = {"proc": None}
    restart_count = 0
    last_restart = 0

    print(f"[daemon] 进入持续守护模式，健康检查间隔 {HEALTH_CHECK_INTERVAL}s")
    print(f"[daemon] Trae 配置: 接口地址 http://localhost:{port}/v1，模型名 matha")

    try:
        while True:
            time.sleep(HEALTH_CHECK_INTERVAL)

            # 检查服务健康
            if not is_service_healthy(port):
                print("[daemon] 服务不健康，尝试恢复...")

                # 如果有子进程引用，检查是否退出
                if proc_holder.get("proc") and proc_holder["proc"].poll() is not None:
                    print(f"[daemon] 服务进程已退出，代码={proc_holder['proc'].returncode}")

                # 清理旧进程（可能是更新残留）
                free_port_if_stale(port)
                time.sleep(2)

                # 退避重启
                now = time.time()
                if now - last_restart < MAX_RESTART_BACKOFF:
                    delay = min(MAX_RESTART_BACKOFF, (restart_count + 1) * 5)
                    print(f"[daemon] 等待 {delay}s 后重启（退避策略）...")
                    time.sleep(delay)

                proc = start_server_process(port, host)
                proc_holder["proc"] = proc
                last_restart = now
                restart_count += 1

                # 等待就绪
                for _ in range(15):
                    time.sleep(1)
                    if proc and proc.poll() is not None:
                        break
                    if is_service_healthy(port):
                        print(f"[daemon] 服务已恢复 (第 {restart_count} 次重启)")
                        break
            else:
                # 服务健康，重置重启计数
                if restart_count > 0:
                    restart_count = 0

    except KeyboardInterrupt:
        print("\n[daemon] 收到中断信号，正在停止...")
        if proc_holder.get("proc"):
            stop_server_process(proc_holder["proc"])
        clear_port_registry()
        print("[daemon] 已退出")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Matha 服务守护进程")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    parser.add_argument("--once", action="store_true", help="单次启动模式（不持续守护）")
    args = parser.parse_args()

    run_daemon(port=args.port, host=args.host, once=args.once)


if __name__ == "__main__":
    main()
