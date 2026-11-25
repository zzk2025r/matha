# -*- coding: utf-8 -*-
"""Matha 独立可执行文件 — PyInstaller 装配（阶段 43a-1 真化）。

构建命令（与 .github/workflows/matha-ci.yml build-exe 同源）:
    python -m PyInstaller --noconfirm matha.spec
产物: dist/matha.exe（onefile，进程映像名 matha.exe，非 python.exe）

装配口径（三条，逐条有锁）:
① 单一 Analysis + 单一 EXE，入口 src/matha_main.py（统一 CLI：repl / 终端 /
   run / eval / build …全族子命令）。既往两份 Analysis 同名 'matha'，首份以
   src/repl.py 为入口且 exclude_binaries=True 而无 COLLECT——半成品 EXE 必被
   第二份覆写，属死装配（构建耗时翻倍、入口口径二义）。
② 语料入包 ⇒ 冻结态自包含。Matha 语料（matha/**/*.matha）、多语言前端源
   （matha/frontends/**，src/hybrid_frontend.py 按仓库相对路径读取）、域插件
   清单（src/domains/manifest.json，src/domains/registry.py 的 importlib 动态
   导入源）一并入包，落解包根 sys._MEIPASS 下**与仓库同构的相对路径**——
   src/matha_chain.py 的 `_REPO_ROOT = Path(__file__).resolve().parent.parent`
   在冻结态即解包根，链面装载器据此拼 根()/matha/<名>，故目录形状必须等于
   仓库形状。既往 datas=[] ⇒ matha.exe 的 终端 直接
   FileNotFoundError: <_MEIPASS>/matha/lexer.matha（装载与链面终端不可用，
   只有宿主引擎面可跑）。
③ 域插件 hiddenimports 由 manifest 派生，不再手抄。registry 走
   importlib.import_module(plugin["module"])，静态分析看不见；手抄 57 名漏
   32 个域（含 os_module / capability / filesystem / store / data_science /
   neural_network）。派生后新增/删除域插件随 manifest 自动同步，零死条目。

边界: 本装配不引入任何第三方运行时依赖（pyproject dependencies=[] 不变）——
PyInstaller 仅构建期，excludes 显式屏蔽宿主站点包使其不被间接拉入产物。
路径一律由 PyInstaller 注入的 SPECPATH 全局派生，不硬编绝对路径。
"""

import json
from pathlib import Path

ROOT = Path(SPECPATH)
SRC = ROOT / "src"
MATHA = ROOT / "matha"

# ── ② 语料入包：目标路径 = 仓库相对目录（解包根下的形状即仓库形状） ──


def _dest_dir(path: Path, base: Path) -> str:
    sub = path.relative_to(base).parent.as_posix()
    return base.name if sub == "." else base.name + "/" + sub


def _assets():
    """(源文件, 包内目录) 列表——三段各有明确运行期消费方，无兜底通配。"""
    items = [
        (str(p), _dest_dir(p, MATHA))
        for p in sorted(MATHA.rglob("*.matha"))
        if "__pycache__" not in p.parts
    ]
    frontends = MATHA / "frontends"
    items += [
        (str(p), _dest_dir(p, MATHA))
        for p in sorted(frontends.rglob("*"))
        if p.is_file() and p.suffix in (".c", ".go", ".js", ".rs")
    ]
    items.append((str(SRC / "domains" / "manifest.json"), "src/domains"))
    return items


# ── ③ 核心模块 hiddenimports（人工维护，须逐个对应 src/ 下真在的模块） ──

_CORE_HIDDEN = [
    'src.math_driver',
    'src.matha_main',
    'src.compiler.matha_cc',
    'src.mir',
    'src.mir_codegen',
    'src.mir_converter',
    'src.compiler.memoize',
    'src.compiler.jit',
    'src.compiler.llvm_hybrid',
    'src.compiler.aot',
    'src.profiler',
    'src.lsp',
    'src.doc_gen',
    'src.pkg_manager_v2',
    'src.multi_lang_codegen',
    'src.multi_lang_verifier',
    'src.csp_os_thread',
    'src.performance_benchmark',
    'src.type_system_v2',
    'src.offline_store',
    'src.offline.sqlite_storage',
    'src.offline.sync',
    'src.offline.mobile_api_client',
    'src.stdlib.core',
    'src.stdlib.arithmetic',
    'src.stdlib.calculus',
    'src.stdlib.calculus_symbolic',
    'src.stdlib.linear_algebra',
    'src.stdlib.logic',
    'src.intent_parser',
    'src.repl_completion',
    'src.repl_highlight',
    'src.repl_v23',
    'src.result',
    'src.interp',
    'src.parser',
    'src.ast_nodes',
    'src.tokens',
    'src.lexer',
    'src.semantic',
    'src.symbolic',
    'src.symbols',
    'src.diagnostics',
]


def _plugin_hidden():
    """域插件模块名——直接读 manifest，与 registry 的可导入集同源。"""
    manifest = json.loads((SRC / "domains" / "manifest.json").read_text(encoding="utf-8"))
    names = {pl["module"] for pl in manifest["plugins"] if pl.get("module")}
    names.add("src.domains.registry")  # 装载器本身不在插件清单内
    return sorted(names)


HIDDEN = _CORE_HIDDEN + _plugin_hidden()

a = Analysis(
    [str(SRC / "matha_main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=_assets(),
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'pytest',
        'unittest',
        'IPython',
        'jupyter',
        'notebook',
        'flask',
        'django',
        'openai',
        'anthropic',
        'google.generativeai',
        'requests',
        'numpy',
        'scipy',
        'numba',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='matha',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 加壳对 PyInstaller 引导段无收益，且抬高杀软误判面
    console=True,  # 保留控制台窗口——CMD 调用/管道/重定向的契约面
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
