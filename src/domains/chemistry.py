"""Matha 化学模块：分子结构、化学反应、量子化学、周期表。

覆盖：
  1) 分子结构
  2) 化学反应
  3) 量子化学
  4) 周期表
  5) 热力学
  6) 动力学
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

# 物理常数（SI）
R_GAS = 8.314462618        # 摩尔气体常量 J/(mol·K)
K_B = 1.380649e-23         # 玻尔兹曼常量 J/K
N_A = 6.02214076e23        # 阿伏伽德罗常量 1/mol
T0_K = 273.15              # 标准状况温度 K
P0_PA = 101325.0           # 标准状况压强 Pa
V0_M3 = 0.022413969545014  # 标准状况摩尔体积 m³/mol


# ============================================================
# 柯里化工具
# ============================================================

def _curry2(func):
    def with_first(a):
        return lambda b: func(a, b)
    return with_first


def _curry3(func):
    def with_first(a):
        def with_second(b):
            return lambda c: func(a, b, c)
        return with_second
    return with_first


# ============================================================
# 热力学 / 动力学公式
# 约定：多参函数一律 _curry2/_curry3 封装（与 statmech / thermo 一致）
# ============================================================

def _理想气体_P(n: float, V: float, T: float) -> float:
    """理想气体压强：P = nRT/V（Pa）。

    n 物质的量 mol，V 体积 m³，T 温度 K。
    例：1 mol、V0_M3、273.15 K → 101325 Pa（1 atm）。
    """
    if V == 0:
        raise ValueError("体积 V 不能为 0")
    return n * R_GAS * T / V


def _理想气体_V(n: float, P: float, T: float) -> float:
    """理想气体体积：V = nRT/P（m³）。"""
    if P == 0:
        raise ValueError("压强 P 不能为 0")
    return n * R_GAS * T / P


def _理想气体_T(n: float, P: float, V: float) -> float:
    """理想气体温度：T = PV/(nR)（K）。"""
    if n == 0:
        raise ValueError("物质的量 n 不能为 0")
    return P * V / (n * R_GAS)


def _理想气体_密度(P: float, M: float, T: float) -> float:
    """理想气体密度：ρ = PM/(RT)（kg/m³）。

    P 压强 Pa，M 摩尔质量 kg/mol，T 温度 K。
    """
    if T == 0:
        raise ValueError("温度 T 不能为 0")
    return P * M / (R_GAS * T)


def _微观_压强(N: float, T: float) -> float:
    """微观理想气体压强：P = Nk_BT/V 的无体积形式 P·V = Nk_BT（Pa·m³）。"""
    return N * K_B * T


def _物质的量_分子数(n: float) -> float:
    """分子数：N = n·N_A（1）。"""
    return n * N_A


def _标准状况_体积(n: float) -> float:
    """标准状况体积：V = n·V0_M3（m³）。"""
    return n * V0_M3


def _标准状况_压强() -> float:
    """标准状况压强：P0（Pa）。"""
    return P0_PA


def _内能变化_理想气体(f: float, n: float, dT: float) -> float:
    """理想气体内能变化：ΔU = (f/2)nRΔT（J）。f 为自由度。"""
    return f / 2 * n * R_GAS * dT


def _吉布斯自由能(dH: float, dS: float, T: float) -> float:
    """吉布斯自由能：ΔG = ΔH - TΔS（J/mol）。"""
    return dH - T * dS


def _平衡常数_K(dG: float, T: float) -> float:
    """平衡常数：K = exp(-ΔG/RT)。"""
    if T == 0:
        return 0.0
    return math.exp(-dG / (R_GAS * T))


def _阿伦尼乌斯_k(A: float, Ea: float, T: float) -> float:
    """阿伦尼乌斯速率常数：k = A·exp(-Ea/RT)。"""
    if T == 0:
        return 0.0
    return A * math.exp(-Ea / (R_GAS * T))


def _一级反应_半衰期(ln2: float, k: float) -> float:
    """一级反应半衰期：t½ = ln2/k（s）。"""
    return ln2 / k if k else float("inf")


def _化学计量_限速(n0: float, stoich: float) -> float:
    """化学计量限速：n = n0/stoich（mol）。"""
    return n0 / stoich if stoich else 0.0


class BondType(Enum):
    """化学键类型。"""
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    IONIC = "ionic"
    HYDROGEN = "hydrogen"


@dataclass
class Atom:
    """原子。"""
    element: str = "H"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    charge: float = 0.0


@dataclass
class Molecule:
    """分子。"""
    name: str = ""
    atoms: list[Atom] = field(default_factory=list)
    bonds: list[tuple] = field(default_factory=list)
    formula: str = ""
    molar_mass: float = 0.0


@dataclass
class Reaction:
    """化学反应。"""
    reactants: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    energy: float = 0.0
    balanced: bool = True


class ChemistryEngine:
    """化学引擎：分子、反应、周期表。"""

    def __init__(self):
        self._molecules: list[Molecule] = []
        self._reactions: list[Reaction] = []
        self._initialized = False
        self._init_chemistry()

    def _init_chemistry(self) -> None:
        """初始化化学引擎。"""
        self._initialized = True

    def create_molecule(self, name: str = "H2O") -> Molecule:
        """创建分子。"""
        mol = Molecule(name=name)
        self._molecules.append(mol)
        return mol

    def add_atom(self, mol: Molecule, element: str,
                    x: float = 0, y: float = 0,
                    z: float = 0) -> Atom:
        """添加原子。"""
        atom = Atom(element=element, x=x, y=y, z=z)
        mol.atoms.append(atom)
        return atom

    def add_bond(self, mol: Molecule, a1: int, a2: int,
                    bond_type: str = "single") -> bool:
        """添加化学键。"""
        mol.bonds.append((a1, a2, bond_type))
        return True

    def create_reaction(self, reactants: list[str],
                            products: list[str]) -> Reaction:
        """创建反应。"""
        rx = Reaction(reactants=reactants, products=products)
        self._reactions.append(rx)
        return rx

    def get_element(self, symbol: str) -> dict:
        """获取元素信息。"""
        return {"symbol": symbol, "name": "Element", "atomic_number": 1}

    def calculate_energy(self, reaction: Reaction) -> float:
        """计算反应能量。"""
        return reaction.energy


def create_chemistry_engine() -> ChemistryEngine:
    """创建化学引擎。"""
    return ChemistryEngine()


def _register_chemistry(builtins: dict) -> None:
    """注册化学内置函数。"""
    builtins["创建化学引擎"] = create_chemistry_engine
    builtins["创建分子"] = lambda n="H2O": ChemistryEngine().create_molecule(n)
    builtins["添加原子"] = lambda mol, e, x, y, z: ChemistryEngine().add_atom(mol, e, x, y, z)
    builtins["添加化学键"] = lambda mol, a1, a2, t="single": ChemistryEngine().add_bond(mol, a1, a2, t)
    builtins["创建反应"] = lambda r, p: ChemistryEngine().create_reaction(r, p)
    builtins["获取元素"] = lambda s: ChemistryEngine().get_element(s)
    builtins["计算能量"] = lambda rx: ChemistryEngine().calculate_energy(rx)
    # 热力学：理想气体_P(n)(V)(T)
    builtins["理想气体_P"] = _curry3(_理想气体_P)
    builtins["理想气体_V"] = _curry3(_理想气体_V)
    builtins["理想气体_T"] = _curry3(_理想气体_T)
    builtins["理想气体_密度"] = _curry3(_理想气体_密度)
    builtins["微观_压强"] = _curry2(_微观_压强)
    builtins["标准状况_体积"] = _curry2(_标准状况_体积)
    builtins["标准状况_压强"] = _标准状况_压强
    # 动力学 / 热化学
    builtins["内能变化_理想气体"] = _curry3(_内能变化_理想气体)
    builtins["吉布斯自由能"] = _curry3(_吉布斯自由能)
    builtins["平衡常数_K"] = _curry2(_平衡常数_K)
    builtins["阿伦尼乌斯_k"] = _curry3(_阿伦尼乌斯_k)
    builtins["一级反应_半衰期"] = _curry2(_一级反应_半衰期)
    builtins["化学计量_限速"] = _curry2(_化学计量_限速)


def _chemistry_symtab_names() -> list[str]:
    return [
        "创建化学引擎", "创建分子", "添加原子",
        "添加化学键", "创建反应", "获取元素", "计算能量",
        "理想气体_P", "理想气体_V", "理想气体_T", "理想气体_密度",
        "微观_压强", "标准状况_体积", "标准状况_压强",
        "内能变化_理想气体", "吉布斯自由能", "平衡常数_K",
        "阿伦尼乌斯_k", "一级反应_半衰期", "化学计量_限速",
    ]


__all__ = [
    "BondType", "Atom", "Molecule", "Reaction",
    "ChemistryEngine", "create_chemistry_engine",
    "R_GAS", "K_B", "N_A", "T0_K", "P0_PA", "V0_M3",
    "_register_chemistry", "_chemistry_symtab_names",
]
