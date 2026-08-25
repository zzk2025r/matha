"""Matha 外部语言互操作子系统：双实现对比驱动的自我升级。

让 Matha 能调用其它编程语言（Python 宿主内嵌 + subprocess 通用通道），
核心用途是「双实现对比」——用外部语言构建参考实现，Matha 同时构建一份
等价实现，在沙箱中对比输出，通过则升级 Matha 实现，不通过则回滚。

设计要点：
  - ForeignRunner：执行外部语言代码。
      * Python：宿主内 eval/exec，在独立 globals 命名空间运行（隔离副作用），
        支持「定义函数 + 调用」模式。
      * 其它语言：subprocess 调用解释器，通过临时文件 + JSON I/O 传递参数
        与返回值，进程级隔离。
  - DualComparator：对同一组测试输入，分别调用 Matha 函数与外部函数，
        逐项对比返回值，产出 CompareResult。
  - compare_upgrade：沙箱试运行 Matha 源码 → 在沙箱中对比 → 全通过则 commit，
        任一不一致或出错则 rollback（复用自我升级子系统的安全语义）。

安全模型：复用沙箱隔离。
  - 外部代码在独立命名空间/子进程运行，不污染 Matha 解释器本体。
  - 对比升级的 Matha 试运行在 Sandbox 内进行，失败回滚零污染。
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Optional

from src.interp import Interpreter, MathaRuntimeError
from src.selfupgrade import Sandbox, UpgradeResult


# 支持的外部语言（小写规范化）
_LANG_PYTHON = "python"
_LANG_JS = "javascript"
_LANG_NODE = "node"
_LANG_RUBY = "ruby"

# 语言 → 解释器可执行名（subprocess 模式）
_INTERPRETERS = {
    _LANG_PYTHON: ["python"],
    _LANG_JS: ["node"],
    _LANG_NODE: ["node"],
    _LANG_RUBY: ["ruby"],
}


# ============================================================
# 外部语言执行器
# ============================================================

class ForeignRunner:
    """执行外部编程语言代码。

    Python：宿主内 eval/exec，在独立 globals 中运行（隔离副作用）。
    其它语言：subprocess 调用解释器，JSON 传递输入输出，进程级隔离。
    """

    def eval(self, lang: str, code: str, inputs: Optional[dict] = None) -> Any:
        """求值外部语言代码，返回结果。

        - Python：表达式用 eval 返回值；语句用 exec，返回 None
          （可通过 inputs 注入变量，执行后可从返回的 globals 取值）。
        - 其它语言：整段脚本执行，stdout 尝试 JSON 解析，失败返回原文本。

        Args:
            lang: 语言名（python/javascript/node/ruby）
            code: 源代码
            inputs: 注入到执行环境的变量（仅 Python 模式生效）
        """
        lang = lang.lower()
        if lang == _LANG_PYTHON:
            return self._eval_python(code, inputs)
        return self._eval_subprocess(lang, code, inputs)

    def call(self, lang: str, code: str, func_name: str,
             args: list) -> Any:
        """执行外部代码并调用其中定义的函数，返回函数返回值。

        Python：exec 定义函数后直接调用（宿主内）。
        其它语言：生成「定义 + 调用 + JSON 输出」的 wrapper 脚本，
        subprocess 执行后解析 stdout。

        Args:
            lang: 语言名
            code: 定义函数的源代码
            func_name: 要调用的函数名
            args: 参数列表（会 JSON 序列化传给外部函数）
        """
        lang = lang.lower()
        if lang == _LANG_PYTHON:
            return self._call_python(code, func_name, args)
        return self._call_subprocess(lang, code, func_name, args)

    # ---------- Python 宿主内嵌 ----------

    def _eval_python(self, code: str, inputs: Optional[dict]) -> Any:
        g: dict = {"__builtins__": __builtins__}
        if inputs:
            g.update(inputs)
        try:
            return eval(code, g)
        except SyntaxError:
            exec(code, g)
            return None

    def _call_python(self, code: str, func_name: str, args: list) -> Any:
        g: dict = {"__builtins__": __builtins__}
        exec(code, g)
        if func_name not in g:
            raise MathaRuntimeError(
                f"外部 Python 代码未定义函数 '{func_name}'")
        return g[func_name](*args)

    # ---------- subprocess 通用通道 ----------

    def _eval_subprocess(self, lang: str, code: str,
                         inputs: Optional[dict]) -> Any:
        interp = _INTERPRETERS.get(lang)
        if interp is None:
            raise MathaRuntimeError(f"不支持的语言: {lang}")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=self._ext(lang), delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            path = f.name
        try:
            proc = subprocess.run(
                interp + [path],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode != 0:
                raise MathaRuntimeError(
                    f"外部 {lang} 执行失败: {proc.stderr.strip()[:200]}")
            out = proc.stdout.strip()
            return self._parse_output(out)
        finally:
            os.unlink(path)

    def _call_subprocess(self, lang: str, code: str, func_name: str,
                         args: list) -> Any:
        interp = _INTERPRETERS.get(lang)
        if interp is None:
            raise MathaRuntimeError(f"不支持的语言: {lang}")
        wrapper = self._build_call_wrapper(lang, code, func_name, args)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=self._ext(lang), delete=False, encoding="utf-8"
        ) as f:
            f.write(wrapper)
            path = f.name
        try:
            proc = subprocess.run(
                interp + [path],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode != 0:
                raise MathaRuntimeError(
                    f"外部 {lang} 调用失败: {proc.stderr.strip()[:200]}")
            return self._parse_output(proc.stdout.strip())
        finally:
            os.unlink(path)

    def _build_call_wrapper(self, lang: str, code: str, func_name: str,
                            args: list) -> str:
        """生成「定义函数 + 用 JSON 参数调用 + JSON 输出」的 wrapper。"""
        args_json = json.dumps(args, ensure_ascii=False)
        if lang in (_LANG_JS, _LANG_NODE):
            return (
                f"{code}\n"
                f"const _args = JSON.parse(process.argv[2]);\n"
                f"const _r = {func_name}(..._args);\n"
                f"process.stdout.write(JSON.stringify(_r));\n"
            )
        if lang == _LANG_RUBY:
            return (
                f"require 'json'\n{code}\n"
                f"_args = JSON.parse(ARGV[0])\n"
                f"_r = send(:{func_name}, *_args)\n"
                f"STDOUT.write(_r.to_json)\n"
            )
        if lang == _LANG_PYTHON:
            return (
                f"import json, sys\n{code}\n"
                f"_args = json.loads(sys.argv[1])\n"
                f"_r = {func_name}(*_args)\n"
                f"sys.stdout.write(json.dumps(_r, ensure_ascii=False))\n"
            )
        raise MathaRuntimeError(f"不支持的语言: {lang}")

    @staticmethod
    def _ext(lang: str) -> str:
        return {".py": _LANG_PYTHON, ".js": _LANG_JS, ".rb": _LANG_RUBY,
                _LANG_PYTHON: ".py", _LANG_JS: ".js", _LANG_NODE: ".js",
                _LANG_RUBY: ".rb"}.get(lang, ".txt")

    @staticmethod
    def _parse_output(out: str) -> Any:
        if not out:
            return None
        try:
            return json.loads(out)
        except (json.JSONDecodeError, ValueError):
            return out


# ============================================================
# 双实现对比
# ============================================================

@dataclass
class CompareResult:
    """双实现对比结果。"""
    通过: bool                       # 全部测试输入一致
    总数: int                        # 测试输入数
    一致数: int                      # 一致的输入数
    差异: list = field(default_factory=list)  # 不一致项详情

    def as_dict(self) -> dict:
        return {
            "通过": self.通过,
            "总数": self.总数,
            "一致数": self.一致数,
            "差异数": len(self.差异),
        }


class DualComparator:
    """双实现对比器：Matha 函数 vs 外部语言函数。

    对同一组测试输入，分别调用两个实现，逐项对比返回值。
    """

    def __init__(self, interp: Interpreter, matha_func: str,
                 foreign_lang: str, foreign_code: str):
        self.interp = interp
        self.matha_func = matha_func
        self.foreign_lang = foreign_lang.lower()
        self.foreign_code = foreign_code
        self._runner = ForeignRunner()

    def compare(self, test_cases: list) -> CompareResult:
        """对每个测试输入（参数列表）对比两个实现的返回值。

        Args:
            test_cases: list of arg-lists，如 [[1,2], [3,4]]

        Returns:
            CompareResult
        """
        diffs: list = []
        ok = 0
        for i, args in enumerate(test_cases):
            # Matha 侧
            try:
                m_res = self.interp.call(self.matha_func, *args)
            except Exception as ex:
                m_res = f"<Matha异常: {ex}>"
            # 外部侧
            try:
                f_res = self._runner.call(
                    self.foreign_lang, self.foreign_code,
                    self._foreign_func_name(), args,
                )
            except Exception as ex:
                f_res = f"<外部异常: {ex}>"
            if _values_equal(m_res, f_res):
                ok += 1
            else:
                diffs.append({
                    "输入": args, "Matha结果": m_res, "外部结果": f_res,
                })
        return CompareResult(
            通过=len(diffs) == 0, 总数=len(test_cases),
            一致数=ok, 差异=diffs,
        )

    def _foreign_func_name(self) -> str:
        """外部代码中的函数名：默认与 Matha 函数同名。

        外部代码可能用不同命名（如 snake_case），此处简化为同名；
        若需不同名，可在 foreign_code 中定义后通过子类覆盖。
        """
        return self.matha_func


def _values_equal(a: Any, b: Any) -> bool:
    """对比 Matha 值与外部值是否相等（容忍类型差异）。

    - 数值：直接 == （int/float 互通）
    - 字符串：直接 ==
    - list/tuple：逐元素递归
    - dict：key/value 递归
    - bool 严格区分（True != 1）
    """
    # bool 优先：True 不应等于 1
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_values_equal(a[k], b[k]) for k in a)
    return a == b


# ============================================================
# 对比驱动的自我升级
# ============================================================

def compare_upgrade(parent: Interpreter, matha_src: str,
                    matha_func: str, foreign_lang: str,
                    foreign_code: str, test_cases: list,
                    extra_verify=None) -> UpgradeResult:
    """双实现对比驱动的自我升级。

    流程：
      1. 创建沙箱（克隆本体）
      2. 在沙箱中加载 Matha 源码（试运行）
      3. 运行出错 → rollback，返回失败（本体未触碰）
      4. 在沙箱中用 DualComparator 对比 Matha 函数与外部参考实现
      5. 对比不通过 → rollback，返回失败（含差异详情）
      6. extra_verify 给定时调用，返回假或抛错 → rollback
      7. 全通过 → commit，返回成功（含变更 diff）

    Args:
        parent: 本体解释器
        matha_src: 待升级的 Matha 源码（定义 matha_func）
        matha_func: 要对比的 Matha 函数名
        foreign_lang: 参考实现语言（python/javascript/ruby）
        foreign_code: 参考实现源码（定义同名函数）
        test_cases: 对比用的测试输入列表（每个是参数列表）
        extra_verify: 可选的额外校验 callable(sandbox) -> bool

    Returns:
        UpgradeResult（成功时 输出 含对比摘要，变更 含 diff）
    """
    sb = Sandbox(parent)
    outs, trace, err = sb.run(matha_src)
    if err is not None:
        sb.rollback()
        return UpgradeResult(
            成功=False, 错误=f"Matha 源码加载失败: {err}",
            输出=outs, 追踪=trace, 变更={})
    # 沙箱内对比
    cmp = DualComparator(sb.interp, matha_func, foreign_lang, foreign_code)
    try:
        result = cmp.compare(test_cases)
    except Exception as ex:
        sb.rollback()
        return UpgradeResult(
            成功=False, 错误=f"对比执行异常: {ex}",
            输出=outs, 追踪=trace, 变更={})
    if not result.通过:
        sb.rollback()
        diff_summary = "; ".join(
            f"输入{d['输入']}: Matha={d['Matha结果']!r} vs 外部={d['外部结果']!r}"
            for d in result.差异[:3]
        )
        return UpgradeResult(
            成功=False,
            错误=f"对比不一致（{result.一致数}/{result.总数} 通过）: {diff_summary}",
            输出=outs, 追踪=trace, 变更={})
    # 额外校验
    if extra_verify is not None:
        try:
            ok = extra_verify(sb)
        except Exception as ex:
            sb.rollback()
            return UpgradeResult(
                成功=False, 错误=f"额外校验异常: {ex}",
                输出=outs, 追踪=trace, 变更={})
        if not ok:
            sb.rollback()
            return UpgradeResult(
                成功=False, 错误="额外校验未通过",
                输出=outs, 追踪=trace, 变更={})
    # 全通过 → 提交
    diff = sb.commit()
    return UpgradeResult(
        成功=True, 错误=None,
        输出=outs + [result.as_dict()], 追踪=trace, 变更=diff)
