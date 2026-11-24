# -*- coding: utf-8 -*-
"""阶段 12d：终端独立入口 + .msh 批处理 + matha_main 集成 端到端入门禁。

口径：全部用例走**真 subprocess**（python -m src.matha_term / python -m src.matha_main
终端），无进程内 mock——锁定「可以独立运行，也可以在其它系统终端中运行」的交付面。
三锁纪律：
  ① 对拍：单命令/批处理/REPL 三形态的输出与退出码（0/1 如实）。
  ② 闭环：编写→加载→运行全链经 -c；REPL 错误后继续、退出 标志终止、EOF 退出。
  ③ 拒绝：错误命令如实打印「错误: ...」且退出码 1；缺失脚本/缺 -c 参数如实拒绝；
     未知命令 CMD 式透传真执行、失败显示退出码；重定向经入口真落盘
     （13b 真化，e2e 锁升级：CMD 式静默 + 文件内容核实）；管道经入口真执行
     （13a 真化，e2e 锁升级）。

零跳过，零失败。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PY = sys.executable
_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT)}
_TIMEOUT = 180


def _run(args, stdin=None, cwd=None, env=None):
    return subprocess.run(
        [PY, "-m"] + args,
        input=stdin, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env={**_ENV, **(env or {})}, timeout=_TIMEOUT, cwd=str(cwd or ROOT),
    )


# ---------- ① 对拍：单命令 / 透传 / 退出码 ----------

def test_e2e_c_mode_echo():
    r = _run(["src.matha_term", "-c", "回显 hi"])
    assert r.returncode == 0, r.stderr
    assert "hi" in r.stdout


def test_e2e_c_mode_exit_flag():
    r = _run(["src.matha_term", "-c", "退出"])
    assert r.returncode == 0, r.stderr


def test_e2e_c_mode_error_honest():
    r = _run(["src.matha_term", "-c", "目录 a b"])
    assert r.returncode == 1
    assert "错误:" in r.stdout
    assert "目录: 至多 1 个参数" in r.stdout


def test_e2e_c_mode_passthrough():
    r = _run(["src.matha_term", "-c", "python --version"])
    assert r.returncode == 0, r.stderr
    assert "Python" in r.stdout


def test_e2e_c_mode_passthrough_exit_code():
    r = _run(["src.matha_term", "-c", 'python -c "import sys; sys.exit(3)"'])
    assert r.returncode == 0, "透传失败应显示退出码行而非进程失败"
    assert "命令退出码: 3" in r.stdout


def test_e2e_c_mode_run_matha():
    r = _run(["src.matha_term", "-c", '运行 "输出(1+2)"'])
    assert r.returncode == 0, r.stderr
    assert "3" in r.stdout


def test_e2e_c_mode_debug_host_backend():
    """调试Matha 依赖宿主解释器的逐节点轨迹与环境快照：定向 host 后端可用。

    默认后端已是纯 Matha 链面（阶段 42c），链面上 调试 走显式拒绝（非静默降级），
    拒绝路径锁见 tests/test_selfhost_language_phase42.py。
    """
    r = _run(["src.matha_term", "-c", '调试 "let 值 = 5 in 输出(值 + 1)"'],
             env={"MATHA_TERM_BACKEND": "host"})
    assert r.returncode == 0, r.stderr
    assert "== 轨迹 ==" in r.stdout and "== 输出 ==" in r.stdout and "== 变量 ==" in r.stdout
    assert "6" in r.stdout


def test_e2e_c_mode_redirect_real_pipe(tmp_path):
    r = _run(["src.matha_term", "-c", "回显 hi > out.txt"], cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "", "CMD 式静默：落盘不回显"
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hi\n"
    r = _run(["src.matha_term", "-c", "回显 hi | 查找 h"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "hi" in r.stdout


# ---------- ② 闭环：.msh 批处理 ----------

def test_e2e_batch_clean(tmp_path):
    script = tmp_path / "clean.msh"
    script.write_text(
        "# 注释行\n"
        "\n"
        "回显 第一行\n"
        '运行 "输出(6*7)"\n'
        "回显 末行\n",
        encoding="utf-8")
    r = _run(["src.matha_term", str(script)])
    assert r.returncode == 0, r.stderr
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert lines == ["第一行", "42", "末行"]


def test_e2e_batch_error_continues(tmp_path):
    script = tmp_path / "err.msh"
    script.write_text("回显 前行\n目录 a b\n回显 后行\n", encoding="utf-8")
    r = _run(["src.matha_term", str(script)])
    assert r.returncode == 1
    assert "错误(第 2 行)" in r.stdout
    assert "前行" in r.stdout and "后行" in r.stdout


def test_e2e_batch_exit_flag_stops(tmp_path):
    script = tmp_path / "stop.msh"
    script.write_text("回显 前行\n退出\n回显 不应到达\n", encoding="utf-8")
    r = _run(["src.matha_term", str(script)])
    assert r.returncode == 0, r.stderr
    assert "前行" in r.stdout and "不应到达" not in r.stdout


def test_e2e_batch_write_load_loop(tmp_path):
    """编写→加载→运行 全链经批处理落盘验证。"""
    script = tmp_path / "loop.msh"
    out_matha = (tmp_path / "hello.matha").as_posix()
    script.write_text(
        f'编写 "{out_matha}" "输出(40+2)"\n'
        f'加载 "{out_matha}"\n',
        encoding="utf-8")
    r = _run(["src.matha_term", str(script)])
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "hello.matha").read_text(encoding="utf-8") == "输出(40+2)"
    assert "42" in r.stdout


def test_e2e_missing_script_rejected():
    r = _run(["src.matha_term", "无此脚本.msh"])
    assert r.returncode == 1
    assert "脚本不存在" in r.stdout


def test_e2e_c_missing_arg_rejected():
    r = _run(["src.matha_term", "-c"])
    assert r.returncode == 1
    assert "错误" in r.stdout


# ---------- ② 闭环：交互式 REPL（stdin 管道） ----------

def test_e2e_repl_session():
    stdin = "回显 交互行\npython --version\n目录 a b\n回显 错误后仍继续\n退出\n回显 不应到达\n"
    r = _run(["src.matha_term"], stdin=stdin)
    assert r.returncode == 0, r.stderr
    out = r.stdout.replace("Matha> ", "")
    assert "帮助 查看命令" in out            # 横幅
    assert "交互行" in out
    assert "Python" in out                   # 透传真执行
    assert "错误: 目录: 至多 1 个参数" in out  # 错误如实显示
    assert "错误后仍继续" in out             # 错误后会话继续
    assert "不应到达" not in out             # 退出 标志终止
    assert "Matha>" in r.stdout              # CMD 式提示符存在


def test_e2e_repl_eof_exits():
    r = _run(["src.matha_term"], stdin="")
    assert r.returncode == 0, r.stderr
    assert "帮助 查看命令" in r.stdout


# ---------- ① 对拍：matha_main 集成（终端 / term 双别名） ----------

def test_e2e_matha_main_terminal_zh():
    r = _run(["src.matha_main", "终端", "-c", "回显 集成中文"])
    assert r.returncode == 0, r.stderr
    assert "集成中文" in r.stdout


def test_e2e_matha_main_term_en():
    r = _run(["src.matha_main", "term", "-c", "回显 集成英文"])
    assert r.returncode == 0, r.stderr
    assert "集成英文" in r.stdout


def test_e2e_matha_main_batch(tmp_path):
    script = tmp_path / "via_main.msh"
    script.write_text("回显 经主入口\n", encoding="utf-8")
    r = _run(["src.matha_main", "终端", str(script)])
    assert r.returncode == 0, r.stderr
    assert "经主入口" in r.stdout


def test_e2e_matha_main_term_in_help():
    r = _run(["src.matha_main", "--help"])
    assert r.returncode == 0
    assert "终端" in r.stdout
