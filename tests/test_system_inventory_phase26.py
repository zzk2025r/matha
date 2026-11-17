# -*- coding: utf-8 -*-
"""阶段 26d 三锁：设备/任务管理器（src/system_inventory.py + system_monitor 域 +
matha sys CLI 子命令族）。

锁五面：
  A. 硬件盘点 —— which/run 可注入：nvidia-smi 命中（CSV 解析）/失败退出码/
     异常/缺席四态诚实；单片机工具链只探存在性（toolchain_families 板族映射）；
  B. 自身状况 —— 版本/插件汇总/后端/features/状态目录盘点/进程内存形状；
  C. 软件与模块清单 —— .matha/apps + .matha_packages manifest 解析（损坏
     manifest 跳过不伪装）；终端注册表/custom_ops/优化遍/插件使用四节；
  D. 域双面 —— system_monitor 五符号（硬件_信息/自身_状况/软件_清单/
     模块_清单/插件_冲突）host 与 VM 双面同值；
  E. CLI —— matha sys 六子节 JSON 输出 + 缺节诚实拒绝（argparse exit≠0）。

平台注意：内存面 psutil/resource 缺席记「不可得」（不伪装成功）；平台名
断言用集合成员而非硬编码单值。
"""
import json
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

from src.system_inventory import (
    hardware_info,
    modules_inventory,
    self_status,
    software_inventory,
)
from src import __version__ as matha_version

ROOT = Path(__file__).resolve().parent.parent

CLI = [sys.executable, str(ROOT / "src" / "matha_main.py"), "sys"]


def _cli(*argv, cwd=ROOT, timeout=120):
    return subprocess.run(CLI + list(argv), capture_output=True, text=True,
                          timeout=timeout, cwd=str(cwd))


# ============================================================
# A. 硬件盘点（注入面）
# ============================================================

def _fake_run(returncode=0, stdout=""):
    return lambda cmd, **kw: SimpleNamespace(returncode=returncode, stdout=stdout)


class TestHardwareInfo:
    def test_gpu_found_parsed(self):
        which = lambda name: "C:/fake/nvidia-smi" if name == "nvidia-smi" else None
        run = _fake_run(0, "NVIDIA RTX 4090, 24564 MiB, 536.40\n"
                           "NVIDIA RTX 3080, 10240 MiB, 536.40\n")
        info = hardware_info(which=which, run=run)
        gpu = info["GPU"]["nvidia"]
        assert gpu["可得"] is True and gpu["卡数"] == 2
        assert gpu["卡"][0] == {"名称": "NVIDIA RTX 4090", "显存": "24564 MiB",
                                "驱动": "536.40"}

    def test_gpu_nonzero_exit_honest(self):
        which = lambda name: "C:/fake/nvidia-smi" if name == "nvidia-smi" else None
        info = hardware_info(which=which, run=_fake_run(3, ""))
        gpu = info["GPU"]["nvidia"]
        assert gpu["可得"] is False and "退出码 3" in gpu["原因"]

    def test_gpu_command_exception_honest(self):
        which = lambda name: "C:/fake/nvidia-smi" if name == "nvidia-smi" else None

        def boom(cmd, **kw):
            raise TimeoutError("超时")

        info = hardware_info(which=which, run=boom)
        gpu = info["GPU"]["nvidia"]
        assert gpu["可得"] is False and "TimeoutError" in gpu["原因"]

    def test_gpu_absent_honest(self):
        info = hardware_info(which=lambda name: None, run=_fake_run())
        gpu = info["GPU"]["nvidia"]
        assert gpu["可得"] is False and gpu["原因"] == "nvidia-smi 未找到"

    def test_mcu_toolchain_probing(self):
        info = hardware_info(which=lambda name: None, run=_fake_run())
        tools = info["单片机工具链"]
        # 板族映射来自 mcu 域（真数据），探存面只报存在性
        assert set(tools) >= {"avrdude", "st-flash", "esptool", "openocd"}
        for tool, rec in tools.items():
            assert rec["可得"] is False and rec["路径"] is None
            assert isinstance(rec["板族"], list) and rec["板族"]

    def test_memory_shape_both_states(self):
        info = hardware_info(which=lambda n: None, run=_fake_run())
        mem = info["内存"]
        if mem["可得"]:
            assert {"总量字节", "可用字节", "占用百分比"} <= set(mem)
        else:
            assert mem["原因"] == "psutil 未安装"

    def test_static_fields(self):
        info = hardware_info(which=lambda n: None, run=_fake_run())
        assert {"平台", "架构", "系统版本", "Python", "CPU 逻辑核数"} <= set(info)
        assert info["平台"] in {"Windows", "Linux", "Darwin"}
        assert isinstance(info["CPU 逻辑核数"], int) and info["CPU 逻辑核数"] >= 1


class TestToolchainFamilies:
    def test_family_mapping_sorted(self):
        from src.domains.mcu import toolchain_families
        families = toolchain_families()
        assert families["avrdude"] == sorted(families["avrdude"])
        assert "uno" in families["avrdude"]
        # 每个 .matha 板名都归属唯一工具族
        all_boards = [b for boards in families.values() for b in boards]
        assert len(all_boards) == len(set(all_boards))


# ============================================================
# B. 自身状况
# ============================================================

class TestSelfStatus:
    def test_shape_and_identity(self, tmp_path):
        status = self_status(tmp_path)
        assert {"版本", "报告时刻", "工作目录", "插件", "运行时后端", "features",
                "扩展状态", "状态目录盘点", "进程内存"} <= set(status)
        assert status["版本"] == matha_version
        assert status["工作目录"] == str(tmp_path)
        report = status["插件"]
        # 全局注册表可能处于前序扩展启停测试的生命周期态——健康计数
        # （89 插件零被拒）由 compat 档新鲜构造锁定，此处只锁形态非空。
        assert report["插件总数"] >= 1
        assert "vm" in status["运行时后端"]["可用"]

    def test_state_dir_inventory_empty_root(self, tmp_path):
        status = self_status(tmp_path)
        inv = status["状态目录盘点"]
        assert inv[".matha 存在"] is False
        for name in ("store", "apps", "cache", "envs", "extensions.json"):
            assert inv["子项"][name] is False
        assert inv["子项"][".matha_packages（根级）"] is False
        assert status["扩展状态"] is None  # 无 extensions.json → 不装载不伪装

    def test_process_memory_honest_degradation(self, tmp_path):
        mem = self_status(tmp_path)["进程内存"]
        assert mem["可得"] is True or "原因" in mem  # 两态均诚实


# ============================================================
# C. 软件与模块清单
# ============================================================

class TestSoftwareInventory:
    def test_apps_and_packages_parsed(self, tmp_path):
        app_dir = tmp_path / ".matha" / "apps" / "计算器"
        app_dir.mkdir(parents=True)
        (app_dir / "manifest.json").write_text(json.dumps(
            {"应用": "计算器", "版本": "1.2", "入口": "main.matha",
             "来源": "商店", "安装时间": "2026-11-17"}), encoding="utf-8")
        pkg_dir = tmp_path / ".matha_packages" / "arithmetic"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "manifest.json").write_text(json.dumps(
            {"name": "arithmetic", "version": "0.1", "entry": "arithmetic.matha",
             "enabled": True}), encoding="utf-8")
        inv = software_inventory(tmp_path)
        assert inv["应用"] == [{"名": "计算器", "版本": "1.2", "入口": "main.matha",
                                "来源": "商店", "安装时间": "2026-11-17"}]
        pkg = inv["包"][0]
        assert pkg["名"] == "arithmetic" and pkg["版本"] == "0.1"
        assert pkg["入口"] == "arithmetic.matha" and pkg["启用"] is True

    def test_corrupt_manifest_skipped_not_faked(self, tmp_path):
        app_dir = tmp_path / ".matha" / "apps" / "坏应用"
        app_dir.mkdir(parents=True)
        (app_dir / "manifest.json").write_text("{损坏", encoding="utf-8")
        inv = software_inventory(tmp_path)
        assert inv["应用"] == []  # 跳过，不产出假条目

    def test_missing_dirs_empty(self, tmp_path):
        inv = software_inventory(tmp_path)
        assert inv == {"应用": [], "包": []}


class TestModulesInventory:
    def test_term_registry_parsed(self, tmp_path):
        (tmp_path / "matha_term_registry.txt").write_text(
            "部署 D:/tools/部署.msh\n坏行\n查看 C:/x/查看.msh\n",
            encoding="utf-8")
        inv = modules_inventory(tmp_path)
        assert inv["终端注册命令"] == [
            {"名": "部署", "路径": "D:/tools/部署.msh"},
            {"名": "查看", "路径": "C:/x/查看.msh"}]

    def test_four_sections_present(self, tmp_path):
        inv = modules_inventory(tmp_path)
        assert {"自定义运算符", "终端注册命令", "优化遍", "插件使用"} <= set(inv)
        assert isinstance(inv["自定义运算符"].get("版本", 0), int)
        for entry in inv["优化遍"]:
            assert {"名", "启用", "统计"} <= set(entry) or "不可得" in entry
        # 计数健康锁在 compat 档新鲜构造面；全局面只锁非空（见上）。
        assert len(inv["插件使用"]) >= 1


# ============================================================
# D. 域双面
# ============================================================

from src.diag_backends import ensure_registered  # noqa: E402
ensure_registered("src.interp")
from src.kernel.exec_api import run_checked  # noqa: E402


def _both_faces(source):
    h, he = run_checked(source, mode="legacy-interp")
    v, ve = run_checked(source, mode="vm")
    return (h, he), (v, ve)


class TestDomainBothFaces:
    def test_hardware_platform(self):
        (h, he), (v, ve) = _both_faces('输出(硬件_信息()["平台"])')
        assert he is None and ve is None
        assert h == v and h[0] in {"Windows", "Linux", "Darwin"}

    def test_self_version(self):
        (h, he), (v, ve) = _both_faces('输出(自身_状况()["版本"])')
        assert he is None and ve is None
        assert h == v == [matha_version]

    def test_software_and_modules(self):
        for src in ('输出(软件_清单()["包"])', '输出(模块_清单()["自定义运算符"]["版本"])'):
            (h, he), (v, ve) = _both_faces(src)
            assert he is None and ve is None
            assert h == v

    def test_conflicts_cross_face(self):
        (h, he), (v, ve) = _both_faces('输出(插件_冲突())')
        assert he is None and ve is None
        assert h == v and "梁_弯曲正应力" in str(h)


# ============================================================
# E. CLI
# ============================================================

class TestCliSys:
    def test_hardware_section(self):
        r = _cli("hardware")
        assert r.returncode == 0, r.stderr[-400:]
        data = json.loads(r.stdout)
        assert {"平台", "GPU", "单片机工具链"} <= set(data)

    def test_self_section(self):
        r = _cli("self")
        assert r.returncode == 0, r.stderr[-400:]
        data = json.loads(r.stdout)
        assert data["版本"] == matha_version
        assert data["插件"]["插件总数"] >= 89

    def test_plugins_section(self):
        r = _cli("plugins")
        assert r.returncode == 0, r.stderr[-400:]
        data = json.loads(r.stdout)
        assert {"汇总", "使用", "冲突"} <= set(data)
        assert data["汇总"]["注册被拒"] == {}

    def test_software_and_modules_sections(self):
        r = _cli("software")
        assert r.returncode == 0, r.stderr[-400:]
        assert {"应用", "包"} <= set(json.loads(r.stdout))
        r = _cli("modules")
        assert r.returncode == 0, r.stderr[-400:]
        assert {"自定义运算符", "终端注册命令", "优化遍", "插件使用"} \
            <= set(json.loads(r.stdout))

    def test_all_section_five_parts(self):
        r = _cli("all")
        assert r.returncode == 0, r.stderr[-400:]
        assert {"硬件", "自身", "插件", "软件", "模块"} == set(json.loads(r.stdout))

    def test_root_flag_honored(self, tmp_path):
        r = _cli("self", "--root", str(tmp_path))
        assert r.returncode == 0, r.stderr[-400:]
        data = json.loads(r.stdout)
        assert data["工作目录"] == str(tmp_path)
        assert data["状态目录盘点"][".matha 存在"] is False

    def test_missing_section_rejected(self):
        r = _cli()
        assert r.returncode != 0
