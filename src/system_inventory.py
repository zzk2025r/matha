# -*- coding: utf-8 -*-
"""Matha 设备/任务管理器信息层（阶段 26d）。

四个盘点节的纯函数层（纯标准库 + 只读探测；psutil/系统命令缺失时诚实降级，
不伪装成功）。CLI（matha sys）与领域（src/domains/system_monitor.py）共用。

  hardware_info()      硬件与状况：平台/CPU/内存/GPU 工具链/单片机工具链/Python
  self_status()        Matha 自身：版本/插件汇总/运行时后端/features/扩展状态/.matha 盘点
  software_inventory() 软件清单：.matha/apps 安装 + .matha_packages 包
  modules_inventory()  模块清单：custom_ops/终端注册表/优化遍/已加载插件

检测边界（登记口径）：只读——GPU 面只调 nvidia-smi 查询不设状态；单片机工具链
只探存在性（真实烧录见 mcu 域）；内存面 psutil 缺席记「不可得」。
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

_MATHA_DIRNAME = ".matha"
_TERM_REGISTRY_FILENAME = "matha_term_registry.txt"

_GPU_QUERY = ["--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]


# ============================================================
# 硬件与状况
# ============================================================

def hardware_info(*, which: Callable[[str], str | None] | None = None,
                  run: Callable[..., subprocess.CompletedProcess] | None = None) -> dict:
    """硬件盘点（which/run 可注入——测试面）。缺失工具诚实降级为 不可得。"""
    which = which or shutil.which
    run = run or subprocess.run

    memory: dict = {"可得": False, "原因": "psutil 未安装"}
    try:
        import psutil
        vm = psutil.virtual_memory()
        memory = {"可得": True, "总量字节": vm.total, "可用字节": vm.available,
                  "占用百分比": vm.percent}
    except Exception:
        pass

    gpu: dict = {"nvidia": {"可得": False, "原因": "nvidia-smi 未找到"}}
    nvidia = which("nvidia-smi")
    if nvidia:
        try:
            proc = run(["nvidia-smi", *_GPU_QUERY], capture_output=True,
                       text=True, timeout=10)
            if proc.returncode == 0 and proc.stdout.strip():
                cards = []
                for line in proc.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) == 3:
                        cards.append({"名称": parts[0], "显存": parts[1],
                                      "驱动": parts[2]})
                gpu["nvidia"] = {"可得": True, "卡数": len(cards), "卡": cards}
            else:
                gpu["nvidia"] = {"可得": False, "原因": f"退出码 {proc.returncode}"}
        except Exception as e:
            gpu["nvidia"] = {"可得": False, "原因": f"{type(e).__name__}: {e}"}

    from src.domains.mcu import toolchain_families
    mcu_tools = {}
    for tool, boards in toolchain_families().items():
        path = which(tool)
        mcu_tools[tool] = {"可得": path is not None, "路径": path, "板族": boards}

    return {
        "平台": platform.system(),
        "架构": platform.machine(),
        "系统版本": platform.release(),
        "Python": platform.python_version(),
        "CPU 逻辑核数": os.cpu_count(),
        "内存": memory,
        "GPU": gpu,
        "单片机工具链": mcu_tools,
    }


# ============================================================
# Matha 自身状况
# ============================================================

def _process_memory() -> dict:
    """当前进程内存（psutil 可选；resource 在 Windows 缺席——诚实降级）。"""
    try:
        import resource  # noqa: F401  Unix 面
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        return {"可得": True, "峰值 RSS 字节": rusage.ru_maxrss * 1024,
                "来源": "resource.getrusage"}
    except Exception:
        pass
    try:
        import psutil
        proc = psutil.Process()
        mi = proc.memory_info()
        return {"可得": True, "RSS 字节": mi.rss, "来源": "psutil"}
    except Exception:
        return {"可得": False, "原因": "psutil 未安装（Windows 无 resource 面）"}


def self_status(root: str | Path | None = None) -> dict:
    """Matha 自身盘点：版本/插件汇总/运行时/features/扩展/状态目录。"""
    root = Path(root) if root else Path.cwd()
    matha_dir = root / _MATHA_DIRNAME

    from src import __version__ as matha_version
    from src.kernel.exec_api import available_modes, backend_info
    from src.plugin_api import get_resolver

    resolver = get_resolver()
    report = resolver.report()

    features = {}
    try:
        from src.features import known_states
        features = known_states()
    except Exception:
        features = {"不可得": True}

    ext_state = None
    try:
        from src.extensions import load_state
        if (matha_dir / "extensions.json").exists():
            ext_state = load_state(root)
    except Exception:
        ext_state = {"损坏": True}

    inventory: dict[str, bool] = {}
    for name in ("store", "apps", "cache", "envs"):
        inventory[name] = (matha_dir / name).exists()
    inventory["extensions.json"] = (matha_dir / "extensions.json").exists()
    inventory[".matha_packages（根级）"] = (root / ".matha_packages").exists()

    return {
        "版本": matha_version,
        "报告时刻": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "工作目录": str(root),
        "插件": report,
        "运行时后端": {"可用": available_modes(), "登记": backend_info()},
        "features": features,
        "扩展状态": ext_state,
        "状态目录盘点": {".matha 存在": matha_dir.exists(), "子项": inventory},
        "进程内存": _process_memory(),
    }


# ============================================================
# 软件清单（检测与加载软件）
# ============================================================

def _read_manifest(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def software_inventory(root: str | Path | None = None) -> dict:
    """软件清单：已安装应用（.matha/apps）+ 已装包（.matha_packages）。"""
    root = Path(root) if root else Path.cwd()

    apps = []
    apps_dir = root / _MATHA_DIRNAME / "apps"
    if apps_dir.exists():
        for d in sorted(apps_dir.iterdir()):
            manifest = _read_manifest(d / "manifest.json")
            if manifest is not None:
                apps.append({"名": manifest.get("应用", d.name),
                             "版本": manifest.get("版本", ""),
                             "入口": manifest.get("入口", ""),
                             "来源": manifest.get("来源", ""),
                             "安装时间": manifest.get("安装时间", "")})

    packages = []
    pkgs_dir = root / ".matha_packages"
    if pkgs_dir.exists():
        for d in sorted(pkgs_dir.iterdir()):
            manifest = _read_manifest(d / "manifest.json")
            if manifest is not None:
                packages.append({"名": manifest.get("name", d.name),
                                 "版本": manifest.get("version", ""),
                                 "入口": manifest.get("entry", ""),
                                 "启用": manifest.get("enabled", True)})

    return {"应用": apps, "包": packages}


# ============================================================
# 模块清单（检测自定义/模块/已加载插件）
# ============================================================

def modules_inventory(root: str | Path | None = None) -> dict:
    """模块清单：自定义运算符/终端注册命令/优化遍/已加载插件。"""
    root = Path(root) if root else Path.cwd()

    custom_ops = {}
    try:
        from src.custom_ops import REGISTRY, version
        custom_ops = {"版本": version(),
                      "符号": {sym: {"precedence": op.precedence, "assoc": op.assoc}
                               for sym, op in REGISTRY.items()}}
    except Exception:
        custom_ops = {"不可得": True}

    term_registry: list[dict] = []
    reg_path = root / _TERM_REGISTRY_FILENAME
    if reg_path.exists():
        for line in reg_path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                term_registry.append({"名": parts[0], "路径": " ".join(parts[1:])})

    passes = []
    try:
        from src.compiler.pass_manager import get_pass_manager
        manager = get_pass_manager()
        stats = manager.get_stats()
        enabled = getattr(manager, "_enabled_passes", set())
        passes = [{"名": name, "启用": name in enabled, "统计": stats.get(name, {})}
                  for name in getattr(manager, "_passes", {})]
    except Exception:
        passes = [{"不可得": True}]

    from src.plugin_api import get_resolver
    return {
        "自定义运算符": custom_ops,
        "终端注册命令": term_registry,
        "优化遍": passes,
        "插件使用": get_resolver().plugin_usage(),
    }
