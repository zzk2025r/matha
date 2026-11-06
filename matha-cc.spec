# -*- coding: utf-8 -*-
"""
matha-cc 编译器独立可执行文件 - PyInstaller 配置文件

构建命令:
    pyinstaller --onefile matha-cc.spec
"""

a = Analysis(
    ['src/compiler/matha_cc_cli.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src.compiler.matha_cc',
        'src.mir',
        'src.mir_codegen',
        'src.mir_converter',
        'src.compiler.memoize',
        'src.compiler.jit',
        'src.compiler.llvm_hybrid',
        'src.compiler.aot',
        'src.compiler.native',
        'src.profiler',
        'src.lsp',
        'src.doc_gen',
        'src.pkg_manager_v2',
        'src.multi_lang_codegen',
        'src.multi_lang_verifier',
        'src.type_system_v2',
        'src.stdlib.core',
        'src.stdlib.arithmetic',
        'src.stdlib.calculus',
        'src.stdlib.calculus_symbolic',
        'src.stdlib.linear_algebra',
        'src.parser',
        'src.ast_nodes',
        'src.tokens',
        'src.lexer',
        'src.semantic',
        'src.symbolic',
        'src.symbols',
        'src.interp',
        'src.math_driver',
        'src.result',
        # 领域模块
        'src.domains.hal',
        'src.domains.hardware',
        'src.domains.hardware_reverse',
        'src.domains.kernel_math',
        'src.domains.software_app',
        'src.domains.hardware',
    ],
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

# 单文件模式（与本文件头部声明的 `pyinstaller --onefile` 以及 matha.spec 的
# exe_onedir 写法保持一致）：旧写法只给了 `exclude_binaries=True` 而没有配套的
# `COLLECT`，PyInstaller 会把 EXE 落在 build/matha-cc/ 且不携带 Python DLL与扩展库，
# 产物启动即报 `Failed to load Python DLL ...\_internal\python314.dll`，`dist/` 下
# 根根本没有 matha-cc。把 binaries/datas 直接并入 EXE 才会生成可运行的
# dist/matha-cc.exe。
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='matha-cc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
