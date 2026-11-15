"""Matha 内核终端 I/O 原语（阶段 12b）。

终端所需的 OS 级最小能力——stdin 读取、目录/文件系统操作、进程内 Matha
执行——是「需要 OS 访问、纯 Matha 无法实现」的内核能力（与文件读写同族，
见 file_builtin.py 的定位声明）：

    宿主侧   src.interp.BUILTINS                —— 注册本模块实现
    VM 侧    src.mbc.vm._default_builtins       —— 注册同一批实现

命名独立（终端词法器/终端句法器为纯 Matha 模块，本文件只提供 OS 原语，
不做任何命令逻辑）。`调试Matha` 需要宿主解释器内部轨迹与环境快照，只能在
宿主侧实现——VM 侧注册同名实现但显式拒绝（诚实边界，非静默降级）。

安全边界：删除路径只允许文件与**空目录**（递归删除显式拒绝，永不提供
rmtree）。
"""
from __future__ import annotations

import os
import shutil

# 管道输入态（阶段 13a）：None = 交互模式（真 stdin）；List = 管道模式，
# 输入行() 逐行弹出缓存，耗尽即 EOF 空串——**不回落交互 stdin**（管道语义）。
# 管道结束() 恢复交互模式；终端执行器入口每次调用先清除，防上一条出错行泄漏。
_pipe_lines: list | None = None


def pipe_feed(lines) -> bool:
    """管道输入(行们) → 注入管道输入缓存（进入管道模式）。"""
    global _pipe_lines
    if not isinstance(lines, list):
        raise RuntimeError(f"管道输入: 需要 List 参数（行列表），实得 {type(lines).__name__}")
    _pipe_lines = [str(x) for x in lines]
    return True


def pipe_end(_=None) -> bool:
    """管道结束() → 清除管道态，恢复交互 stdin 模式。"""
    global _pipe_lines
    _pipe_lines = None
    return True


def read_line(_prompt=None) -> str:
    """输入行() → 读一行（不含行尾换行符）。

    管道模式：从管道缓存逐行弹出，耗尽返回空串（EOF 语义），不触碰
    交互 stdin；交互模式：真 stdin，EOF 返回空串。
    """
    if _pipe_lines is not None:
        return _pipe_lines.pop(0) if _pipe_lines else ""
    try:
        return input()
    except EOFError:
        return ""


def list_dir(path) -> list:
    """列目录(路径) → [[名, 是否目录, 大小字节], ...]（按名排序，含隐藏项）。"""
    try:
        out: list = []
        with os.scandir(str(path)) as it:
            for entry in sorted(it, key=lambda e: e.name):
                size = entry.stat(follow_symlinks=False).st_size
                out.append([entry.name, entry.is_dir(follow_symlinks=False), int(size)])
        return out
    except Exception as ex:
        raise RuntimeError(f"列目录失败: {ex}")


def make_dir(path) -> bool:
    """建目录(路径) → 成功 True（已存在亦视为成功，与 CMD mkdir 口径一致）。"""
    try:
        os.makedirs(str(path), exist_ok=True)
        return True
    except Exception as ex:
        raise RuntimeError(f"建目录失败: {ex}")


def delete_path(path) -> bool:
    """删除路径(路径) → 删除文件或**空目录**；目录非空 → 显式拒绝（安全边界）。"""
    p = str(path)
    if os.path.isdir(p):
        try:
            os.rmdir(p)
        except OSError as ex:
            raise RuntimeError(
                f"删除路径失败: 目录非空或不可删，递归删除不受支持（安全边界）: {ex}")
        return True
    if os.path.isfile(p) or os.path.islink(p):
        try:
            os.remove(p)
        except Exception as ex:
            raise RuntimeError(f"删除路径失败: {ex}")
        return True
    raise RuntimeError(f"删除路径失败: 路径不存在: {p}")


def copy_file(src, dst) -> bool:
    """复制文件(源, 目标) → True；失败显式报错。"""
    try:
        shutil.copy2(str(src), str(dst))
        return True
    except Exception as ex:
        raise RuntimeError(f"复制文件失败: {ex}")


def rename_path(old, new) -> bool:
    """改名(旧, 新) → True；目标已存在/跨盘等失败显式报错（不静默覆盖）。"""
    try:
        os.rename(str(old), str(new))
        return True
    except Exception as ex:
        raise RuntimeError(f"改名失败: {ex}")


def get_cwd(_=None) -> str:
    """当前目录() → 工作目录绝对路径。"""
    return os.getcwd()


def change_dir(path) -> bool:
    """换目录(路径) → True；失败显式报错。"""
    try:
        os.chdir(str(path))
        return True
    except Exception as ex:
        raise RuntimeError(f"换目录失败: {ex}")


def path_exists(path) -> bool:
    """路径存在(路径) → True/False。"""
    return os.path.exists(str(path))


def run_matha(source) -> list:
    """执行Matha(源码) → 当前进程内真实运行一段 Matha 源码，返回输出列表。

    经 src.kernel.exec_api（默认 MBC/VM 后端）执行；编译/运行错误如实上抛，
    不吞错、不伪造成功。
    """
    from src.kernel import exec_api
    outputs, error = exec_api.run_checked(str(source))
    if error is not None:
        raise RuntimeError(f"执行Matha 错误: {error}")
    return list(outputs)


def make_terminal_builtins(curry2) -> dict:
    """构造 12 个终端 I/O 内建（宿主/VM 注册面的物化面）。

    阶段 23a：注册点改为懒物化（src/kernel/lazy_kernel.py LazyKernelFn），
    程序用到任一终端符号时才 import 本模块。柯里化形状由调用方注入——
    宿主传 ``lambda fn: _curry_module(2, fn)``（lambda 链），VM 传 ``_curry2``
    （_Curried 类），物化值与旧急切值逐字节同形状。
    """
    from src.kernel.lazy_kernel import TERMINAL_BUILTIN_NAMES
    b: dict = {
        "输入行": read_line,
        "管道输入": pipe_feed,
        "管道结束": pipe_end,
        "列目录": list_dir,
        "建目录": make_dir,
        "删除路径": delete_path,
        "复制文件": curry2(copy_file),
        "改名": curry2(rename_path),
        "当前目录": get_cwd,
        "换目录": change_dir,
        "路径存在": path_exists,
        "执行Matha": run_matha,
    }
    assert set(b) == set(TERMINAL_BUILTIN_NAMES), "终端符号清单与 lazy_kernel 漂移"
    return b
