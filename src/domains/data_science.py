# -*- coding: utf-8 -*-
"""Matha 数据科学领域插件：数据集/预处理/模型评估（纯标准库真实现）。

【定位 2026-11 · 阶段 1 AI 修复】历史上 load_csv 不读文件恒 True、
split 返回 (self, self)、normalize/one_hot 空 pass、precision/recall/f1
恒 0.0、confusion_matrix 恒 [[0]]、注册层「准确率」恒 0.0，属假实现。
本轮全部重写为可手算对拍的真实现；无背书实现的能力（select_k_best
特征选择）显式拒绝，不返回假特征名。行为级锁见
tests/test_data_science_plugin.py（手算对拍/显式拒绝/注册契约/主链 e2e；
阶段 3 补管线闭环：load→split→normalize→one_hot→metrics 链式手算）。

口径：二分类指标仅支持 {0,1} 标签，零分母按 sklearn zero_division=0
约定返 0.0（定义行为，非占位）；训练有效性主张不背书
（docs/KNOWN_ISSUES.md §7c）。
"""
from __future__ import annotations

import csv
from typing import Any


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class Dataset:
    """数值 CSV 数据集：加载/切分/归一化/标签独热。

    features/samples 构造参数仅为申报元数据，load_csv 后以实际为准。
    """

    def __init__(self, name: str = "dataset",
                 features: int = 10, samples: int = 100):
        for cname, v in (("features", features), ("samples", samples)):
            if not isinstance(v, int) or isinstance(v, bool) or v < 1:
                raise ValueError(f"{cname} 须为正整数：{v!r}")
        self.name = name
        self.features = features
        self.samples = samples
        self._data: list[list[float]] = []
        self._labels: list[Any] = []
        self.encoded_labels: list[list[int]] = []

    def load_csv(self, path: str, label_column: int | None = None) -> bool:
        """读数值 CSV。每行等宽、单元格可转 float，否则如实抛错。

        label_column 指定时该列作为分类标签（保留原始字符串），
        其余列为特征；文件不存在抛 FileNotFoundError，不伪装成功。
        """
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows or all(not r for r in rows):
            raise ValueError(f"CSV 为空：{path}")
        width = len(rows[0])
        if width == 0:
            raise ValueError(f"CSV 首行为空：{path}")
        if label_column is not None:
            if (not isinstance(label_column, int)
                    or isinstance(label_column, bool)
                    or not 0 <= label_column < width):
                raise ValueError(
                    f"label_column 须在 [0, {width}) 内：{label_column!r}")
            if width < 2:
                raise ValueError("指定标签列后须至少剩一列特征")
        data: list[list[float]] = []
        labels: list[Any] = []
        for i, row in enumerate(rows):
            if len(row) != width:
                raise ValueError(
                    f"CSV 第 {i + 1} 行宽度 {len(row)} ≠ 首行 {width}")
            feat = []
            for j, cell in enumerate(row):
                if j == label_column:
                    labels.append(cell)
                    continue
                try:
                    feat.append(float(cell))
                except ValueError:
                    raise ValueError(
                        f"CSV 第 {i + 1} 行第 {j + 1} 列非数值：{cell!r}") from None
            data.append(feat)
        self._data = data
        self._labels = labels
        self.encoded_labels = []
        self.features = len(data[0])
        self.samples = len(data)
        return True

    def split_train_test(self, ratio: float = 0.8
                         ) -> tuple[Dataset, Dataset]:
        """顺序切分（确定性，无洗牌）：前 floor(n*ratio) 行训练，其余测试。

        返回两个新 Dataset（数据切片拷贝），两侧均须非空。
        """
        if not _is_number(ratio) or not 0.0 < ratio < 1.0:
            raise ValueError(f"切分比例须在 (0, 1) 内：{ratio!r}")
        if not self._data:
            raise ValueError("数据集为空，请先 加载CSV")
        n = len(self._data)
        n_train = int(n * ratio)
        if n_train < 1 or n_train >= n:
            raise ValueError(
                f"样本数 {n} 按比例 {ratio} 切分后必有一侧为空")
        train = Dataset(f"{self.name}_train", self.features, n_train)
        test = Dataset(f"{self.name}_test", self.features, n - n_train)
        train._data = [list(r) for r in self._data[:n_train]]
        test._data = [list(r) for r in self._data[n_train:]]
        if self._labels:
            train._labels = list(self._labels[:n_train])
            test._labels = list(self._labels[n_train:])
        return train, test

    def normalize(self) -> None:
        """逐列 min-max 归一化到 [0,1]（原地）。常量列范围无定义，显式拒绝。"""
        if not self._data:
            raise ValueError("数据集为空，请先 加载CSV")
        for j in range(self.features):
            col = [row[j] for row in self._data]
            lo, hi = min(col), max(col)
            if hi == lo:
                raise ValueError(
                    f"第 {j + 1} 列为常量 {lo}，min-max 范围无定义")
            for row in self._data:
                row[j] = (row[j] - lo) / (hi - lo)

    def one_hot_encode(self) -> None:
        """标签独热编码到 encoded_labels（按首次出现顺序定列，确定性）。"""
        if not self._labels:
            raise ValueError("无标签可编码（加载CSV 时请指定 label_column）")
        order: list[Any] = []
        for v in self._labels:
            if v not in order:
                order.append(v)
        self.encoded_labels = [
            [1 if v == c else 0 for c in order] for v in self._labels
        ]


class FeatureExtractor:
    """特征提取器。extract 为数值化 cast；特征选择无背书实现，显式拒绝。"""

    def extract(self, data: list[Any]) -> list[float]:
        """提取特征（数值 cast，非数值如实抛错）。"""
        if not isinstance(data, (list, tuple)):
            raise ValueError("extract 输入须为列表")
        out = []
        for i, x in enumerate(data):
            if not _is_number(x):
                raise ValueError(f"第 {i + 1} 个元素非数值：{x!r}")
            out.append(float(x))
        return out

    def select_k_best(self, k: int) -> list[str]:
        """选择最佳特征。仓库无背书的选择算法/评分准则，显式拒绝。"""
        raise NotImplementedError(
            "select_k_best 未实现（仓库无背书的特征选择算法）；"
            "请用 extract 做数值化特征提取")


def _check_pair(y_true: list, y_pred: list) -> None:
    if not isinstance(y_true, (list, tuple)) or not isinstance(y_pred, (list, tuple)):
        raise ValueError("标签须为列表")
    if not y_true:
        raise ValueError("标签为空")
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"标签数不一致：{len(y_true)} ≠ {len(y_pred)}")


def _check_labels(y_true: list, y_pred: list) -> None:
    _check_pair(y_true, y_pred)
    for name, ys in (("y_true", y_true), ("y_pred", y_pred)):
        for v in ys:
            if isinstance(v, bool) or not isinstance(v, int) or v not in (0, 1):
                raise ValueError(
                    f"{name} 仅支持二分类 {{0,1}} 标签：{v!r}")


def _binary_counts(y_true: list, y_pred: list) -> tuple[int, int, int, int]:
    """返回 (TN, FP, FN, TP)，正类为 1。"""
    _check_labels(y_true, y_pred)
    tn = fp = fn = tp = 0
    for t, p in zip(y_true, y_pred):
        if t == 1 and p == 1:
            tp += 1
        elif t == 1:
            fn += 1
        elif p == 1:
            fp += 1
        else:
            tn += 1
    return tn, fp, fn, tp


class ModelEvaluation:
    """模型评估：accuracy 接受任意可判等标签；precision/recall/f1/混淆矩阵
    限二分类 {0,1}（正类为 1）。

    零分母约定（sklearn zero_division=0 同口径）：无预测正例时
    precision=0.0，无真实正例时 recall=0.0，P+R=0 时 f1=0.0。
    """

    def accuracy(self, y_true: list, y_pred: list) -> float:
        """准确率（任意可判等标签，不限二分类）。"""
        _check_pair(y_true, y_pred)
        return sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)

    def precision(self, y_true: list, y_pred: list) -> float:
        """精确率 TP/(TP+FP)。"""
        _, fp, _, tp = _binary_counts(y_true, y_pred)
        return tp / (tp + fp) if tp + fp else 0.0

    def recall(self, y_true: list, y_pred: list) -> float:
        """召回率 TP/(TP+FN)。"""
        _, _, fn, tp = _binary_counts(y_true, y_pred)
        return tp / (tp + fn) if tp + fn else 0.0

    def f1_score(self, y_true: list, y_pred: list) -> float:
        """F1 = 2PR/(P+R)。"""
        p = self.precision(y_true, y_pred)
        r = self.recall(y_true, y_pred)
        return 2 * p * r / (p + r) if p + r else 0.0

    def confusion_matrix(self, y_true: list, y_pred: list) -> list[list[int]]:
        """混淆矩阵 [[TN, FP], [FN, TP]]（sklearn 布局）。"""
        tn, fp, fn, tp = _binary_counts(y_true, y_pred)
        return [[tn, fp], [fn, tp]]


class DataScienceManager:
    """数据科学管理器（工厂）。"""

    def __init__(self):
        self._datasets: list[Dataset] = []
        self._feature_extractors: list[FeatureExtractor] = []
        self._evaluations: list[ModelEvaluation] = []

    def create_dataset(self, name: str = "dataset",
                          features: int = 10,
                          samples: int = 100) -> Dataset:
        """创建数据集。"""
        ds = Dataset(name, features, samples)
        self._datasets.append(ds)
        return ds

    def create_feature_extractor(self) -> FeatureExtractor:
        """创建特征提取器。"""
        fe = FeatureExtractor()
        self._feature_extractors.append(fe)
        return fe

    def evaluate_model(self) -> ModelEvaluation:
        """创建模型评估器。"""
        me = ModelEvaluation()
        self._evaluations.append(me)
        return me


def create_data_science() -> DataScienceManager:
    """创建数据科学管理器。"""
    return DataScienceManager()


def _register_data_science(builtins: dict) -> None:
    """注册数据科学内置函数。

    Matha 调用 f(a, b) 在 VM 与 interp 两侧均为柯里化单参应用 f(a)(b)，
    零参写法 f() 传入 0，故注册形态必须是逐参 lambda 链（与 neural_network
    插件同口径）；平铺多参 lambda 会被首参提前求值。
    """
    builtins["创建数据科学"] = lambda _: create_data_science()
    builtins["创建数据集"] = lambda n: lambda f: lambda s: \
        DataScienceManager().create_dataset(n, f, s)
    builtins["创建特征提取器"] = lambda _: DataScienceManager().create_feature_extractor()
    builtins["评估模型"] = lambda _: DataScienceManager().evaluate_model()
    builtins["加载CSV"] = lambda ds: lambda p: ds.load_csv(p)
    builtins["归一化"] = lambda ds: ds.normalize()
    builtins["划分训练测试"] = lambda ds: lambda r: ds.split_train_test(r)
    builtins["准确率"] = lambda t: lambda p: ModelEvaluation().accuracy(t, p)


def _data_science_symtab_names() -> list[str]:
    return [
        "创建数据科学", "创建数据集", "创建特征提取器",
        "评估模型", "加载CSV", "归一化", "划分训练测试",
        "准确率",
    ]


__all__ = [
    "Dataset", "FeatureExtractor", "ModelEvaluation",
    "DataScienceManager", "create_data_science",
    "_register_data_science", "_data_science_symtab_names",
]
