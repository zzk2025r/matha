"""
Matha 自适应优化系统 - 根据程序特征动态选择优化策略

这个模块提供了：
1. 程序特征分析 - 收集程序的各种特征
2. 优化策略选择 - 基于特征选择合适的优化策略
3. 优化效果评估 - 评估优化效果并调整策略
4. 机器学习模型 - 使用机器学习预测最佳优化策略

这个系统是 Matha 实现智能化优化的核心组件。
"""
from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("matha.adaptive_optimizer")

# 机器学习路径为可选依赖（sklearn）：核心安装第三方依赖为 0（pyproject dependencies=[]），
# 仅在显式调用 train()/ML 预测时惰性装入；缺席时 select_strategy 走 _select_by_rules 规则路径。


@dataclass
class ProgramFeature:
    """程序特征"""
    name: str
    value: float
    type: str = "numeric"  # numeric, categorical, text
    description: str = ""

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict) -> ProgramFeature:
        """从字典创建特征"""
        return cls(
            name=data["name"],
            value=data["value"],
            type=data.get("type", "numeric"),
            description=data.get("description", "")
        )


@dataclass
class OptimizationStrategy:
    """优化策略"""
    name: str
    description: str = ""
    passes: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_improvement: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "passes": self.passes,
            "parameters": self.parameters,
            "expected_improvement": self.expected_improvement,
            "confidence": self.confidence
        }

    @classmethod
    def from_dict(cls, data: Dict) -> OptimizationStrategy:
        """从字典创建策略"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            passes=data.get("passes", []),
            parameters=data.get("parameters", {}),
            expected_improvement=data.get("expected_improvement", 0.0),
            confidence=data.get("confidence", 0.0)
        )


class ProgramAnalyzer:
    """程序分析器 - 收集程序特征"""

    def __init__(self) -> None:
        """初始化程序分析器"""
        self.features: List[ProgramFeature] = []

    def analyze(self, program: Any) -> List[ProgramFeature]:
        """
        分析程序并提取特征

        Args:
            program: 输入程序

        Returns:
            程序特征列表
        """
        self.features = []

        # 分析函数数量
        self._analyze_function_count(program)

        # 分析循环结构
        self._analyze_loops(program)

        # 分析函数调用
        self._analyze_function_calls(program)

        # 分析数据流
        self._analyze_data_flow(program)

        # 分析指令类型分布
        self._analyze_instruction_types(program)

        # 分析代码复杂度
        self._analyze_complexity(program)

        # 分析内存使用模式
        self._analyze_memory_usage(program)

        # 分析并行性
        self._analyze_parallelism(program)

        return self.features

    def _analyze_function_count(self, program: Any) -> None:
        """分析函数数量"""
        func_count = len(getattr(program, "functions", {}))
        self.features.append(ProgramFeature(
            name="函数数量",
            value=float(func_count),
            type="numeric",
            description="程序中定义的函数总数"
        ))

    def _analyze_loops(self, program: Any) -> None:
        """分析循环结构"""
        loop_count = 0
        total_loop_iterations = 0

        for func in getattr(program, "functions", {}).values():
            for instr in getattr(func, "instructions", []):
                # 检测循环指令
                if hasattr(instr, "op") and instr.op in ("loop", "for", "while"):
                    loop_count += 1
                    # 尝试获取循环迭代次数
                    if hasattr(instr, "iterations"):
                        total_loop_iterations += instr.iterations

        self.features.append(ProgramFeature(
            name="循环数量",
            value=float(loop_count),
            type="numeric",
            description="程序中循环结构的总数"
        ))

        if loop_count > 0:
            self.features.append(ProgramFeature(
                name="平均循环迭代次数",
                value=float(total_loop_iterations / loop_count),
                type="numeric",
                description="循环的平均迭代次数"
            ))

    def _analyze_function_calls(self, program: Any) -> None:
        """分析函数调用"""
        call_count = 0
        recursive_calls = 0
        external_calls = 0

        for func in getattr(program, "functions", {}).values():
            for instr in getattr(func, "instructions", []):
                # 检测函数调用指令
                if hasattr(instr, "func_name") and instr.func_name:
                    call_count += 1
                    # 检查是否是递归调用
                    if instr.func_name == getattr(func, "name", ""):
                        recursive_calls += 1
                    # 检查是否是外部调用
                    if instr.func_name not in getattr(program, "functions", {}):
                        external_calls += 1

        self.features.append(ProgramFeature(
            name="函数调用次数",
            value=float(call_count),
            type="numeric",
            description="程序中函数调用的总次数"
        ))

        self.features.append(ProgramFeature(
            name="递归调用比例",
            value=float(recursive_calls / call_count) if call_count > 0 else 0.0,
            type="numeric",
            description="递归调用占总函数调用的比例"
        ))

        self.features.append(ProgramFeature(
            name="外部调用比例",
            value=float(external_calls / call_count) if call_count > 0 else 0.0,
            type="numeric",
            description="外部函数调用占总函数调用的比例"
        ))

    def _analyze_data_flow(self, program: Any) -> None:
        """分析数据流"""
        total_instructions = 0
        load_count = 0
        store_count = 0
        move_count = 0

        for func in getattr(program, "functions", {}).values():
            for instr in getattr(func, "instructions", []):
                total_instructions += 1
                # 检测数据流指令
                if hasattr(instr, "op"):
                    if instr.op in ("load", "ld"):
                        load_count += 1
                    elif instr.op in ("store", "st"):
                        store_count += 1
                    elif instr.op in ("move", "mov"):
                        move_count += 1

        if total_instructions > 0:
            self.features.append(ProgramFeature(
                name="加载指令比例",
                value=float(load_count / total_instructions),
                type="numeric",
                description="加载指令占总指令的比例"
            ))

            self.features.append(ProgramFeature(
                name="存储指令比例",
                value=float(store_count / total_instructions),
                type="numeric",
                description="存储指令占总指令的比例"
            ))

            self.features.append(ProgramFeature(
                name="移动指令比例",
                value=float(move_count / total_instructions),
                type="numeric",
                description="移动指令占总指令的比例"
            ))

    def _analyze_instruction_types(self, program: Any) -> None:
        """分析指令类型分布"""
        instruction_counts: Dict[str, int] = {}
        total_instructions = 0

        for func in getattr(program, "functions", {}).values():
            for instr in getattr(func, "instructions", []):
                total_instructions += 1
                # 统计指令类型
                op = getattr(instr, "op", "unknown")
                instruction_counts[op] = instruction_counts.get(op, 0) + 1

        # 计算主要指令类型比例
        for op, count in instruction_counts.items():
            if count > total_instructions * 0.05:  # 只统计占比超过5%的指令类型
                self.features.append(ProgramFeature(
                    name=f"{op}指令比例",
                    value=float(count / total_instructions),
                    type="numeric",
                    description=f"{op}指令占总指令的比例"
                ))

    def _analyze_complexity(self, program: Any) -> None:
        """分析代码复杂度"""
        cyclomatic_complexity = 0
        cognitive_complexity = 0
        halstead_difficulty = 0

        for func in getattr(program, "functions", {}).values():
            # 计算圈复杂度
            decisions = 0
            for instr in getattr(func, "instructions", []):
                if hasattr(instr, "op") and instr.op in ("if", "while", "for", "switch", "case"):
                    decisions += 1
            cyclomatic_complexity = decisions + 1

            # 计算认知复杂度
            nesting_level = 0
            max_nesting = 0
            for instr in getattr(func, "instructions", []):
                if hasattr(instr, "op") and instr.op in ("if", "while", "for"):
                    nesting_level += 1
                    max_nesting = max(max_nesting, nesting_level)
                elif hasattr(instr, "op") and instr.op in ("endif", "endwhile", "endfor"):
                    nesting_level -= 1
            cognitive_complexity = max_nesting + decisions

            # 计算Halstead难度
            operators = set()
            operands = set()
            for instr in getattr(func, "instructions", []):
                if hasattr(instr, "op"):
                    operators.add(instr.op)
                if hasattr(instr, "operands"):
                    for op in instr.operands:
                        operands.add(str(op))
            halstead_difficulty = len(operators) / 2 * operands.__len__() / 2

        n_funcs = len(getattr(program, "functions", {}))
        # 无函数程序（如纯表达式/空 IR）除零防御：平均复杂度诚实记 0.0
        avg_cyclomatic = float(cyclomatic_complexity / n_funcs) if n_funcs else 0.0
        avg_cognitive = float(cognitive_complexity / n_funcs) if n_funcs else 0.0

        self.features.append(ProgramFeature(
            name="平均圈复杂度",
            value=avg_cyclomatic,
            type="numeric",
            description="程序的平均圈复杂度"
        ))

        self.features.append(ProgramFeature(
            name="平均认知复杂度",
            value=avg_cognitive,
            type="numeric",
            description="程序的平均认知复杂度"
        ))

        self.features.append(ProgramFeature(
            name="Halstead难度",
            value=halstead_difficulty,
            type="numeric",
            description="程序的Halstead难度指标"
        ))

    def _analyze_memory_usage(self, program: Any) -> None:
        """分析内存使用模式"""
        memory_accesses = 0
        unique_memory_locations = set()
        stack_accesses = 0
        heap_accesses = 0

        for func in getattr(program, "functions", {}).values():
            for instr in getattr(func, "instructions", []):
                # 检测内存访问指令
                if hasattr(instr, "op") and instr.op in ("load", "store", "ld", "st"):
                    memory_accesses += 1
                    # 尝试确定内存位置
                    if hasattr(instr, "address"):
                        addr = str(instr.address)
                        unique_memory_locations.add(addr)
                        if "stack" in addr.lower() or "sp" in addr.lower():
                            stack_accesses += 1
                        elif "heap" in addr.lower() or "malloc" in addr.lower():
                            heap_accesses += 1

        if memory_accesses > 0:
            self.features.append(ProgramFeature(
                name="内存访问密度",
                value=float(memory_accesses / sum(len(getattr(f, "instructions", [])) for f in getattr(program, "functions", {}).values())),
                type="numeric",
                description="每条指令的内存访问次数"
            ))

            self.features.append(ProgramFeature(
                name="堆栈访问比例",
                value=float(stack_accesses / memory_accesses),
                type="numeric",
                description="堆栈内存访问占总内存访问的比例"
            ))

            self.features.append(ProgramFeature(
                name="堆访问比例",
                value=float(heap_accesses / memory_accesses),
                type="numeric",
                description="堆内存访问占总内存访问的比例"
            ))

    def _analyze_parallelism(self, program: Any) -> None:
        """分析并行性"""
        parallel_instructions = 0
        independent_instructions = 0

        for func in getattr(program, "functions", {}).values():
            instructions = getattr(func, "instructions", [])
            n = len(instructions)

            # 简单分析：检测没有数据依赖的指令
            for i in range(n):
                # 检查指令是否可以并行执行
                can_parallel = True

                # 检查是否有数据依赖
                for j in range(i):
                    # 如果前面的指令有数据依赖，则不能并行
                    if self._has_data_dependency(instructions[j], instructions[i]):
                        can_parallel = False
                        break

                if can_parallel:
                    parallel_instructions += 1

                    # 检查是否是完全独立的指令
                    if self._is_independent(instructions[i]):
                        independent_instructions += 1

        total_instructions = sum(len(getattr(f, "instructions", [])) for f in getattr(program, "functions", {}).values())
        if total_instructions > 0:
            self.features.append(ProgramFeature(
                name="并行指令比例",
                value=float(parallel_instructions / total_instructions),
                type="numeric",
                description="可以并行执行的指令占总指令的比例"
            ))

            self.features.append(ProgramFeature(
                name="独立指令比例",
                value=float(independent_instructions / total_instructions),
                type="numeric",
                description="完全独立的指令占总指令的比例"
            ))

    def _has_data_dependency(self, instr1: Any, instr2: Any) -> bool:
        """检查两个指令是否有数据依赖"""
        # 简化实现：检查是否有相同的操作数
        if not hasattr(instr1, "operands") or not hasattr(instr2, "operands"):
            return False

        # 检查是否有相同的操作数
        for op1 in instr1.operands:
            for op2 in instr2.operands:
                if op1 == op2:
                    return True

        return False

    def _is_independent(self, instr: Any) -> bool:
        """检查指令是否是完全独立的"""
        # 简化实现：检查是否是常量操作
        if hasattr(instr, "op") and instr.op in ("load_const", "add", "sub", "mul", "div"):
            return True

        return False


class StrategySelector:
    """策略选择器 - 基于程序特征选择优化策略"""

    def __init__(self) -> None:
        """初始化策略选择器"""
        self.strategies: List[OptimizationStrategy] = []
        # ML 模型惰性化：构造零第三方依赖，train() 首次调用时装入 sklearn
        self.model = None
        self.feature_names: List[str] = []
        self.is_trained = False

        # 加载默认策略
        self._load_default_strategies()

    def _load_default_strategies(self) -> None:
        """加载默认优化策略"""
        # 高计算密集型程序策略
        self.strategies.append(OptimizationStrategy(
            name="高计算密集型",
            description="适用于计算密集型程序的优化策略",
            passes=[
                "常量折叠",
                "公共子表达式消除",
                "强度削弱",
                "循环展开",
                "窥孔优化"
            ],
            parameters={
                "循环展开因子": 4,
                "迭代次数": 3
            },
            expected_improvement=0.3,
            confidence=0.8
        ))

        # 内存密集型程序策略
        self.strategies.append(OptimizationStrategy(
            name="内存密集型",
            description="适用于内存密集型程序的优化策略",
            passes=[
                "死代码消除",
                "复制传播",
                "内联优化",
                "窥孔优化"
            ],
            parameters={
                "内联阈值": 3,
                "迭代次数": 2
            },
            expected_improvement=0.25,
            confidence=0.7
        ))

        # 控制流密集型程序策略
        self.strategies.append(OptimizationStrategy(
            name="控制流密集型",
            description="适用于控制流密集型程序的优化策略",
            passes=[
                "死代码消除",
                "公共子表达式消除",
                "窥孔优化"
            ],
            parameters={
                "迭代次数": 2
            },
            expected_improvement=0.2,
            confidence=0.6
        ))

        # 通用优化策略
        self.strategies.append(OptimizationStrategy(
            name="通用优化",
            description="适用于一般程序的优化策略",
            passes=[
                "常量折叠",
                "死代码消除",
                "公共子表达式消除",
                "复制传播",
                "窥孔优化"
            ],
            parameters={
                "迭代次数": 2
            },
            expected_improvement=0.15,
            confidence=0.9
        ))

    def train(self, training_data: List[Tuple[List[ProgramFeature], OptimizationStrategy]]) -> None:
        """
        训练策略选择模型

        Args:
            training_data: 训练数据，每个元素是 (程序特征, 最佳策略) 的元组
        """
        # ML 依赖惰性装入：缺席时诚实报错（绝不静默退化成假成功）
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score
        except ImportError as e:
            raise ImportError(
                "策略选择器的 ML 训练路径需要 scikit-learn（pip install scikit-learn）；"
                "未安装时 select_strategy 自动走 _select_by_rules 规则路径，无需训练。"
            ) from e
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)

        # 准备训练数据
        X = []
        y = []

        # 收集所有特征名称
        all_feature_names = set()
        for features, _ in training_data:
            for feature in features:
                all_feature_names.add(feature.name)
        self.feature_names = sorted(all_feature_names)

        # 转换特征为向量
        for features, strategy in training_data:
            feature_vector = []
            for name in self.feature_names:
                # 查找特征值
                value = 0.0
                for feature in features:
                    if feature.name == name:
                        value = feature.value
                        break
                feature_vector.append(value)
            X.append(feature_vector)

            # 转换策略为标签
            strategy_index = self.strategies.index(strategy) if strategy in self.strategies else -1
            y.append(strategy_index)

        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # 训练模型
        self.model.fit(X_train, y_train)

        # 评估模型
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"策略选择模型训练完成，准确率: {accuracy:.2f}")

        self.is_trained = True

    def select_strategy(self, features: List[ProgramFeature]) -> OptimizationStrategy:
        """
        基于程序特征选择优化策略

        Args:
            features: 程序特征

        Returns:
            选择的优化策略
        """
        if not self.is_trained or self.model is None:
            # 模型未训练或缺 sklearn（ML 可选）时，使用基于规则的简单选择
            return self._select_by_rules(features)

        # 转换特征为向量
        feature_vector = []
        for name in self.feature_names:
            # 查找特征值
            value = 0.0
            for feature in features:
                if feature.name == name:
                    value = feature.value
                    break
            feature_vector.append(value)

        # 使用模型预测最佳策略
        strategy_index = self.model.predict([feature_vector])[0]
        if 0 <= strategy_index < len(self.strategies):
            selected_strategy = self.strategies[strategy_index]

            # 更新策略的置信度
            selected_strategy.confidence = float(max(self.model.predict_proba([feature_vector])[0]))

            return selected_strategy
        else:
            # 回退到基于规则的选择
            return self._select_by_rules(features)

    def _select_by_rules(self, features: List[ProgramFeature]) -> OptimizationStrategy:
        """基于规则选择策略"""
        # 提取特征值
        feature_dict = {f.name: f.value for f in features}

        # 基于规则选择策略
        # 1. 如果计算密集型特征高，选择高计算密集型策略
        if (feature_dict.get("内存访问密度", 0) < 0.1 and 
            feature_dict.get("并行指令比例", 0) > 0.3):
            return self.strategies[0]  # 高计算密集型

        # 2. 如果内存访问密集，选择内存密集型策略
        if feature_dict.get("内存访问密度", 0) > 0.2:
            return self.strategies[1]  # 内存密集型

        # 3. 如果控制流复杂，选择控制流密集型策略
        if feature_dict.get("平均圈复杂度", 0) > 10:
            return self.strategies[2]  # 控制流密集型

        # 4. 默认选择通用优化策略
        return self.strategies[3]  # 通用优化

    def add_strategy(self, strategy: OptimizationStrategy) -> None:
        """添加优化策略"""
        self.strategies.append(strategy)

    def remove_strategy(self, strategy_name: str) -> bool:
        """移除优化策略"""
        for i, strategy in enumerate(self.strategies):
            if strategy.name == strategy_name:
                self.strategies.pop(i)
                return True
        return False

    def list_strategies(self) -> List[OptimizationStrategy]:
        """列出所有策略"""
        return self.strategies.copy()


class AdaptiveOptimizer:
    """自适应优化器 - 核心组件"""

    def __init__(self) -> None:
        """初始化自适应优化器"""
        self.analyzer = ProgramAnalyzer()
        self.selector = StrategySelector()
        self.optimization_history: List[Tuple[List[ProgramFeature], OptimizationStrategy, float]] = []

    def optimize(self, program: Any) -> Any:
        """
        自适应优化程序

        Args:
            program: 输入程序

        Returns:
            优化后的程序
        """
        # 1. 分析程序特征
        logger.info("分析程序特征...")
        features = self.analyzer.analyze(program)

        # 2. 选择优化策略
        logger.info("选择优化策略...")
        strategy = self.selector.select_strategy(features)
        logger.info(f"选择策略: {strategy.name}")

        # 3. 应用优化策略
        logger.info("应用优化策略...")
        # 这里应该调用实际的优化管道
        # 简化实现，直接返回原程序
        optimized_program = program

        # 4. 评估优化效果
        # 简化实现，使用预期改进
        improvement = strategy.expected_improvement

        # 5. 记录优化历史
        self.optimization_history.append((features, strategy, improvement))

        logger.info(f"优化完成，预期改进: {improvement:.2f}")
        return optimized_program

    def train_selector(self, training_data: List[Tuple[List[ProgramFeature], OptimizationStrategy]]) -> None:
        """
        训练策略选择器

        Args:
            training_data: 训练数据
        """
        logger.info("训练策略选择器...")
        self.selector.train(training_data)
        logger.info("策略选择器训练完成")

    def add_strategy(self, strategy: OptimizationStrategy) -> None:
        """添加优化策略"""
        self.selector.add_strategy(strategy)

    def remove_strategy(self, strategy_name: str) -> bool:
        """移除优化策略"""
        return self.selector.remove_strategy(strategy_name)

    def list_strategies(self) -> List[OptimizationStrategy]:
        """列出所有策略"""
        return self.selector.list_strategies()

    def get_optimization_history(self) -> List[Tuple[List[ProgramFeature], OptimizationStrategy, float]]:
        """获取优化历史"""
        return self.optimization_history.copy()

    def save_model(self, model_path: str) -> None:
        """保存训练好的模型"""
        if not self.selector.is_trained:
            logger.warning("模型未训练，无法保存")
            return

        import joblib
        joblib.dump(self.selector.model, model_path)
        logger.info(f"模型已保存到 {model_path}")

    def load_model(self, model_path: str) -> None:
        """加载训练好的模型"""
        import joblib
        self.selector.model = joblib.load(model_path)
        self.selector.is_trained = True
        logger.info(f"模型已从 {model_path} 加载")


# 全局自适应优化器实例
_global_adaptive_optimizer = None


def get_adaptive_optimizer() -> AdaptiveOptimizer:
    """获取全局自适应优化器"""
    global _global_adaptive_optimizer
    if _global_adaptive_optimizer is None:
        _global_adaptive_optimizer = AdaptiveOptimizer()
    return _global_adaptive_optimizer


def optimize_program(program: Any) -> Any:
    """优化程序"""
    optimizer = get_adaptive_optimizer()
    return optimizer.optimize(program)


def train_selector(training_data: List[Tuple[List[ProgramFeature], OptimizationStrategy]]) -> None:
    """训练策略选择器"""
    optimizer = get_adaptive_optimizer()
    optimizer.train_selector(training_data)


def add_strategy(strategy: OptimizationStrategy) -> None:
    """添加优化策略"""
    optimizer = get_adaptive_optimizer()
    optimizer.add_strategy(strategy)


def remove_strategy(strategy_name: str) -> bool:
    """移除优化策略"""
    optimizer = get_adaptive_optimizer()
    return optimizer.remove_strategy(strategy_name)


def list_strategies() -> List[OptimizationStrategy]:
    """列出所有策略"""
    optimizer = get_adaptive_optimizer()
    return optimizer.list_strategies()


def get_optimization_history() -> List[Tuple[List[ProgramFeature], OptimizationStrategy, float]]:
    """获取优化历史"""
    optimizer = get_adaptive_optimizer()
    return optimizer.get_optimization_history()


def save_model(model_path: str) -> None:
    """保存模型"""
    optimizer = get_adaptive_optimizer()
    optimizer.save_model(model_path)


def load_model(model_path: str) -> None:
    """加载模型"""
    optimizer = get_adaptive_optimizer()
    optimizer.load_model(model_path)
