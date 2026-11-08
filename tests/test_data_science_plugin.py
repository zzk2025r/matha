# -*- coding: utf-8 -*-
"""数据科学领域插件行为级门禁锁（阶段 1 · AI 修复）。

背景：`src/domains/data_science.py` 历史上是假实现——load_csv 不读文件
恒 True、split 返回 (self,self)、normalize/one_hot 空 pass、
precision/recall/f1 恒 0.0、confusion_matrix 恒 [[0]]、注册层「准确率」
恒 0.0。本轮重写为纯标准库真实现，本文件三类锁封死回退：

  1. **手算对拍**：CSV 真读、切分精确切片、min-max 逐元素、独热按首次
     出现顺序、五个评估指标与独立手算逐位比对；
  2. **显式拒绝**：空文件/参差不齐/非数值单元格/常量列/空数据集/
     非法比例/多分类标签进二分类指标/select_k_best 一律如实抛错；
  3. **注册契约**：manifest 符号面不漂移、柯里化注册形态（Matha
     f(a,b) 两侧均为 f(a)(b)，零参 f() 传 0）。

另有主执行链端到端锁（干净子进程经 exec_api 懒加载真算/拒绝，
遵「sys.modules 断言起子进程」纪律）。阶段 3 补管线闭环锁（第 5 节）：
load→split→normalize→one_hot→metrics 链式手算，标签随切分走、
独热列序按各自首次出现、切片互为独立拷贝。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.domains.data_science import (  # noqa: E402
    Dataset,
    DataScienceManager,
    FeatureExtractor,
    ModelEvaluation,
    _data_science_symtab_names,
    _register_data_science,
    create_data_science,
)

MANIFEST = ROOT / "src" / "domains" / "manifest.json"


def _csv(tmp_path: Path, text: str) -> str:
    p = tmp_path / "data.csv"
    p.write_text(text, encoding="utf-8")
    return str(p)


# ============================================================
# 1. 手算对拍（封死假值）
# ============================================================

class TestDatasetHandComputed:

    def test_load_csv_reads_real_values(self, tmp_path):
        ds = Dataset(features=2, samples=3)
        assert ds.load_csv(_csv(tmp_path, "1,2\n3,4\n5,6\n")) is True
        assert ds._data == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        assert ds.features == 2 and ds.samples == 3
        # 反恒 True 病理：换内容必须换数据
        ds2 = Dataset()
        ds2.load_csv(_csv(tmp_path, "9,8\n7,6\n"))
        assert ds2._data == [[9.0, 8.0], [7.0, 6.0]]
        assert ds2.samples == 2

    def test_load_csv_label_column_keeps_raw_strings(self, tmp_path):
        ds = Dataset()
        ds.load_csv(_csv(tmp_path, "1,2,cat\n3,4,dog\n5,6,cat\n"),
                    label_column=2)
        assert ds._data == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        assert ds._labels == ["cat", "dog", "cat"]
        assert ds.features == 2

    def test_split_exact_slices_and_new_objects(self, tmp_path):
        ds = Dataset(name="d")
        ds.load_csv(_csv(tmp_path, "1,0\n2,1\n3,0\n4,1\n5,0\n"),
                    label_column=1)
        train, test = ds.split_train_test(0.6)
        assert train is not ds and test is not ds  # 反 (self,self) 病理
        assert train._data == [[1.0], [2.0], [3.0]]
        assert test._data == [[4.0], [5.0]]
        assert train._labels == ["0", "1", "0"]
        assert test._labels == ["1", "0"]
        assert train.samples == 3 and test.samples == 2
        train._data[0][0] = 99.0  # 切片须为拷贝
        assert ds._data[0][0] == 1.0

    def test_normalize_min_max_hand_computed(self, tmp_path):
        ds = Dataset()
        ds.load_csv(_csv(tmp_path, "1,2\n3,4\n5,6\n"))
        assert ds.normalize() is None
        assert ds._data == [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]

    def test_one_hot_first_appearance_order(self, tmp_path):
        ds = Dataset()
        ds.load_csv(_csv(tmp_path, "1,cat\n2,dog\n3,cat\n4,bird\n"),
                    label_column=1)
        ds.one_hot_encode()
        assert ds.encoded_labels == [
            [1, 0, 0], [0, 1, 0], [1, 0, 0], [0, 0, 1]]


class TestMetricsHandComputed:

    def setup_method(self):
        self.me = ModelEvaluation()
        # TN=2 FP=0 FN=1 TP=2
        self.t = [1, 1, 0, 0, 1]
        self.p = [1, 0, 0, 0, 1]

    def test_all_five_metrics_match_hand_computation(self):
        assert self.me.accuracy(self.t, self.p) == 0.8
        assert self.me.precision(self.t, self.p) == 1.0
        assert self.me.recall(self.t, self.p) == pytest.approx(2 / 3)
        assert self.me.f1_score(self.t, self.p) == pytest.approx(0.8)
        assert self.me.confusion_matrix(self.t, self.p) == [[2, 0], [1, 2]]

    def test_zero_division_convention_is_defined_behavior(self):
        # 无预测正例：precision=0；无 TP：recall=0、f1=0（sklearn 同口径）
        assert self.me.precision([1, 0], [0, 0]) == 0.0
        assert self.me.recall([1, 0], [0, 0]) == 0.0
        assert self.me.f1_score([1, 0], [0, 0]) == 0.0
        assert self.me.confusion_matrix([1, 0], [0, 0]) == [[1, 0], [1, 0]]

    def test_perfect_prediction(self):
        t = [1, 0, 1]
        assert self.me.precision(t, t) == 1.0
        assert self.me.recall(t, t) == 1.0
        assert self.me.f1_score(t, t) == 1.0
        assert self.me.confusion_matrix(t, t) == [[1, 0], [0, 2]]

    def test_accuracy_accepts_multiclass_labels(self):
        assert self.me.accuracy(["a", "b", "c"],
                                ["a", "x", "c"]) == pytest.approx(2 / 3)

    def test_extract_real_numeric_cast(self):
        fe = FeatureExtractor()
        assert fe.extract([1, 2.5, 3]) == [1.0, 2.5, 3.0]


# ============================================================
# 2. 显式拒绝（封死静默占位）
# ============================================================

class TestExplicitRejection:

    def test_load_csv_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Dataset().load_csv(str(tmp_path / "nope.csv"))

    @pytest.mark.parametrize("text", ["", "\n", "1,2\n3\n", "1,x\n", "1,2\n\n"])
    def test_load_csv_bad_content_rejected(self, tmp_path, text):
        with pytest.raises(ValueError):
            Dataset().load_csv(_csv(tmp_path, text))

    @pytest.mark.parametrize("col", [-1, 2, 1.5, True, "1"])
    def test_load_csv_bad_label_column_rejected(self, tmp_path, col):
        with pytest.raises(ValueError):
            Dataset().load_csv(_csv(tmp_path, "1,2\n3,4\n"), label_column=col)

    def test_load_csv_label_column_needs_feature_left(self, tmp_path):
        with pytest.raises(ValueError):
            Dataset().load_csv(_csv(tmp_path, "1\n2\n"), label_column=0)

    @pytest.mark.parametrize("ratio", [0.0, 1.0, 1.5, -0.1, "0.8", True])
    def test_split_bad_ratio_rejected(self, tmp_path, ratio):
        ds = Dataset()
        ds.load_csv(_csv(tmp_path, "1\n2\n3\n4\n5\n"))
        with pytest.raises(ValueError):
            ds.split_train_test(ratio)

    def test_split_empty_dataset_rejected(self):
        with pytest.raises(ValueError, match="为空"):
            Dataset().split_train_test(0.8)

    def test_split_one_side_empty_rejected(self, tmp_path):
        ds = Dataset()
        ds.load_csv(_csv(tmp_path, "1\n2\n3\n4\n5\n"))
        with pytest.raises(ValueError, match="一侧为空"):
            ds.split_train_test(0.01)  # floor(5*0.01)=0
        ds1 = Dataset()
        ds1.load_csv(_csv(tmp_path, "1\n"))
        with pytest.raises(ValueError, match="一侧为空"):
            ds1.split_train_test(0.8)

    def test_normalize_empty_rejected(self):
        with pytest.raises(ValueError, match="为空"):
            Dataset().normalize()

    def test_normalize_constant_column_rejected(self, tmp_path):
        ds = Dataset()
        ds.load_csv(_csv(tmp_path, "1,5\n1,7\n"))
        with pytest.raises(ValueError, match="常量"):
            ds.normalize()

    def test_one_hot_without_labels_rejected(self):
        with pytest.raises(ValueError, match="无标签"):
            Dataset().one_hot_encode()

    @pytest.mark.parametrize("bad", [0, -1, 2.5, True, "3"])
    def test_dataset_bad_metadata_rejected(self, bad):
        with pytest.raises(ValueError):
            Dataset(features=bad)
        with pytest.raises(ValueError):
            Dataset(samples=bad)

    @pytest.mark.parametrize("data", ["12", [1, "x"], [1, None], [True]])
    def test_extract_bad_input_rejected(self, data):
        with pytest.raises(ValueError):
            FeatureExtractor().extract(data)

    def test_select_k_best_rejected(self):
        with pytest.raises(NotImplementedError, match="select_k_best"):
            FeatureExtractor().select_k_best(3)

    @pytest.mark.parametrize("t,p", [
        ([], []), ([1], []), ([1, 0], [1]), ("10", "10"),
        ([0, 1, 2], [0, 1, 2]), ([True, False], [True, False]),
        ([1.0, 0.0], [1.0, 0.0]), (["1", "0"], ["1", "0"]),
    ])
    def test_binary_metrics_reject_bad_labels(self, t, p):
        me = ModelEvaluation()
        for fn in (me.precision, me.recall, me.f1_score, me.confusion_matrix):
            with pytest.raises(ValueError):
                fn(t, p)

    @pytest.mark.parametrize("t,p", [([], []), ([1], []), ("10", "10")])
    def test_accuracy_rejects_empty_and_mismatch(self, t, p):
        with pytest.raises(ValueError):
            ModelEvaluation().accuracy(t, p)


# ============================================================
# 3. 注册契约（manifest 符号面 + 柯里化形态）
# ============================================================

class TestRegistrationContract:

    def test_manifest_symbols_match_exports(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        plugins = (manifest["plugins"]
                   if isinstance(manifest, dict) and "plugins" in manifest
                   else manifest)
        entry = next(p for p in plugins
                     if p.get("module") == "src.domains.data_science")
        builtins: dict = {}
        _register_data_science(builtins)
        assert set(entry["symbols"]) == set(_data_science_symtab_names())
        assert set(entry["symbols"]) == set(builtins)

    def test_curried_forms(self, tmp_path):
        b: dict = {}
        _register_data_science(b)
        assert isinstance(b["创建数据科学"](0), DataScienceManager)
        ds = b["创建数据集"]("d")(2)(5)
        assert isinstance(ds, Dataset) and ds.features == 2 and ds.samples == 5
        assert isinstance(b["创建特征提取器"](0), FeatureExtractor)
        assert isinstance(b["评估模型"](0), ModelEvaluation)
        # 反恒 0.0 病理：注册层准确率必须真算
        assert b["准确率"]([1, 1, 0])([1, 0, 0]) == pytest.approx(2 / 3)
        assert b["加载CSV"](ds)(_csv(tmp_path, "1,2\n3,4\n")) is True
        assert ds._data == [[1.0, 2.0], [3.0, 4.0]]
        assert b["归一化"](ds) is None
        assert ds._data == [[0.0, 0.0], [1.0, 1.0]]
        train, test = b["划分训练测试"](ds)(0.5)
        assert train._data == [[0.0, 0.0]] and test._data == [[1.0, 1.0]]

    def test_manager_factories_track_instances(self):
        m = create_data_science()
        ds = m.create_dataset("d", 2, 5)
        fe = m.create_feature_extractor()
        me = m.evaluate_model()
        assert m._datasets == [ds] and m._feature_extractors == [fe]
        assert m._evaluations == [me]


# ============================================================
# 4. 主执行链端到端（干净子进程，懒加载真算）
# ============================================================

_E2E_SNIPPET = """
import json, sys
sys.path.insert(0, %r)
from src.kernel import exec_api
from src.plugin_api import get_resolver
src = '''@：【加载领域】，数据科学
#1：[准确率([1, 1, 0, 0, 1], [1, 0, 0, 0, 1])]
'''
out = exec_api.run(src)
v = out[-1]
assert isinstance(v, (int, float)) and abs(v - 0.8) < 1e-12, out
assert "data_science" in get_resolver().loaded()
print(json.dumps({"out": v}))
""" % str(ROOT)


def test_main_chain_lazy_loads_and_computes_for_real():
    proc = subprocess.run([sys.executable, "-c", _E2E_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["out"] == pytest.approx(0.8)


_E2E_REJECT_SNIPPET = """
import sys
sys.path.insert(0, %r)
from src.kernel import exec_api
src = '''@：【加载领域】，数据科学
ds = 创建数据集("d", 2, 5)
划分训练测试(ds, 0.8)
'''
try:
    exec_api.run(src)
except ValueError as e:
    assert "为空" in str(e)
    print("REJECTED")
else:
    raise AssertionError("空数据集切分假成功复活：未抛 ValueError")
""" % str(ROOT)


def test_main_chain_surfaces_honest_rejection():
    proc = subprocess.run([sys.executable, "-c", _E2E_REJECT_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "REJECTED" in proc.stdout


# ============================================================
# 5. 阶段 3 · 管线闭环（load→split→normalize→one_hot→metrics 链式手算）
# ============================================================

class TestPipelineClosedLoop:
    """单步手算已由第 1 节锁定；本节锁「链路数据流」：标签随切分走、
    归一化不动标签、独热列序按各自首次出现、指标消费派生标签闭环。"""

    def test_full_pipeline_hand_computed(self, tmp_path):
        ds = Dataset("d", 2, 6)
        assert ds.load_csv(_csv(tmp_path,
                                "1,10,cat\n2,20,dog\n3,30,cat\n"
                                "4,40,dog\n5,50,cat\n6,60,dog\n"),
                           label_column=2) is True
        assert ds._labels == ["cat", "dog", "cat", "dog", "cat", "dog"]
        train, test = ds.split_train_test(0.5)
        assert train._data == [[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]]
        assert test._data == [[4.0, 40.0], [5.0, 50.0], [6.0, 60.0]]
        assert train._labels == ["cat", "dog", "cat"]
        assert test._labels == ["dog", "cat", "dog"]
        train.normalize()
        test.normalize()
        assert train._data == [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
        assert test._data == [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
        # 归一化原地动特征、不动标签
        assert train._labels == ["cat", "dog", "cat"]
        train.one_hot_encode()
        test.one_hot_encode()
        assert train.encoded_labels == [[1, 0], [0, 1], [1, 0]]
        # 独热列序按各自首次出现：test 首标签是 dog → 列序 [dog, cat]
        assert test.encoded_labels == [[1, 0], [0, 1], [1, 0]]
        # 指标闭环：y_true 由 test 标签派生（cat=0, dog=1），模拟模型输出 [1,0,0]
        y_true = [1 if v == "dog" else 0 for v in test._labels]
        assert y_true == [1, 0, 1]
        y_pred = [1, 0, 0]
        me = ModelEvaluation()
        assert me.accuracy(y_true, y_pred) == pytest.approx(2 / 3)
        assert me.precision(y_true, y_pred) == 1.0
        assert me.recall(y_true, y_pred) == 0.5
        assert me.f1_score(y_true, y_pred) == pytest.approx(2 / 3)
        assert me.confusion_matrix(y_true, y_pred) == [[1, 0], [1, 1]]

    def test_split_slices_are_independent_copies(self, tmp_path):
        ds = Dataset("d", 1, 4)
        ds.load_csv(_csv(tmp_path, "1\n2\n3\n4\n"))
        train, test = ds.split_train_test(0.5)
        train.normalize()
        assert train._data == [[0.0], [1.0]]
        assert test._data == [[3.0], [4.0]]
        assert ds._data == [[1.0], [2.0], [3.0], [4.0]]

    def test_manager_pipeline_chain(self, tmp_path):
        m = create_data_science()
        ds = m.create_dataset("d", 2, 4)
        ds.load_csv(_csv(tmp_path, "1,a\n2,b\n3,a\n4,b\n"), label_column=1)
        train, _test = ds.split_train_test(0.5)
        train.one_hot_encode()
        assert train.encoded_labels == [[1, 0], [0, 1]]
        me = m.evaluate_model()
        assert me.accuracy([0, 1], [0, 1]) == 1.0
        assert m._datasets == [ds] and m._evaluations == [me]