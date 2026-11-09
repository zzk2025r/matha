# -*- coding: utf-8 -*-
"""阶段 6 锁：matha_system 十处死接线修复 + 门面真委托/显式拒绝。

背景（阶段 6 审计）：_init_package/_init_type_checker/_init_test/
_init_formatter/_init_doc/_init_async/_init_science/_init_visualization/
_init_symbolic/_init_security2 从未被 _init_domains 调用——类属性从未
赋值，门面方法直接 AttributeError，假 dict 回退不可达；其中
install_package/run_test/generate_docs 为纯假返回，hash_password 回退
明文密码（安全隐患）。本轮：十处 init 接入 _init_domains，门面真委托
或 RuntimeError 显式拒绝；顺带根治两个被真接线暴露的目标模块崩溃
（type_checker.check_type 调不存在的 _infer_type；
symbolic._evaluate 对 parse 产出的裸数节点取 .value）。

本文件锁：
  1. 接线防漂移：_init_domains 源码含十处调用；bare 系统真初始化后
     类属性与真实类身份对拍；init 失败分支相关属性全置 None；
  2. 手算对拍：包安装/依赖拓扑、类型检查、测试真跑（失败用例必须
     passed=False）、格式化、文档真扫描、异步真跑、矩阵行列式、
     符号求解、密码哈希/JWT；
  3. 显式拒绝：类缺失 → RuntimeError（全门面参数化）；假对象 →
     TypeError；模块导入炸 → init 不裸抛。
安全纪律：本文件仅使用假密钥（test-key / fake-key-abc）。
"""
from __future__ import annotations

import asyncio
import builtins
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.async_support import AsyncManager  # noqa: E402
from src.code_formatter import MathaFormatter  # noqa: E402
from src.doc_generator import MathaDocGenerator  # noqa: E402
from src.matha_system import MathaSystem  # noqa: E402
from src.package_manager import DependencyResolver, PackageManager  # noqa: E402
from src.science import Array, Dataset, Matrix  # noqa: E402
from src.security_enhanced import (  # noqa: E402
    Certificate, MathaSecurity, OAuth2Client, SSLContext,
)
from src.symbolic import Equation, MathaSymbolic  # noqa: E402
from src.test_framework import MathaTestRunner  # noqa: E402
from src.type_checker import TypeChecker  # noqa: E402
from src.visualization import ChartType, Figure, MathaPlotter  # noqa: E402


def _bare() -> MathaSystem:
    s = MathaSystem.__new__(MathaSystem)
    s.debug = False
    return s


@pytest.fixture()
def sys6() -> MathaSystem:
    s = _bare()
    s._init_domains()
    return s


# ============================================================
# 1. 接线防漂移：十处 init 必须在 _init_domains 主链上
# ============================================================

class TestWiringDriftLock:

    @pytest.mark.parametrize("init_name", [
        "_init_package", "_init_type_checker", "_init_test",
        "_init_formatter", "_init_doc", "_init_async", "_init_science",
        "_init_visualization", "_init_symbolic", "_init_security2",
    ])
    def test_init_domains_calls_init(self, init_name):
        src = inspect.getsource(MathaSystem._init_domains)
        assert f"self.{init_name}()" in src

    @pytest.mark.parametrize("attr,cls", [
        ("package_manager_class", PackageManager),
        ("dependency_resolver_class", DependencyResolver),
        ("type_checker_class", TypeChecker),
        ("test_runner_class", MathaTestRunner),
        ("formatter_class", MathaFormatter),
        ("doc_generator_class", MathaDocGenerator),
        ("async_manager_class", AsyncManager),
        ("array_class", Array),
        ("matrix_class", Matrix),
        ("dataset_class", Dataset),
        ("plotter_class", MathaPlotter),
        ("symbolic_class", MathaSymbolic),
        ("security_class", MathaSecurity),
        ("certificate_class", Certificate),
        ("ssl_context_class", SSLContext),
        ("oauth2_client_class", OAuth2Client),
    ])
    def test_class_attr_is_real_class(self, sys6, attr, cls):
        assert getattr(sys6, attr) is cls

    @pytest.mark.parametrize("module,init_name,attrs", [
        ("src.science", "_init_science",
         ["array_class", "matrix_class", "dataset_class"]),
        ("src.security_enhanced", "_init_security2",
         ["security_class", "certificate_class",
          "ssl_context_class", "oauth2_client_class"]),
        ("src.package_manager", "_init_package",
         ["package_manager_class", "dependency_resolver_class"]),
    ])
    def test_init_failure_sets_all_attrs_none(self, monkeypatch, module,
                                              init_name, attrs):
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == module:
                raise ImportError("模拟导入失败")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        s = _bare()
        getattr(s, init_name)()
        for attr in attrs:
            assert getattr(s, attr) is None


# ============================================================
# 2. 包管理：真安装/真拓扑（手算对拍）
# ============================================================

class TestPackageManager:

    def test_create_returns_real_manager(self, sys6):
        assert isinstance(sys6.create_package_manager(), PackageManager)

    def test_install_registered_hand_value(self, sys6):
        pm = sys6.create_package_manager()
        pm.register_package("foo", "1.0.0")
        r = sys6.install_package(pm, "foo")
        assert r["success"] is True
        assert r["package"] == "foo"
        assert "foo" in r["message"]
        assert pm.list_installed() == {"foo": "1.0.0"}

    def test_install_unregistered_fails_honestly(self, sys6):
        pm = sys6.create_package_manager()
        r = sys6.install_package(pm, "nope")
        assert r["success"] is False
        assert pm.list_installed() == {}

    def test_install_version_mismatch_fails(self, sys6):
        pm = sys6.create_package_manager()
        pm.register_package("foo", "1.0.0")
        assert pm.install("foo", "2.0.0").success is False

    def test_install_pulls_dependency(self, sys6):
        pm = sys6.create_package_manager()
        pm.register_package("bar", "1.0.0")
        pm.register_package("foo", "1.0.0", dependencies={"bar": "1.0.0"})
        r = sys6.install_package(pm, "foo")
        assert r["success"] is True
        assert pm.list_installed() == {"bar": "1.0.0", "foo": "1.0.0"}

    def test_install_fake_pm_rejected(self, sys6):
        with pytest.raises(TypeError, match="install"):
            sys6.install_package(object(), "foo")

    def test_resolve_topological_hand_order(self, sys6):
        ok, order, errors = sys6.resolve_dependencies(
            {"a": ["b"], "b": [], "c": ["a"]})
        assert ok is True and errors == []
        assert order.index("b") < order.index("a") < order.index("c")

    def test_resolve_cycle_detected(self, sys6):
        ok, order, errors = sys6.resolve_dependencies(
            {"a": ["b"], "b": ["a"]})
        assert ok is False
        assert any("循环依赖" in e for e in errors)


# ============================================================
# 3. 类型检查：真检查真推断（含 _infer_type 崩溃回归锁）
# ============================================================

class TestTypeCheckerFacade:

    def test_create_returns_real_checker(self, sys6):
        assert isinstance(sys6.create_type_checker(), TypeChecker)

    @pytest.mark.parametrize("value,expected,ok", [
        (3, "int", True), ("x", "int", False), (True, "bool", True),
        (3, "any", True), (3.5, "float", True), ([1], "list", True),
    ])
    def test_check_type_hand_values(self, sys6, value, expected, ok):
        assert sys6.check_type(value, expected) is ok

    @pytest.mark.parametrize("value,expected", [
        (3, "int"), (3.5, "float"), ("x", "str"), (True, "bool"),
        (None, "None"), ([1], "list"), ({"a": 1}, "dict"),
    ])
    def test_infer_type_hand_values(self, sys6, value, expected):
        assert sys6.infer_type(value) == expected


# ============================================================
# 4. 测试框架：失败用例必须 passed=False（纯假返回清除锁）
# ============================================================

class TestTestRunnerFacade:

    def test_create_returns_real_runner(self, sys6):
        assert isinstance(sys6.create_test_runner(), MathaTestRunner)

    def test_passing_test_reports_true(self, sys6):
        r = sys6.create_test_runner()
        out = sys6.run_test(r, "t_pass", lambda: 1)
        assert out == {"name": "t_pass", "passed": True, "error": None}

    def test_failing_test_reports_false_with_error(self, sys6):
        r = sys6.create_test_runner()
        out = sys6.run_test(r, "t_fail", lambda: 1 / 0)
        assert out["passed"] is False
        assert "ZeroDivisionError" in out["error"]

    def test_same_name_twice_both_truthful(self, sys6):
        r = sys6.create_test_runner()
        assert sys6.run_test(r, "same", lambda: 1)["passed"] is True
        assert sys6.run_test(r, "same", lambda: 2)["passed"] is True

    def test_fake_runner_rejected(self, sys6):
        with pytest.raises(TypeError, match="suite"):
            sys6.run_test(object(), "t", lambda: 1)


# ============================================================
# 5. 格式化/文档/异步：真委托对拍
# ============================================================

class TestFormatterFacade:

    def test_format_strips_trailing_whitespace(self, sys6):
        assert sys6.format_code("x = 1  \n") == "x = 1\n"

    def test_format_parity_with_direct_formatter(self, sys6):
        code = "x = 1  \ny  =  2\n"
        assert sys6.format_code(code) == \
            MathaFormatter().format(code).formatted_code


class TestDocGeneratorFacade:

    def test_generate_docs_scans_real_module(self, sys6):
        import src.symbolic as mod
        dg = sys6.create_doc_generator()
        doc = sys6.generate_docs(dg, mod)
        assert "differentiate" in doc
        assert "solve_equation" in doc
        assert "求导" in doc

    def test_generate_docs_parity_with_direct(self, sys6):
        import src.symbolic as mod
        dg = MathaDocGenerator()
        dg.scan_module(mod)
        assert sys6.generate_docs(sys6.create_doc_generator(), mod) == \
            dg.generate_markdown()

    def test_fake_doc_generator_rejected(self, sys6):
        with pytest.raises(TypeError, match="scan_module"):
            sys6.generate_docs(object(), sys)

    def test_partial_doc_generator_rejected(self, sys6):
        class Half:
            def scan_module(self, module):
                return []
        with pytest.raises(TypeError, match="generate_markdown"):
            sys6.generate_docs(Half(), sys)


class TestAsyncFacade:

    def test_run_async_returns_coro_result(self, sys6):
        async def coro():
            return 42
        assert asyncio.run(sys6.run_async(coro())) == 42

    def test_run_async_propagates_exception(self, sys6):
        async def boom():
            raise ValueError("boom")
        with pytest.raises(ValueError, match="boom"):
            asyncio.run(sys6.run_async(boom()))

    def test_run_async_absent_class_rejected(self):
        s = _bare()
        s.async_manager_class = None

        async def coro():
            return 1
        c = coro()
        with pytest.raises(RuntimeError, match="异步"):
            asyncio.run(s.run_async(c))
        c.close()


# ============================================================
# 6. 科学计算/可视化/符号：手算对拍
# ============================================================

class TestScienceFacade:

    def test_array_hand_values(self, sys6):
        a = sys6.create_array([1, 2, 3])
        assert isinstance(a, Array)
        assert a.sum() == 6 and a.mean() == 2

    def test_matrix_determinant_hand_value(self, sys6):
        m = sys6.create_matrix([[1, 2], [3, 4]])
        assert isinstance(m, Matrix)
        assert m.determinant() == -2

    def test_dataset_column_and_describe(self, sys6):
        ds = sys6.create_dataset(["a", "b"], [[1, 2], [3, 4]])
        assert isinstance(ds, Dataset)
        assert ds["a"] == [1, 3]
        assert len(ds) == 2
        assert ds.describe()["a"]["mean"] == 2


class TestVisualizationFacade:

    @pytest.mark.parametrize("method,chart", [
        ("plot_line", ChartType.LINE),
        ("plot_bar", ChartType.BAR),
        ("plot_scatter", ChartType.SCATTER),
    ])
    def test_plot_returns_real_figure(self, sys6, method, chart):
        fig = getattr(sys6, method)([1, 2], [3, 4], "t")
        assert isinstance(fig, Figure)
        assert fig.chart_type is chart
        assert fig.title == "t"
        assert fig.data[0].x == [1, 2] and fig.data[0].y == [3, 4]

    def test_create_plotter_real(self, sys6):
        assert isinstance(sys6.create_plotter(), MathaPlotter)


class TestSymbolicFacade:

    def test_create_symbolic_real(self, sys6):
        assert isinstance(sys6.create_symbolic(), MathaSymbolic)

    def test_diff_symbol_hand_value(self, sys6):
        eng = sys6.create_symbolic()
        d = sys6.differentiate(eng.parse("x"), "x")
        assert d.operator == "number" and d.operands == [1]

    def test_diff_constant_hand_value(self, sys6):
        eng = sys6.create_symbolic()
        d = sys6.differentiate(eng.parse("5"), "x")
        assert d.operator == "number" and d.operands == [0]

    def test_diff_power_parity_with_direct(self, sys6):
        eng = sys6.create_symbolic()
        expr = eng.parse("x^2")
        assert repr(sys6.differentiate(expr, "x")) == \
            repr(MathaSymbolic().diff(expr, "x"))

    def test_solve_linear_hand_value(self, sys6):
        eng = sys6.create_symbolic()
        eq = Equation(left=eng.parse("x-2"), variable="x")
        sols = sys6.solve_equation(eq)
        assert len(sols) == 1
        assert sols[0] == pytest.approx(2.0)


# ============================================================
# 7. 安全增强：真哈希/真 JWT（仅假密钥）
# ============================================================

class TestSecurityFacade:

    def test_hash_password_not_plaintext(self, sys6):
        h = sys6.hash_password("fake-key-abc")
        assert h != "fake-key-abc"
        salt, sep, dk = h.partition("$")
        assert sep and len(salt) == 32 and len(dk) == 64
        int(salt, 16)  # 真 pbkdf2 hex（阶段 7 起盐嵌入格式）
        int(dk, 16)

    def test_hash_password_salted(self, sys6):
        assert sys6.hash_password("fake-key-abc") != \
            sys6.hash_password("fake-key-abc")

    def test_generate_jwt_parity_with_direct(self, sys6):
        jwt = sys6.generate_jwt({"sub": "u"}, "test-key")
        assert jwt.count(".") == 2
        assert jwt == MathaSecurity().generate_jwt({"sub": "u"}, "test-key")

    def test_generate_certificate_fields(self, sys6):
        cert = sys6.generate_certificate("subj", "issuer")
        assert isinstance(cert, Certificate)
        assert cert.subject == "subj" and cert.issuer == "issuer"
        assert len(cert.fingerprint) == 64

    def test_create_oauth2_client_fields(self, sys6):
        c = sys6.create_oauth2_client("cid", "test-key",
                                      "http://localhost/cb")
        assert isinstance(c, OAuth2Client)
        assert c.client_id == "cid"


# ============================================================
# 8. 显式拒绝：类缺失 → RuntimeError（全门面参数化）
# ============================================================

class TestAbsentClassRejection:

    @pytest.mark.parametrize("attrs,call", [
        (["package_manager_class"], lambda s: s.create_package_manager()),
        (["dependency_resolver_class"],
         lambda s: s.resolve_dependencies({})),
        (["type_checker_class"], lambda s: s.create_type_checker()),
        (["type_checker_class"], lambda s: s.check_type(1, "int")),
        (["type_checker_class"], lambda s: s.infer_type(1)),
        (["test_runner_class"], lambda s: s.create_test_runner()),
        (["formatter_class"], lambda s: s.create_formatter()),
        (["formatter_class"], lambda s: s.format_code("x")),
        (["doc_generator_class"], lambda s: s.create_doc_generator()),
        (["async_manager_class"], lambda s: s.create_async_manager()),
        (["array_class"], lambda s: s.create_array([1])),
        (["matrix_class"], lambda s: s.create_matrix([[1]])),
        (["dataset_class"], lambda s: s.create_dataset(["a"], [[1]])),
        (["plotter_class"], lambda s: s.create_plotter()),
        (["plotter_class"], lambda s: s.plot_line([1], [2])),
        (["plotter_class"], lambda s: s.plot_bar([1], [2])),
        (["plotter_class"], lambda s: s.plot_scatter([1], [2])),
        (["symbolic_class"], lambda s: s.create_symbolic()),
        (["symbolic_class"], lambda s: s.differentiate(None)),
        (["symbolic_class"], lambda s: s.solve_equation(None)),
        (["security_class"], lambda s: s.create_security()),
        (["security_class"], lambda s: s.generate_certificate("s", "i")),
        (["security_class"], lambda s: s.hash_password("fake-key-abc")),
        (["security_class"],
         lambda s: s.create_oauth2_client("c", "test-key", "u")),
        (["security_class"], lambda s: s.generate_jwt({}, "test-key")),
    ])
    def test_absent_class_raises_runtime_error(self, attrs, call):
        s = _bare()
        for attr in attrs:
            setattr(s, attr, None)
        with pytest.raises(RuntimeError, match="不可用"):
            call(s)