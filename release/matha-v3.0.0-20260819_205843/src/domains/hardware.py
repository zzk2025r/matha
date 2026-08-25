# -*- coding: utf-8 -*-
"""Hardware Domain: 硬件控制与系统交互内建。

覆盖：
  - 进程管理：exec、kill、wait、ps
  - 网络通信：socket_send、socket_recv、http_get、dns_resolve
  - 文件系统扩展：目录操作、权限查询
  - 系统信息：cpu_count、memory_info、disk_info、uptime
  - GPIO/设备模拟：pin_mode、pin_write、pin_read（仿真层，适配真实硬件需扩展）
  - 环境交互：环境变量读写、系统命令执行

注意：GPIO/设备层在解释器层面为仿真模式；
      真实硬件访问需通过 sys.path 注入 platform 层（如 pigpio, pyserial, RPi.GPIO）。
"""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys
from typing import Any


# ============================================================
# 系统信息
# ============================================================

def _cpu_count() -> int:
    """返回逻辑 CPU 核心数。"""
    return os.cpu_count() or 1


def _memory_info() -> dict:
    """返回内存信息（bytes）。"""
    try:
        import resource
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "rss": rusage.ru_maxrss * 1024,  # macOS/Linux 单位为 KB
            "user_time": rusage.ru_utime,
            "sys_time": rusage.ru_stime,
        }
    except ImportError:
        # Windows fallback
        return {"rss": 0, "user_time": 0.0, "sys_time": 0.0}


def _platform_info() -> str:
    """返回当前平台标识。"""
    return platform.system()


def _arch_info() -> str:
    """返回架构信息。"""
    return platform.machine()


# ============================================================
# 进程管理
# ============================================================

def _exec_cmd(cmd: str, timeout: int = 30) -> dict:
    """执行系统命令，返回 {code, stdout, stderr}。"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            "code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"code": -1, "stdout": "", "stderr": "timeout"}
    except Exception as e:
        return {"code": -2, "stdout": "", "stderr": str(e)}


def _ps() -> list[dict]:
    """返回当前进程列表。"""
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            procs.append({
                "pid": p.info["pid"],
                "name": p.info["name"],
                "cpu": p.info["cpu_percent"],
                "mem": p.info["memory_percent"],
            })
        return procs
    except ImportError:
        # fallback: ps 命令
        res = _exec_cmd("ps aux" if platform.system() != "Windows" else "tasklist")
        lines = res["stdout"].strip().split("\n")
        return [{"raw": line} for line in lines[:50]]


def _kill(pid: int, sig: int = 15) -> bool:
    """向进程发送信号。"""
    try:
        os.kill(pid, sig)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _wait(pid: int, timeout: int = 5) -> bool:
    """等待进程结束。"""
    try:
        import psutil
        return psutil.wait_procs([psutil.Process(pid)], timeout=timeout)
    except ImportError:
        return True  # 简化：假设等待成功


# ============================================================
# 网络通信
# ============================================================

def _socket_send(host: str, port: int, data: str, timeout: int = 5) -> dict:
    """发送 TCP 数据，返回 {sent, response}。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(data.encode())
        response = sock.recv(4096).decode(errors="replace")
        sock.close()
        return {"sent": len(data), "response": response}
    except Exception as e:
        return {"sent": 0, "response": "", "error": str(e)}


def _socket_recv(host: str, port: int, timeout: int = 5) -> str:
    """连接并接收数据（HTTP GET 场景）。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(b"GET / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
        data = sock.recv(4096).decode(errors="replace")
        sock.close()
        return data
    except Exception as e:
        return f"error: {e}"


def _http_get(url: str, timeout: int = 10) -> dict:
    """HTTP GET 请求，返回 {status, body}。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        # 简单解析 URL
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            url = url[8:]
        parts = url.split("/", 1)
        host = parts[0]
        path = "/" + parts[1] if len(parts) > 1 else "/"
        port = 443 if url.startswith("443:") else 80
        if ":" in host:
            host, p = host.split(":")
            port = int(p)

        sock.connect((host, port))
        request = f"GET {path} HTTP/1.0\r\nHost: {host}\r\n\r\n"
        sock.sendall(request.encode())
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk.decode(errors="replace"))
        sock.close()
        body = "".join(chunks)
        # 提取状态码
        status_line = body.split("\r\n")[0] if body else ""
        return {"status": status_line, "body": body}
    except Exception as e:
        return {"status": "", "body": "", "error": str(e)}


def _dns_resolve(hostname: str) -> list[str]:
    """DNS 解析，返回 IP 列表。"""
    try:
        addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
        return list(set(a[4][0] for a in addrs))
    except socket.gaierror:
        return []


def _ping(host: str, count: int = 4) -> dict:
    """Ping 测试。"""
    res = _exec_cmd(
        f"ping -n {count} {host}" if platform.system() == "Windows"
        else f"ping -c {count} {host}"
    )
    return {"output": res["stdout"], "code": res["code"]}


# ============================================================
# GPIO 仿真层
# ============================================================

# 仿真 GPIO 状态表（模拟引脚状态）
_gpio_state: dict[int, dict] = {}


def _gpio_init(pin: int, mode: str = "out") -> None:
    """初始化 GPIO 引脚（仿真）。mode: 'in' | 'out' | 'pwm'。"""
    if pin < 0:
        raise ValueError(f"无效引脚: {pin}")
    _gpio_state[pin] = {"mode": mode, "value": 0}


def _gpio_set(pin: int, value: int) -> None:
    """设置 GPIO 引脚输出。"""
    if pin not in _gpio_state:
        _gpio_init(pin, "out")
    if _gpio_state[pin]["mode"] == "in":
        raise RuntimeError(f"引脚 {pin} 为输入模式，不可写入")
    _gpio_state[pin]["value"] = 1 if value else 0


def _gpio_get(pin: int) -> int:
    """读取 GPIO 引脚输入。"""
    if pin not in _gpio_state:
        _gpio_init(pin, "in")
    if _gpio_state[pin]["mode"] != "in":
        raise RuntimeError(f"引脚 {pin} 为输出模式，不可读取")
    return _gpio_state[pin]["value"]


def _gpio_pwm(pin: int, duty: float, freq: int = 1000) -> None:
    """设置 PWM 输出（仿真）。duty: 0-100。"""
    if pin not in _gpio_state:
        _gpio_init(pin, "pwm")
    _gpio_state[pin]["mode"] = "pwm"
    _gpio_state[pin]["duty"] = max(0, min(100, duty))
    _gpio_state[pin]["freq"] = freq


def _gpio_cleanup(pin: int) -> None:
    """清理 GPIO 引脚。"""
    _gpio_state.pop(pin, None)


# ============================================================
# 文件/目录扩展
# ============================================================

def _list_dir(path: str = ".") -> list[str]:
    """列出目录内容。"""
    try:
        return os.listdir(str(path))
    except Exception as e:
        return [f"error: {e}"]


def _mkdir(path: str, recursive: bool = False) -> bool:
    """创建目录。"""
    try:
        if recursive:
            os.makedirs(str(path), exist_ok=True)
        else:
            os.mkdir(str(path))
        return True
    except Exception:
        return False


def _file_exists(path: str) -> bool:
    """检查文件是否存在。"""
    return os.path.exists(str(path))


def _file_size(path: str) -> int:
    """返回文件大小（字节）。"""
    try:
        return os.path.getsize(str(path))
    except Exception:
        return -1


# ============================================================
# 环境变量
# ============================================================

def _env_get(name: str, default: str = "") -> str:
    """读取环境变量。"""
    return os.environ.get(name, default)


def _env_set(name: str, value: str) -> None:
    """设置环境变量。"""
    os.environ[name] = str(value)


# ============================================================
# 内建注册
# ============================================================

def _register_hardware(builtins: dict) -> None:
    """将硬件控制内建注册到解释器。"""
    # 系统信息（0 参函数，忽略 Matha 传入的 0 值参数）
    builtins["cpu核数"] = lambda _: _cpu_count()
    builtins["平台"] = lambda _: _platform_info()
    builtins["架构"] = lambda _: _arch_info()
    builtins["内存信息"] = lambda _: _memory_info()

    # 进程管理
    builtins["执行命令"] = lambda cmd, timeout=30: _exec_cmd(cmd, timeout)
    builtins["进程列表"] = _ps
    builtins["终止进程"] = _curry2(_kill)
    builtins["等待进程"] = _curry2(_wait)

    # 网络
    builtins["socket发送"] = _curry3(_socket_send)
    builtins["socket接收"] = _curry2(_socket_recv)
    builtins["http获取"] = _curry2(_http_get)
    builtins["DNS解析"] = _dns_resolve
    builtins["ping"] = _curry2(_ping)

    # GPIO（仿真层）- 直接传参（Matha 单次应用，传 tuple 解包）
    builtins["GPIO初始化"] = lambda args: _gpio_init(args[0], args[1]) if isinstance(args, (list, tuple)) and len(args) >= 2 else _gpio_init(args, "out")
    builtins["GPIO写入"] = lambda args: _gpio_set(args[0], args[1]) if isinstance(args, (list, tuple)) and len(args) >= 2 else _gpio_set(args, 1)
    builtins["GPIO读取"] = lambda args: _gpio_get(args[0]) if isinstance(args, (list, tuple)) and len(args) >= 1 else _gpio_get(args)
    builtins["PWM设置"] = lambda args: _gpio_pwm(args[0], args[1], args[2]) if isinstance(args, (list, tuple)) and len(args) >= 3 else _gpio_pwm(args, 50.0, 1000)
    builtins["GPIO清理"] = lambda args: _gpio_cleanup(args[0]) if isinstance(args, (list, tuple)) and len(args) >= 1 else _gpio_cleanup(args)

    # 文件/目录扩展
    builtins["列出目录"] = _list_dir
    builtins["创建目录"] = _curry2(_mkdir)
    builtins["文件存在"] = _file_exists
    builtins["文件大小"] = _file_size

    # 环境变量
    builtins["环境变量"] = _env_get
    builtins["设置环境变量"] = _env_set


def _register_hardware_symtab_names() -> list[str]:
    """返回硬件域所有内建名。"""
    return [
        "cpu核数", "平台", "架构", "内存信息",
        "执行命令", "进程列表", "终止进程", "等待进程",
        "socket发送", "socket接收", "http获取", "DNS解析", "ping",
        "GPIO初始化", "GPIO写入", "GPIO读取", "PWM设置", "GPIO清理",
        "列出目录", "创建目录", "文件存在", "文件大小",
        "环境变量", "设置环境变量",
    ]


# 柯里化辅助（与 mechanics.py 保持一致）
def _curry2(fn):
    """两参 Python 函数 → 柯里化 f(a)(b)。"""
    def with_first(a):
        return lambda b: fn(a, b)
    return with_first


def _curry3(fn):
    """三参 → 柯里化 f(a)(b)(c)。"""
    def with_first(a):
        def with_second(b):
            return lambda c: fn(a, b, c)
        return with_second
    return with_first
