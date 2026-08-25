# -*- coding: utf-8 -*-
"""
Matha 自定义领域发现与加载模拟演示

场景：用户新增了一个「生物计算」领域，Matha 自动发现、注册、加载并调用其函数。

步骤：
  1. 模拟用户创建新领域模块 src/domains/bio_computing.py
  2. 通过 DomainRegistry 自动发现并注册
  3. 加载内置函数到解释器
  4. 用 Matha 代码调用新领域函数
  5. 展示领域如何无缝集成到编译/解释流水线
"""
import sys
import os

sys.path.insert(0, r"D:\trae")


# ============================================================
# 步骤 1：模拟用户创建新的「生物计算」领域模块
# ============================================================
print("=" * 60)
print("【步骤 1】模拟用户创建新领域模块")
print("=" * 60)

BIO_COMPUTING_CODE = '''# -*- coding: utf-8 -*-
"""生物计算领域：基因组学、蛋白质分析、系统生物学。"""
from __future__ import annotations
import math

# 遗传密码表
GENETIC_CODE = {
    "ATA":"I", "ATC":"I", "ATT":"I", "ATG":"M",
    "ACA":"T", "ACC":"T", "ACG":"T", "ACT":"T",
    "AAC":"N", "AAT":"N", "AAA":"K", "AAG":"K",
    "AGC":"S", "AGT":"S", "AGA":"R", "AGG":"R",
    "CTA":"L", "CTC":"L", "CTG":"L", "CTT":"L",
    "CCA":"P", "CCC":"P", "CCG":"P", "CCT":"P",
    "CAC":"H", "CAT":"H", "CAA":"Q", "CAG":"Q",
    "CGA":"R", "CGC":"R", "CGG":"R", "CGT":"R",
    "GTA":"V", "GTC":"V", "GTG":"V", "GTT":"V",
    "GCA":"A", "GCC":"A", "GCG":"A", "GCT":"A",
    "GAC":"D", "GAT":"D", "GAA":"E", "GAG":"E",
    "GGC":"G", "GGT":"G", "GGG":"G",
    "TCA":"S", "TCC":"S", "TCG":"S", "TCT":"S",
    "TTC":"F", "TTT":"F", "TTA":"L", "TTG":"L",
    "TAC":"Y", "TAT":"Y", "TAA":"*", "TAG":"*",
    "TGC":"C", "TGT":"C", "TGA":"*", "TGG":"W",
}

# ─── 分子生物学 ───────────────────────────────────────────

def dna_translate(dna: str) -> str:
    """DNA → 蛋白质（通过 mRNA 中转）。"""
    rna = dna.replace("T", "U")
    protein = ""
    for i in range(0, len(rna) - 2, 3):
        codon = rna[i:i+3]
        protein += GENETIC_CODE.get(codon, "X")
    return protein

def rna_fold(rna: str) -> str:
    """RNA 二级结构预测（简化：碱基配对数）。"""
    comp = {"A": "U", "U": "A", "G": "C", "C": "G"}
    folded = ""
    for base in rna:
        folded += comp.get(base, base)
    return folded[::-1]

def gc_content(seq: str) -> float:
    """GC 含量。"""
    if not seq:
        return 0.0
    gc = sum(1 for c in seq.upper() if c in "GC")
    return gc / len(seq)

def protein_mass(seq: str) -> float:
    """蛋白质分子量估算（平均残基质量 110 Da）。"""
    return len(seq) * 110.0

def isoelectric_point(seq: str) -> float:
    """等电点简化估算。"""
    acidic = sum(1 for c in seq if c in "DE")
    basic = sum(1 for c in seq if c in "KRH")
    return 6.0 + 0.5 * (basic - acidic)

# ─── 系统生物学 ───────────────────────────────────────────

def metabolic_flux(Vmax: float, Km: float, S: float) -> float:
    """代谢通量（米氏方程）。"""
    return Vmax * S / (Km + S)

def enzyme_kinetics(Vmax: float, Km: float, S: float) -> float:
    """酶动力学（同米氏方程）。"""
    return Vmax * S / (Km + S)

def population_growth(N0: float, r: float, t: float) -> float:
    """指数种群增长。"""
    return N0 * math.exp(r * t)

def epidemic_sir(S0: float, I0: float, R0: float, beta: float, gamma: float, t: float) -> dict:
    """SIR 流行病模型。"""
    S, I, R = S0, I0, R0
    N = S + I + R
    dt = 0.01
    steps = int(t / dt)
    for _ in range(steps):
        dS = -beta * S * I / N * dt
        dI = beta * S * I / N * dt - gamma * I * dt
        dR = gamma * I * dt
        S += dS
        I += dI
        R += dR
    return {"S": S, "I": I, "R": R, "R0": beta / gamma if gamma > 0 else float("inf")}

def phylogenetic_distance(seq1: str, seq2: str) -> float:
    """系统发育距离（p-distance）。"""
    if len(seq1) != len(seq2):
        return float("nan")
    diffs = sum(1 for a, b in zip(seq1, seq2) if a != b)
    return diffs / len(seq1)

__all__ = ["dna_translate", "rna_fold", "gc_content", "protein_mass",
           "isoelectric_point", "metabolic_flux", "enzyme_kinetics",
           "population_growth", "epidemic_sir", "phylogenetic_distance"]
'''

# 写入新模块
bio_module_path = os.path.join(os.path.dirname(__file__), "..", "src", "domains", "bio_computing.py")
os.makedirs(os.path.dirname(bio_module_path), exist_ok=True)
with open(bio_module_path, "w", encoding="utf-8") as f:
    f.write(BIO_COMPUTING_CODE)

print(f"✓ 新领域模块已创建: src/domains/bio_computing.py")
print(f"  包含函数: dna_translate, rna_fold, gc_content, protein_mass, isoelectric_point")
print(f"            metabolic_flux, enzyme_kinetics, population_growth, epidemic_sir, phylogenetic_distance")


# ============================================================
# 步骤 2：自动发现新模块（模拟文件系统扫描）
# ============================================================
print()
print("=" * 60)
print("【步骤 2】自动发现新领域模块")
print("=" * 60)

domain_dir = os.path.join(os.path.dirname(__file__), "..", "src", "domains")
all_modules = [f[:-3] for f in os.listdir(domain_dir) if f.endswith(".py") and not f.startswith("__")]

print(f"\n扫描 src/domains/ 发现 {len(all_modules)} 个模块:")
for m in sorted(all_modules):
    marker = " ← 新增" if m == "bio_computing" else ""
    print(f"  • src.domains.{m}{marker}")

# ============================================================
# 步骤 3：注册新领域到 DomainRegistry
# ============================================================
print()
print("=" * 60)
print("【步骤 3】注册新领域到 DomainRegistry")
print("=" * 60)

from src.domains.registry import DomainRegistry, DomainMeta

registry = DomainRegistry()

# 注册新领域（模拟通过配置文件或命令行注册）
bio_meta = DomainMeta(
    name="BioComputing",
    display_name="生物计算与合成生物学",
    description="基因组学、蛋白质分析、系统生物学",
    module="src.domains.bio_computing",
    functions=[
        "dna_translate", "rna_fold", "gc_content",
        "protein_mass", "isoelectric_point",
        "metabolic_flux", "enzyme_kinetics",
        "population_growth", "epidemic_sir",
        "phylogenetic_distance",
    ],
    constants={
        "GENETIC_CODE_SIZE": 64,
        "CODON_LENGTH": 3,
        "AMINO_ACID_AVG_MW": 110.0,
    },
    optimization_passes=["MathaBioOptPass"],
    targets=["python", "c"],
    category="science",
)
registry.register("BioComputing", bio_meta)
print(f"✓ 领域已注册: {bio_meta.display_name}")
print(f"  模块路径: {bio_meta.module}")
print(f"  内置函数: {len(bio_meta.functions)} 个")
print(f"  常量: {bio_meta.constants}")


# ============================================================
# 步骤 4：加载领域模块并提取内置函数
# ============================================================
print()
print("=" * 60)
print("【步骤 4】自动加载领域模块并提取内置函数")
print("=" * 60)

# 清除缓存确保热加载
if "src.domains.bio_computing" in sys.modules:
    del sys.modules["src.domains.bio_computing"]

bio_module = registry.load("BioComputing")
if bio_module:
    print(f"✓ 模块加载成功: {bio_module.__name__}")
    print(f"  导出函数 ({len(bio_module.__all__)}): {bio_module.__all__}")
else:
    print("✗ 模块加载失败")
    sys.exit(1)

builtins = registry.get_builtins("BioComputing")
print(f"✓ 内置函数已提取: {len(builtins)} 个")
for name in bio_meta.functions:
    if name in builtins:
        doc = builtins[name].__doc__.split("\n")[0] if builtins[name].__doc__ else ""
        print(f"  ✓ {name}: {doc}")
    else:
        print(f"  ✗ {name}: 未找到")


# ============================================================
# 步骤 5：调用领域函数演示
# ============================================================
print()
print("=" * 60)
print("【步骤 5】调用领域函数演示")
print("=" * 60)

# 5.1 分子生物学
print()
print("── 分子生物学 ──")
dna_seq = "ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG"
print(f"DNA 序列: {dna_seq}")

protein = builtins["dna_translate"](dna_seq)
print(f"  DNA→蛋白质: {protein}")

folded = builtins["rna_fold"](dna_seq.replace("T", "U"))
print(f"  RNA折叠（互补反向）: {folded}")

gc = builtins["gc_content"](dna_seq)
print(f"  GC 含量: {gc:.2%}")

mass = builtins["protein_mass"](protein)
print(f"  蛋白质分子量: {mass:.0f} Da")

pI = builtins["isoelectric_point"](protein)
print(f"  等电点(估算): pH = {pI:.1f}")

# 5.2 系统生物学
print()
print("── 系统生物学 ──")
pop = builtins["population_growth"](N0=100, r=0.1, t=10)
print(f"  种群增长: N(0)=100, r=0.1, t=10 → N={pop:.1f}")

flux = builtins["metabolic_flux"](Vmax=100, Km=5, S=10)
print(f"  代谢通量: Vmax=100, Km=5, [S]=10 → v={flux:.1f}")

epidemic = builtins["epidemic_sir"](S0=990, I0=10, R0=0, beta=0.3, gamma=0.1, t=50)
print(f"  SIR 模型 (t=50): S={epidemic['S']:.0f}, I={epidemic['I']:.0f}, R={epidemic['R']:.0f}")
print(f"    R0 (基本再生数): {epidemic['R0']:.2f}")

dist = builtins["phylogenetic_distance"]("ATGGCC", "ATGACC")
print(f"  系统发育距离: 'ATGGCC' vs 'ATGACC' → d={dist:.2f}")


# ============================================================
# 步骤 6：集成到 Matha 解释器
# ============================================================
print()
print("=" * 60)
print("【步骤 6】集成到 Matha 解释器")
print("=" * 60)

from src.interp import Interpreter

interp = Interpreter()

# 将新领域函数注册到解释器
for name, fn in builtins.items():
    interp.builtins[name] = fn

print(f"✓ 已将 {len(builtins)} 个函数注册到解释器 builtins")

# 用 Matha 代码调用新领域函数
print()
print("── Matha 代码执行演示 ──")

test_cases = [
    ("protein = dna_translate('ATGGCCATTGTA')", "蛋白质翻译"),
    ("gc = gc_content('ATGGCC')", "GC含量计算"),
    ("pop = population_growth(100, 0.1, 5)", "种群增长"),
    ("v = enzyme_kinetics(100, 5, 10)", "酶动力学"),
    ("dist = phylogenetic_distance('ATG', 'ACG')", "系统发育距离"),
]

for code, desc in test_cases:
    print(f"\n  描述: {desc}")
    print(f"  代码: {code}")
    try:
        # 直接使用 Python 模拟 Matha 解释执行
        local_vars = {}
        exec(code, {"__builtins__": __builtins__} | interp.builtins, local_vars)
        result = local_vars.get(list(local_vars.keys())[-1], "(无返回值)")
        print(f"  输出: {result}")
    except Exception as e:
        print(f"  输出: {type(e).__name__}: {e}")


# ============================================================
# 步骤 7：领域元数据查询
# ============================================================
print()
print("=" * 60)
print("【步骤 7】领域元数据查询")
print("=" * 60)

all_domains = registry.list_domains()
print(f"\n当前注册的 {len(all_domains)} 个领域:")
for d in sorted(all_domains, key=lambda x: x["name"]):
    status = "✓已加载" if d["loaded"] else "○未加载"
    print(f"  {status} {d['name']:35s} [{d['category']:10s}] {d['functions']} 个函数")

stats = registry.get_stats()
print(f"\n领域统计:")
print(f"  总领域数: {stats['total_domains']}")
for cat, count in stats["categories"].items():
    if count > 0:
        print(f"  {cat}: {count}")


# ============================================================
# 总结
# ============================================================
print()
print("=" * 60)
print("【总结】Matha 自定义领域完整生命周期")
print("=" * 60)
print("""
  ┌─────────────────────────────────────────────────────────┐
  │  用户创建: src/domains/bio_computing.py                 │
  │       ↓                                                 │
  │  自动发现: 扫描 src/domains/*.py 检测到新模块           │
  │       ↓                                                 │
  │  注册: registry.register("BioComputing", meta)          │
  │       ↓                                                 │
  │  加载: importlib.import_module("src.domains.bio_...")   │
  │       ↓                                                 │
  │  提取: get_builtins() → {func_name: callable, ...}      │
  │       ↓                                                 │
  │  集成: interp.builtins.update(builtins)                 │
  │       ↓                                                 │
  │  可用: protein = dna_translate('ATGGCC...')             │
  └─────────────────────────────────────────────────────────┘

  新领域函数均可在 Matha 代码中直接使用！
""")

print("演示完成！Matha 已成功自动发现并加载全新领域。")
