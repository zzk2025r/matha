# -*- coding: utf-8 -*-
"""阶段 12b：终端 OS 胶水内建入门禁（输入行/文件系统/执行Matha/调试Matha/网络）。

三锁纪律：
  ① 对拍：同一文件系统操作序列，宿主内建 = VM 内建（真实 OS 行为一致）。
  ② 闭环：执行Matha 进程内真执行两端一致；调试Matha 真轨迹+真快照+真变量。
  ③ 拒绝：非空目录递归删除显式拒绝；VM 调试Matha 显式拒绝（非静默降级）；
     取网址/执行Matha 失败如实上抛。

网络用 file:// URL 走真实 urllib.request（无 mock、无外网依赖）。
零跳过，零失败。
"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.interp import Interpreter
from src.parser import parse as py_parse
from src.kernel import exec_api
import src.ast_nodes as ast


# ---------- 夹具 ----------

@pytest.fixture()
def host():
    interp = Interpreter()
    interp.outputs.clear()
    return interp


def _host_run(interp, src):
    interp.outputs.clear()
    interp.run(py_parse(src))
    return interp.outputs


@pytest.fixture(scope="module")
def vm():
    """空模块 VM：终端内建经 _default_builtins 直接可用（_write_file 等为柯里化原语）。"""
    comp = Compiler()
    comp.compile_program(ast.Program(decls=[]))
    v = VM(comp.mod)
    v.run()
    return v


from src.mbc.compiler import Compiler  # noqa: E402
from src.mbc.vm import VM  # noqa: E402


def _vm_run(src):
    outs, err = exec_api.run_checked(src)
    if err is not None:
        raise err
    return outs


# ---------- ① 对拍：文件系统（同一操作序列，两端同结果） ----------

def test_fs_parity_listing(tmp_path, host, vm):
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    _host_run(host, f'输出(建目录("{(tmp_path / "A" / "子").as_posix()}"))')
    _vm_run(f'输出(建目录("{(tmp_path / "B" / "子").as_posix()}"))')
    # 宿主用 写文件，VM 用 _write_file（stdlib 包装与内建原语同名对齐）
    _host_run(host, f'写文件("{(tmp_path / "A" / "f.txt").as_posix()}", "对拍")')
    _vm_run(f'_write_file("{(tmp_path / "B" / "f.txt").as_posix()}", "对拍")')
    lh = _host_run(host, f'输出(列目录("{(tmp_path / "A").as_posix()}"))')[-1]
    lv = _vm_run(f'输出(列目录("{(tmp_path / "B").as_posix()}"))')[-1]
    assert lh == lv
    assert ["f.txt", False, 6] in lh
    assert ["子", True, 0] in lh


def test_fs_parity_read_copy_delete(tmp_path, host, vm):
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    _host_run(host, f'写文件("{(tmp_path / "A" / "x.txt").as_posix()}", "内容123")')
    _vm_run(f'_write_file("{(tmp_path / "B" / "x.txt").as_posix()}", "内容123")')
    ch = _host_run(host, f'输出(读文件("{(tmp_path / "A" / "x.txt").as_posix()}"))')[-1]
    cv = _vm_run(f'输出(_read_file("{(tmp_path / "B" / "x.txt").as_posix()}"))')[-1]
    assert ch == cv == "内容123"
    ah = _host_run(
        host, f'输出(复制文件("{(tmp_path / "A" / "x.txt").as_posix()}")'
              f'("{(tmp_path / "A" / "y.txt").as_posix()}"))')[-1]
    av = _vm_run(
        f'输出(复制文件("{(tmp_path / "B" / "x.txt").as_posix()}")'
        f'("{(tmp_path / "B" / "y.txt").as_posix()}"))')[-1]
    assert ah is True and av is True
    dh = _host_run(host, f'输出(删除路径("{(tmp_path / "A" / "y.txt").as_posix()}"))')[-1]
    dv = _vm_run(f'输出(删除路径("{(tmp_path / "B" / "y.txt").as_posix()}"))')[-1]
    assert dh is True and dv is True
    ph = _host_run(host, f'输出(路径存在("{(tmp_path / "A" / "y.txt").as_posix()}"))')[-1]
    pv = _vm_run(f'输出(路径存在("{(tmp_path / "B" / "y.txt").as_posix()}"))')[-1]
    assert ph is False and pv is False


def test_fs_rename_and_cwd(tmp_path, host, vm):
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    _host_run(host, f'写文件("{(tmp_path / "A" / "old.txt").as_posix()}", "r")')
    _vm_run(f'_write_file("{(tmp_path / "B" / "old.txt").as_posix()}", "r")')
    rh = _host_run(
        host, f'输出(改名("{(tmp_path / "A" / "old.txt").as_posix()}")'
              f'("{(tmp_path / "A" / "new.txt").as_posix()}"))')[-1]
    rv = _vm_run(
        f'输出(改名("{(tmp_path / "B" / "old.txt").as_posix()}")'
        f'("{(tmp_path / "B" / "new.txt").as_posix()}"))')[-1]
    assert rh is True and rv is True
    assert (tmp_path / "A" / "new.txt").exists()
    assert not (tmp_path / "B" / "old.txt").exists()
    ch = _host_run(host, '输出(当前目录())')[-1]
    assert isinstance(ch, str) and len(ch) > 0


# ---------- ② 闭环：执行Matha / 调试Matha ----------

def test_run_matha_host(host):
    assert _host_run(host, '输出(执行Matha("输出(1+2)"))')[-1] == [3]
    assert _host_run(host, '输出(执行Matha("let x = 7 in 输出(x * 2)"))')[-1] == [14]


def test_run_matha_vm():
    assert _vm_run('输出(执行Matha("输出(5*6)"))')[-1] == [30]


def test_run_matha_parity(host, vm):
    src = '输出(执行Matha("输出(2+3)"))'
    h = _host_run(host, src)[-1]
    v = _vm_run(src)[-1]
    assert h == v == [5]


def test_run_matha_error_propagates(host):
    with pytest.raises(RuntimeError, match="执行Matha 错误"):
        _host_run(host, '输出(执行Matha("输出(1/0)"))')


def test_debug_matha_trace_and_snapshot(host):
    snap = _host_run(host, '输出(调试Matha("let 值 = 5 in 输出(值 + 1)"))')[-1]
    assert snap["模式"] == "轨迹+快照"
    assert snap["输出"] == [6]
    assert snap["错误"] == ""
    assert len(snap["轨迹"]) > 0, "逐节点轨迹为空"
    assert any("→" in line or "←" in line or "run" in line for line in snap["轨迹"])
    names = [row[0] for row in snap["变量"]]
    assert "值" in names
    vals = {row[0]: row[1] for row in snap["变量"]}
    assert "5" in vals["值"]


def test_debug_matha_error_captured(host):
    snap = _host_run(host, '输出(调试Matha("输出(1/0)"))')[-1]
    assert snap["错误"] != ""
    assert "ZeroDivision" in snap["错误"] or "除" in snap["错误"]


def test_debug_matha_vm_explicit_rejection():
    with pytest.raises(RuntimeError, match="宿主解释器"):
        _vm_run('输出(调试Matha("输出(1)"))')
    with pytest.raises(RuntimeError, match="显式拒绝"):
        _vm_run('输出(调试Matha("输出(1)"))')


# ---------- ② 闭环：输入行（stdin 注入，两端） ----------

def test_read_line_host(host, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("标准输入行\n"))
    assert _host_run(host, '输出(输入行())')[-1] == "标准输入行"


def test_read_line_vm(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("VM标准输入行\n"))
    assert _vm_run('输出(输入行())')[-1] == "VM标准输入行"


def test_read_line_eof_returns_empty(host, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert _host_run(host, '输出(输入行())')[-1] == ""


# ---------- ② 闭环：取网址/下载文件（file:// 真 urllib） ----------

def test_fetch_and_download_file_url(tmp_path, host):
    page = tmp_path / "page.txt"
    page.write_text("终端网页内容", encoding="utf-8")
    url = page.resolve().as_uri()
    body = _host_run(host, f'输出(取网址("{url}"))')[-1]
    assert body == "终端网页内容"
    ok = _host_run(
        host, f'输出(下载文件("{url}")("{(tmp_path / "dl.bin").as_posix()}"))')[-1]
    assert ok is True
    assert (tmp_path / "dl.bin").read_text(encoding="utf-8") == "终端网页内容"


def test_fetch_url_vm_file_url(tmp_path):
    page = tmp_path / "p2.txt"
    page.write_text("VM取网址", encoding="utf-8")
    url = page.resolve().as_uri()
    assert _vm_run(f'输出(取网址("{url}"))')[-1] == "VM取网址"


def test_fetch_url_missing_file_rejects(tmp_path, host):
    missing = (tmp_path / "不存在.txt").resolve().as_uri()
    with pytest.raises(RuntimeError, match="取网址失败"):
        _host_run(host, f'输出(取网址("{missing}"))')


# ---------- ③ 拒绝：删除路径安全边界 ----------

def test_delete_nonempty_dir_rejected(tmp_path, host):
    d = tmp_path / "非空"
    d.mkdir()
    (d / "内容.txt").write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="递归删除不受支持"):
        _host_run(host, f'输出(删除路径("{d.as_posix()}"))')
    # 目录仍在（未发生部分删除）
    assert d.exists()


def test_delete_nonempty_dir_vm_rejected(tmp_path):
    d = tmp_path / "非空vm"
    d.mkdir()
    (d / "内容.txt").write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="递归删除不受支持"):
        _vm_run(f'输出(删除路径("{d.as_posix()}"))')
    assert d.exists()


def test_delete_missing_path_rejected(tmp_path, host):
    with pytest.raises(RuntimeError, match="路径不存在"):
        _host_run(host, f'输出(删除路径("{(tmp_path / "无此物").as_posix()}"))')
