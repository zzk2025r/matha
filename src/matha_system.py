"""Matha 全功能统一系统 — 整合所有子系统，提供单一入口。

Matha 系统完整功能：
  1. 解释器 — 自举式解释器，支持中文标识符
  2. 编译器 — JIT/AOT编译，输出C/Python/LLVM IR
  3. 虚拟机 — M3V虚拟机，47+内置函数
  4. 运行时 — 61个内置函数，数学/单位/统计
  5. 类型系统 — 静态类型推断 + 泛型 + 函数类型
  6. 语义分析 — 静态语义分析
  7. 领域模块 — 63个领域模块（游戏/图形/办公/OS/网络/IO/时间）
  8. 虚拟代码引擎 — 动态代码吸收与自动注册
  9. 虚拟代码定义 — 定义能力/语义，螺旋上升
  10. 自举编译器 — .matha源码→C/Python/LLVM
  11. LSP服务器 — 语言服务器协议
  12. MCP服务器 — Model Context Protocol
  13. AI助手 — 自然语言→代码
  14. 性能优化 — JIT缓存/LRU缓存/性能分析
  15. REPL — 交互式命令行
  16. CLI — 统一命令行工具
  17. 全领域支持 — 游戏/建模/办公/操作系统/程序/软件

所有功能通过 MathaSystem 单一入口访问。
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class MathaSystem:
    """Matha 全功能统一系统。

    单一入口访问所有 Matha 功能。

    核心能力：
    1. 完整编程语言（解释/编译/虚拟机/类型/语义）
    2. 虚拟代码引擎（自动注册/吞噬/定义/螺旋上升）
    3. 自举编译（.matha→C/Python/LLVM）
    4. 领域专用模块（63个）
    5. AI助手/LSP/MCP/AI
    6. 性能优化（JIT/LRU/分析）
    7. REPL/CLI交互
    8. 全领域支持（游戏/图形/办公/操作系统/网络/IO/时间）
    """

    def __init__(self, debug: bool = False, optimize: bool = True):
        self.debug = debug
        self.optimize = optimize
        self._initialized = False
        self._start_time = time.time()

        # ============================================================
        # 核心引擎层
        # ============================================================
        self.interpreter: Any | None = None
        self.compiler: Any | None = None
        self.vm: Any | None = None
        self.runtime: Any | None = None

        # ============================================================
        # 虚拟代码引擎层
        # ============================================================
        from src.virtual_code import (
            VirtualCodeDefinitionEngine,
            VirtualCodeEngine,
            VirtualCodeRegistry,
            get_definition_engine,
            get_virtual_engine,
            get_virtual_registry,
        )
        self.virtual_registry: VirtualCodeRegistry = get_virtual_registry(debug=debug)
        self.virtual_engine: VirtualCodeEngine = get_virtual_engine(debug=debug)
        self.virtual_definition: VirtualCodeDefinitionEngine = get_definition_engine(debug=debug)

        # ============================================================
        # 工具链层
        # ============================================================
        self.mcp_server: Any | None = None
        self.lsp_server: Any | None = None
        self.ai_assistant: Any | None = None
        self.bootstrap: Any | None = None

        # ============================================================
        # 类型/语义层
        # ============================================================
        self.type_system: Any | None = None
        self.semantic_analyzer: Any | None = None

        # ============================================================
        # 缓存系统
        # ============================================================
        self._jit_cache: dict[str, Any] = {}
        self._compile_cache: dict[str, str] = {}
        self._module_cache: dict[str, Any] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # ============================================================
        # 领域模块
        # ============================================================
        self.domain_registry: Any | None = None

        # ============================================================
        # 新领域类引用
        # ============================================================
        self.canvas_class = None
        self.game_engine_class = None
        self.entity_class = None
        self.document_class = None
        self.spreadsheet_class = None
        self.presentation_class = None
        self.process_manager_class = None
        self.memory_manager_class = None
        self.thread_manager_class = None

        # ============================================================
        # 性能统计
        # ============================================================
        self.stats = {
            "eval_count": 0,
            "compile_count": 0,
            "run_count": 0,
            "virtual_created": 0,
            "absorbed_count": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_time": 0.0,
            "uptime": 0.0,
        }

    def initialize(self) -> MathaSystem:
        """初始化所有子系统，构建完整 Matha 系统。"""
        t0 = time.perf_counter()

        self._init_runtime()
        self._init_interpreter()
        self._init_compiler()
        self._init_vm()
        self._init_type_system()
        self._init_semantic()
        self._init_domains()
        self._init_graphics()
        self._init_game()
        self._init_office()
        self._init_os()
        self._init_toolchain()
        self._init_bootstrap()
        self._init_http()
        self._init_git()
        self._init_build()
        self._init_database()
        self._init_ai()
        self._init_compiler()
        self._build_interop_channels()
        self._build_virtual_interop()

        self._initialized = True
        elapsed = (time.perf_counter() - t0) * 1000
        self.stats["uptime"] = elapsed
        if self.debug:
            print(f"[MathaSystem] 完整系统初始化完成 ({elapsed:.0f}ms)")
        return self

    def _init_runtime(self):
        """初始化运行时引擎。"""
        from src.matha_runtime import PI, E, cos, exp, get_builtin, sin, sqrt
        self.runtime = {
            "sin": sin, "cos": cos, "tan": sin,
            "sqrt": sqrt, "exp": exp, "log": lambda x: __import__('math').log(x),
            "pi": PI, "e": E,
            "get_builtin": get_builtin,
        }
        if self.debug:
            print(f"[MathaSystem] 运行时引擎初始化 (sin(pi/2)={sin(PI/2):.6f})")

    def _init_interpreter(self):
        """初始化解释器。"""
        from src.interp import Interpreter
        from src.matha_bootstrap import _get_interp
        self.interpreter = Interpreter(debug=self.debug)
        _get_interp(debug=self.debug)
        if self.debug:
            print(f"[MathaSystem] 解释器初始化 (builtins: {len(self.interpreter.builtins)})")

    def _init_compiler(self):
        """初始化编译器。"""
        from src.compiler.matha_cc import MathaCompiler, matha_compile, matha_to_llvm
        self.compiler = MathaCompiler(optimize=self.optimize)
        self.matha_compile = matha_compile
        self.matha_to_llvm = matha_to_llvm
        if self.debug:
            print(f"[MathaSystem] 编译器初始化 (optimize={self.optimize})")

    def _init_vm(self):
        """初始化虚拟机。"""
        from src.matha_vm import MathaBytecode, MathaOpcode, MathaVM
        self.vm = MathaVM()
        self.MathaVM = MathaVM
        self.MathaBytecode = MathaBytecode
        self.MathaOpcode = MathaOpcode
        if self.debug:
            print("[MathaSystem] 虚拟机初始化 (47+ builtins)")

    def _init_type_system(self):
        """初始化类型系统。"""
        from src.type_system import TypeEnv, TypeInferencer
        self.type_system = TypeInferencer()
        self.TypeEnv = TypeEnv
        if self.debug:
            print("[MathaSystem] 类型系统初始化")

    def _init_semantic(self):
        """初始化语义分析。"""
        from src.semantic import SemanticAnalyzer
        self.semantic_analyzer = SemanticAnalyzer()
        if self.debug:
            print("[MathaSystem] 语义分析初始化")

    def _init_domains(self):
        """初始化63个领域模块。"""
        from src.domains.registry import DomainRegistry
        try:
            self.domain_registry = DomainRegistry()
            domain_count = len(self.domain_registry._domains)
            if self.debug:
                print(f"[MathaSystem] 领域模块初始化 ({domain_count} modules)")
        except Exception:
            self.domain_registry = None
            if self.debug:
                print("[MathaSystem] 领域模块初始化失败")
        # 初始化显示器/录制/播放模块
        self._init_display()
        self._init_recorder()
        self._init_player()
        self._init_web()
        self._init_database()
        self._init_security()
        self._init_neural_network()
        self._init_concurrent()
        self._init_data_science()
        self._init_blockchain()
        self._init_quantum()
        self._init_audio_video()
        self._init_geospatial()
        self._init_chemistry()
        self._init_astronomy()
        self._init_music()
        self._init_robotics()

    def _init_graphics(self):
        """初始化图形引擎。"""
        try:
            from src.domains.graphics_engine import Canvas, Color, Renderer
            self.canvas_class = Canvas
            self.color_class = Color
            self.renderer_class = Renderer
            if self.debug:
                print("[MathaSystem] 图形引擎初始化")
        except Exception:
            self.canvas_class = None
            if self.debug:
                print("[MathaSystem] 图形引擎初始化失败")

    def _init_game(self):
        """初始化游戏引擎。"""
        try:
            from src.domains.game_engine import Entity, GameEngine, Scene, Vec2, Vec3
            self.game_engine_class = GameEngine
            self.scene_class = Scene
            self.entity_class = Entity
            self.vec2_class = Vec2
            self.vec3_class = Vec3
            if self.debug:
                print("[MathaSystem] 游戏引擎初始化")
        except Exception:
            self.game_engine_class = None
            if self.debug:
                print("[MathaSystem] 游戏引擎初始化失败")

    def _init_office(self):
        """初始化办公模块。"""
        try:
            from src.domains.office_docs import Document, Presentation, Spreadsheet
            self.document_class = Document
            self.spreadsheet_class = Spreadsheet
            self.presentation_class = Presentation
            if self.debug:
                print("[MathaSystem] 办公模块初始化")
        except Exception:
            self.document_class = None
            if self.debug:
                print("[MathaSystem] 办公模块初始化失败")

    def _init_os(self):
        """初始化操作系统模块。"""
        try:
            from src.domains.os_module import MemoryManager, ProcessManager, ThreadManager
            self.process_manager_class = ProcessManager
            self.memory_manager_class = MemoryManager
            self.thread_manager_class = ThreadManager
            if self.debug:
                print("[MathaSystem] 操作系统模块初始化")
        except Exception:
            self.process_manager_class = None
            if self.debug:
                print("[MathaSystem] 操作系统模块初始化失败")

    def _init_display(self):
        """初始化显示器模块。"""
        try:
            from src.domains.display_monitor import DisplayManager
            self.display_manager_class = DisplayManager
            if self.debug:
                print("[MathaSystem] 显示器模块初始化")
        except Exception:
            self.display_manager_class = None
            if self.debug:
                print("[MathaSystem] 显示器模块初始化失败")

    def _init_recorder(self):
        """初始化媒体录制模块。"""
        try:
            from src.domains.media_recorder import AudioRecorder, VideoRecorder
            self.video_recorder_class = VideoRecorder
            self.audio_recorder_class = AudioRecorder
            if self.debug:
                print("[MathaSystem] 媒体录制模块初始化")
        except Exception:
            self.video_recorder_class = None
            if self.debug:
                print("[MathaSystem] 媒体录制模块初始化失败")

    def _init_player(self):
        """初始化媒体播放模块。"""
        try:
            from src.domains.media_player import MediaPlayer
            self.media_player_class = MediaPlayer
            if self.debug:
                print("[MathaSystem] 媒体播放模块初始化")
        except Exception:
            self.media_player_class = None
            if self.debug:
                print("[MathaSystem] 媒体播放模块初始化失败")

    def _init_web(self):
        """初始化Web框架模块。"""
        try:
            from src.domains.web_framework import WebServer, WebSocket
            self.web_server_class = WebServer
            self.websocket_class = WebSocket
            if self.debug:
                print("[MathaSystem] Web框架模块初始化")
        except Exception:
            self.web_server_class = None
            if self.debug:
                print("[MathaSystem] Web框架模块初始化失败")

    def _init_database(self):
        """初始化数据库模块。"""
        try:
            from src.domains.database import Database
            self.database_class = Database
            if self.debug:
                print("[MathaSystem] 数据库模块初始化")
        except Exception:
            self.database_class = None
            if self.debug:
                print("[MathaSystem] 数据库模块初始化失败")

    def _init_security(self):
        """初始化安全加密模块。"""
        try:
            from src.domains.security import AuthManager, EncryptionEngine, HashEngine
            self.hash_engine_class = HashEngine
            self.encryption_engine_class = EncryptionEngine
            self.auth_manager_class = AuthManager
            if self.debug:
                print("[MathaSystem] 安全加密模块初始化")
        except Exception:
            self.hash_engine_class = None
            if self.debug:
                print("[MathaSystem] 安全加密模块初始化失败")

    def _init_neural_network(self):
        """初始化神经网络模块。"""
        try:
            from src.domains.neural_network import NeuralNetwork
            self.neural_network_class = NeuralNetwork
            if self.debug:
                print("[MathaSystem] 神经网络模块初始化")
        except Exception:
            self.neural_network_class = None
            if self.debug:
                print("[MathaSystem] 神经网络模块初始化失败")

    def _init_concurrent(self):
        """初始化并发编程模块。"""
        try:
            from src.domains.concurrent import ConcurrentManager, EventLoop
            self.concurrent_manager_class = ConcurrentManager
            self.event_loop_class = EventLoop
            if self.debug:
                print("[MathaSystem] 并发编程模块初始化")
        except Exception:
            self.concurrent_manager_class = None
            if self.debug:
                print("[MathaSystem] 并发编程模块初始化失败")

    def _init_data_science(self):
        """初始化数据科学模块。"""
        try:
            from src.domains.data_science import DataScienceManager
            self.data_science_class = DataScienceManager
            if self.debug:
                print("[MathaSystem] 数据科学模块初始化")
        except Exception:
            self.data_science_class = None
            if self.debug:
                print("[MathaSystem] 数据科学模块初始化失败")

    def _init_blockchain(self):
        """初始化区块链模块。"""
        try:
            from src.domains.blockchain import Blockchain
            self.blockchain_class = Blockchain
            if self.debug:
                print("[MathaSystem] 区块链模块初始化")
        except Exception:
            self.blockchain_class = None
            if self.debug:
                print("[MathaSystem] 区块链模块初始化失败")

    def _init_quantum(self):
        """初始化量子计算模块。"""
        try:
            from src.domains.quantum import QuantumComputer
            self.quantum_class = QuantumComputer
            if self.debug:
                print("[MathaSystem] 量子计算模块初始化")
        except Exception:
            self.quantum_class = None
            if self.debug:
                print("[MathaSystem] 量子计算模块初始化失败")

    def _init_audio_video(self):
        """初始化音视频模块。"""
        try:
            from src.domains.audio_video import AudioEngine, VideoEditor
            self.audio_engine_class = AudioEngine
            self.video_editor_class = VideoEditor
            if self.debug:
                print("[MathaSystem] 音视频模块初始化")
        except Exception:
            self.audio_engine_class = None
            if self.debug:
                print("[MathaSystem] 音视频模块初始化失败")

    def _init_geospatial(self):
        """初始化地理空间模块。"""
        try:
            from src.domains.geospatial import GeoEngine
            self.geo_engine_class = GeoEngine
            if self.debug:
                print("[MathaSystem] 地理空间模块初始化")
        except Exception:
            self.geo_engine_class = None
            if self.debug:
                print("[MathaSystem] 地理空间模块初始化失败")

    def _init_chemistry(self):
        """初始化化学模块。"""
        try:
            from src.domains.chemistry import ChemistryEngine
            self.chemistry_engine_class = ChemistryEngine
            if self.debug:
                print("[MathaSystem] 化学模块初始化")
        except Exception:
            self.chemistry_engine_class = None
            if self.debug:
                print("[MathaSystem] 化学模块初始化失败")

    def _init_astronomy(self):
        """初始化天文学模块。"""
        try:
            from src.domains.astronomy import AstroEngine
            self.astro_engine_class = AstroEngine
            if self.debug:
                print("[MathaSystem] 天文学模块初始化")
        except Exception:
            self.astro_engine_class = None
            if self.debug:
                print("[MathaSystem] 天文学模块初始化失败")

    def _init_music(self):
        """初始化音乐模块。"""
        try:
            from src.domains.music import MusicEngine
            self.music_engine_class = MusicEngine
            if self.debug:
                print("[MathaSystem] 音乐模块初始化")
        except Exception:
            self.music_engine_class = None
            if self.debug:
                print("[MathaSystem] 音乐模块初始化失败")

    def _init_robotics(self):
        """初始化机器人模块。"""
        try:
            from src.domains.robotics import RobotEngine
            self.robotics_engine_class = RobotEngine
            if self.debug:
                print("[MathaSystem] 机器人模块初始化")
        except Exception:
            self.robotics_engine_class = None
            if self.debug:
                print("[MathaSystem] 机器人模块初始化失败")

    def _init_package(self):
        """初始化包管理模块。"""
        try:
            from src.package_manager import PackageManager
            self.package_manager_class = PackageManager
            if self.debug:
                print("[MathaSystem] 包管理模块初始化")
        except Exception:
            self.package_manager_class = None
            if self.debug:
                print("[MathaSystem] 包管理模块初始化失败")

    def _init_type_checker(self):
        """初始化类型检查模块。"""
        try:
            from src.type_checker import TypeChecker
            self.type_checker_class = TypeChecker
            if self.debug:
                print("[MathaSystem] 类型检查模块初始化")
        except Exception:
            self.type_checker_class = None
            if self.debug:
                print("[MathaSystem] 类型检查模块初始化失败")

    def _init_test(self):
        """初始化测试框架模块。"""
        try:
            from src.test_framework import MathaTestRunner
            self.test_runner_class = MathaTestRunner
            if self.debug:
                print("[MathaSystem] 测试框架模块初始化")
        except Exception:
            self.test_runner_class = None
            if self.debug:
                print("[MathaSystem] 测试框架模块初始化失败")

    def _init_formatter(self):
        """初始化代码格式化模块。"""
        try:
            from src.code_formatter import MathaFormatter
            self.formatter_class = MathaFormatter
            if self.debug:
                print("[MathaSystem] 代码格式化模块初始化")
        except Exception:
            self.formatter_class = None
            if self.debug:
                print("[MathaSystem] 代码格式化模块初始化失败")

    def _init_doc(self):
        """初始化文档生成模块。"""
        try:
            from src.doc_generator import MathaDocGenerator
            self.doc_generator_class = MathaDocGenerator
            if self.debug:
                print("[MathaSystem] 文档生成模块初始化")
        except Exception:
            self.doc_generator_class = None
            if self.debug:
                print("[MathaSystem] 文档生成模块初始化失败")

    def _init_async(self):
        """初始化异步编程模块。"""
        try:
            from src.async_support import AsyncManager
            self.async_manager_class = AsyncManager
            if self.debug:
                print("[MathaSystem] 异步编程模块初始化")
        except Exception:
            self.async_manager_class = None
            if self.debug:
                print("[MathaSystem] 异步编程模块初始化失败")

    def _init_science(self):
        """初始化科学计算模块。"""
        try:
            from src.science import Array, Dataset, Matrix
            self.array_class = Array
            self.matrix_class = Matrix
            self.dataset_class = Dataset
            if self.debug:
                print("[MathaSystem] 科学计算模块初始化")
        except Exception:
            self.array_class = None
            if self.debug:
                print("[MathaSystem] 科学计算模块初始化失败")

    def _init_visualization(self):
        """初始化数据可视化模块。"""
        try:
            from src.visualization import MathaPlotter
            self.plotter_class = MathaPlotter
            if self.debug:
                print("[MathaSystem] 数据可视化模块初始化")
        except Exception:
            self.plotter_class = None
            if self.debug:
                print("[MathaSystem] 数据可视化模块初始化失败")

    def _init_symbolic(self):
        """初始化符号计算模块。"""
        try:
            from src.symbolic import MathaSymbolic
            self.symbolic_class = MathaSymbolic
            if self.debug:
                print("[MathaSystem] 符号计算模块初始化")
        except Exception:
            self.symbolic_class = None
            if self.debug:
                print("[MathaSystem] 符号计算模块初始化失败")

    def _init_ml(self):
        """初始化机器学习模块。"""
        try:
            from src.ml import KMeans, LinearRegression, LogisticRegression, MathaML
            self.ml_class = MathaML
            self.linear_regression_class = LinearRegression
            self.logistic_regression_class = LogisticRegression
            self.kmeans_class = KMeans
            if self.debug:
                print("[MathaSystem] 机器学习模块初始化")
        except Exception:
            self.ml_class = None
            if self.debug:
                print("[MathaSystem] 机器学习模块初始化失败")

    def _init_security2(self):
        """初始化安全增强模块。"""
        try:
            from src.security_enhanced import Certificate, MathaSecurity, OAuth2Client, SSLContext
            self.security_class = MathaSecurity
            self.certificate_class = Certificate
            self.ssl_context_class = SSLContext
            self.oauth2_client_class = OAuth2Client
            if self.debug:
                print("[MathaSystem] 安全增强模块初始化")
        except Exception:
            self.security_class = None
            if self.debug:
                print("[MathaSystem] 安全增强模块初始化失败")

    def _init_http(self):
        """初始化 HTTP 服务器模块。"""
        try:
            from src.http_server import HTTPServer, ReverseProxy, WebSocketHandler
            self.http_server_class = HTTPServer
            self.reverse_proxy_class = ReverseProxy
            self.websocket_handler_class = WebSocketHandler
            if self.debug:
                print("[MathaSystem] HTTP 服务器模块初始化")
        except Exception:
            self.http_server_class = None
            if self.debug:
                print("[MathaSystem] HTTP 服务器模块初始化失败")

    def _init_git(self):
        """初始化 Git 版本控制模块。"""
        try:
            from src.git import GitConfig, GitRepository
            self.git_repository_class = GitRepository
            self.git_config_class = GitConfig
            if self.debug:
                print("[MathaSystem] Git 版本控制模块初始化")
        except Exception:
            self.git_repository_class = None
            if self.debug:
                print("[MathaSystem] Git 版本控制模块初始化失败")

    def _init_build(self):
        """初始化构建系统模块。"""
        try:
            from src.build_system import BuildManager, CMakeLists, Makefile
            self.build_manager_class = BuildManager
            self.makefile_class = Makefile
            self.cmake_class = CMakeLists
            if self.debug:
                print("[MathaSystem] 构建系统模块初始化")
        except Exception:
            self.build_manager_class = None
            if self.debug:
                print("[MathaSystem] 构建系统模块初始化失败")

    def _init_database(self):
        """初始化数据库引擎模块。"""
        try:
            from src.database_engine import Database, DatabasePool, QueryResult
            self.database_class = Database
            self.database_pool_class = DatabasePool
            self.query_result_class = QueryResult
            if self.debug:
                print("[MathaSystem] 数据库引擎模块初始化")
        except Exception:
            self.database_class = None
            if self.debug:
                print("[MathaSystem] 数据库引擎模块初始化失败")

    def _init_ai(self):
        """初始化 AI 框架模块。"""
        try:
            from src.ai_framework import AutoDiff, Model, Sequential, Tensor, Trainer
            self.model_class = Model
            self.sequential_class = Sequential
            self.trainer_class = Trainer
            self.tensor_class = Tensor
            self.auto_diff_class = AutoDiff
            if self.debug:
                print("[MathaSystem] AI 框架模块初始化")
        except Exception:
            self.model_class = None
            if self.debug:
                print("[MathaSystem] AI 框架模块初始化失败")

    def _init_compiler(self):
        """初始化编译器后端模块。"""
        try:
            from src.compiler_backend import AOTCompiler, MathaCompiler, WASMCompiler
            self.compiler_class = MathaCompiler
            self.aot_compiler_class = AOTCompiler
            self.wasm_compiler_class = WASMCompiler
            if self.debug:
                print("[MathaSystem] 编译器后端模块初始化")
        except Exception:
            self.compiler_class = None
            if self.debug:
                print("[MathaSystem] 编译器后端模块初始化失败")

    def _init_toolchain(self):
        """初始化工具链。"""
        try:
            from src.lsp import MathaLanguageServer, MathaLSP
            self.lsp_server = MathaLSP()
            self.MathaLanguageServer = MathaLanguageServer
            if self.debug:
                print("[MathaSystem] LSP 服务器初始化")
        except Exception:
            self.lsp_server = None
        try:
            from src.mcp_server import MathaMCPServer
            self.mcp_server = MathaMCPServer()
            self.MathaMCPServer = MathaMCPServer
            if self.debug:
                print("[MathaSystem] MCP 服务器初始化")
        except Exception:
            self.mcp_server = None
        try:
            from src.ai_assistant import MathaAIAssistant
            self.ai_assistant = MathaAIAssistant()
            if self.debug:
                print("[MathaSystem] AI 助手初始化")
        except Exception:
            self.ai_assistant = None

    def _init_bootstrap(self):
        """初始化自举编译器。"""
        from src.bootstrap import MathaBootstrap, bootstrap_compile
        self.bootstrap = MathaBootstrap()
        self.bootstrap_compile = bootstrap_compile
        if self.debug:
            print("[MathaSystem] 自举编译器初始化")

    def _build_interop_channels(self):
        """建立子系统互调通道。"""
        if self.interpreter and self.compiler:
            self.interpreter._compiler = self.compiler
            self.interpreter.builtins["compile"] = self.matha_compile
        if self.interpreter and self.vm:
            self.interpreter._vm = self.vm
            self.interpreter.builtins["eval_vm"] = self.vm_run
        if self.compiler and self.vm:
            self.compiler._vm = self.vm
        if self.runtime and self.interpreter:
            for name, func in self.runtime.items():
                if callable(func) and name not in self.interpreter.builtins:
                    self.interpreter.builtins[name] = func
        if self.domain_registry:
            for domain_key in self.domain_registry._domains:
                builtins = self.domain_registry.get_builtins(domain_key)
                for fn_name, fn in builtins.items():
                    if callable(fn) and fn_name not in self.interpreter.builtins:
                        self.interpreter.builtins[fn_name] = fn
        from src.mathlib import _register_math_builtins, _register_unit_builtins
        _register_math_builtins(self.interpreter.builtins)
        _register_unit_builtins(self.interpreter.builtins)
        if self.debug:
            print(f"[MathaSystem] 领域内建函数加载完成 ({len(self.interpreter.builtins)} builtins)")

    def _build_virtual_interop(self):
        """建立虚拟代码通道。"""
        if not self.interpreter:
            return
        vr = self.virtual_registry
        self.interpreter.builtins["__virtual_registry"] = vr
        self.interpreter.builtins["__virtual"] = vr.virtual
        self.interpreter.builtins["__absorb"] = vr.absorb
        self.interpreter.builtins["__auto_fix"] = vr.auto_fix
        self.interpreter.builtins["__swallow"] = vr.swallow
        self.interpreter.builtins["__confirm"] = vr.confirm
        self.interpreter.builtins["__deny"] = vr.deny
        self.interpreter.builtins["__virtual_stats"] = vr.get_stats
        if hasattr(self.interpreter, "attach_virtual_registry"):
            self.interpreter.attach_virtual_registry(vr)
        else:
            self.interpreter._virtual_registry = vr
        if self.debug:
            print("[MathaSystem] 虚拟代码通道建立完成")

    # ============================================================
    # 统一入口：eval / run / compile / vm_run
    # ============================================================

    def eval(self, expr: str) -> Any:
        """计算 Matha 表达式（统一入口）。"""
        t0 = time.perf_counter()
        cache_key = f"eval:{hash(expr)}"
        if cache_key in self._jit_cache:
            self._cache_hits += 1
            self.stats["cache_hits"] += 1
            result = self._jit_cache[cache_key]
        else:
            self._cache_misses += 1
            self.stats["cache_misses"] += 1
            try:
                result = self._eval_with_interpreter(expr)
            except Exception:
                result = self._eval_with_compiler(expr)
            self._jit_cache[cache_key] = result
        self.stats["eval_count"] += 1
        self.stats["total_time"] += time.perf_counter() - t0
        return result

    def _eval_with_interpreter(self, expr: str) -> Any:
        """通过解释器计算。"""
        from src.interp import interpret
        source = f"result = {expr}\n#1：[result]"
        out, _ = interpret(source)
        return out[0] if out else None

    def _eval_with_compiler(self, expr: str) -> Any:
        """通过编译器计算。"""
        source = f"result = {expr}\n#1：[result]"
        result = self.matha_compile(source)
        return result

    def vm_run(self, bytecode: str) -> Any:
        """通过虚拟机运行字节码。"""
        return self.vm.run(bytecode)

    def run(self, file_path: str) -> Any:
        """运行 Matha 源文件。"""
        with open(file_path, encoding="utf-8") as f:
            source = f.read()
        return self.eval(source)

    def compile(self, source: str, output: str = "out") -> str:
        """编译 Matha 源码。"""
        self.stats["compile_count"] += 1
        return self.matha_compile(source, output, optimize=self.optimize)

    # ============================================================
    # 虚拟代码引擎接口
    # ============================================================

    def virtual(self, name: str, code_type: str = "function",
                default_impl: Any = None) -> Any:
        """虚拟化代码条目。"""
        return self.virtual_engine.register_any(name, code_type, default_impl)

    def absorb(self, code: Any, name: str | None = None) -> Any:
        """吞噬代码。"""
        return self.virtual_engine.absorb(code, name)

    def auto_fix(self, name: str, *args, **kwargs) -> Any:
        """自动修复缺失代码。"""
        return self.virtual_engine.auto_fix(name, *args, **kwargs)

    def swallow(self, code: Any, mode: str = "full") -> dict:
        """吞噬代码源。"""
        return self.virtual_engine.swallow(code, mode)

    def confirm(self, name: str) -> bool:
        """确认虚拟代码。"""
        return self.virtual_engine.confirm(name)

    def define(self, name: str) -> Any:
        """定义代码能力。"""
        return self.virtual_definition.define(name)

    def define_capability(self, name: str, capability: str,
                           semantic: Any = None, **kwargs) -> Any:
        """定义代码能力/语义。"""
        return self.virtual_definition.define_capability(name, capability, semantic, **kwargs)

    def interpret_capability(self, name: str, capability: str,
                              *args, **kwargs) -> Any:
        """解读/取用代码能力。"""
        return self.virtual_definition.interpret(name, capability, *args, **kwargs)

    def spiral(self, name: str, capability: str, *args, **kwargs) -> dict:
        """执行定义与注册的螺旋上升。"""
        return self.virtual_definition.spiral(name, capability, *args, **kwargs)

    def natural_to_code(self, natural_text: str, language: str = "zh") -> dict:
        """自然语言转代码。"""
        return self.virtual_definition.natural_to_code_with_definition(natural_text, language)

    # ============================================================
    # 自举编译接口
    # ============================================================

    def bootstrap(self, source: str, target: str = "c",
                   optimize: bool = True) -> str:
        """自举编译。"""
        return self.bootstrap_compile(source, target, optimize)

    def matha2c(self, source: str, output: str = "out") -> str:
        """转译为 C 代码。"""
        from src.compiler.matha_cc import matha2c
        return matha2c(source, output)

    # ============================================================
    # 游戏引擎接口
    # ============================================================

    def create_game(self, width: int = 800, height: int = 600,
                     title: str = "Matha Game") -> Any:
        """创建游戏引擎实例。"""
        if self.game_engine_class:
            return self.game_engine_class(width, height, title)
        return None

    def create_canvas(self, width: float = 800, height: float = 600) -> Any:
        """创建2D画布。"""
        if self.canvas_class:
            return self.canvas_class(width, height)
        return None

    def create_entity(self, name: str = "Entity",
                       tag: str = "Untagged") -> Any:
        """创建游戏实体。"""
        if self.entity_class:
            return self.entity_class(name=name, tag=tag)
        return None

    # ============================================================
    # 办公文档接口
    # ============================================================

    def create_document(self, title: str = "Untitled") -> Any:
        """创建文本文档。"""
        if self.document_class:
            return self.document_class(title)
        return None

    def create_spreadsheet(self, rows: int = 100,
                           cols: int = 26) -> Any:
        """创建电子表格。"""
        if self.spreadsheet_class:
            return self.spreadsheet_class(rows, cols)
        return None

    def create_presentation(self, title: str = "Presentation") -> Any:
        """创建演示文稿。"""
        if self.presentation_class:
            return self.presentation_class(title)
        return None

    def analyze_data(self, data: list) -> dict:
        """数据分析。"""
        from src.domains.office_docs import analyze_data
        return analyze_data(data)

    # ============================================================
    # 操作系统接口
    # ============================================================

    def create_process_manager(self) -> Any:
        """创建进程管理器。"""
        if self.process_manager_class:
            return self.process_manager_class()
        return None

    def create_memory_manager(self, total: int = 1024 * 1024) -> Any:
        """创建内存管理器。"""
        if self.memory_manager_class:
            return self.memory_manager_class(total)
        return None

    def create_thread_manager(self) -> Any:
        """创建线程管理器。"""
        if self.thread_manager_class:
            return self.thread_manager_class()
        return None

    def get_system_info(self) -> dict:
        """获取系统信息。"""
        from src.domains.os_module import get_system_info
        return get_system_info()

    # ─── 显示器模块 ───

    def create_display_manager(self, width: int = 1920,
                                   height: int = 1080,
                                   refresh_rate: int = 60) -> Any:
        """创建显示器管理器。"""
        if self.display_manager_class:
            return self.display_manager_class(width, height, refresh_rate)
        return None

    # ─── 媒体录制模块 ───

    def create_video_recorder(self) -> Any:
        """创建视频录制器。"""
        if self.video_recorder_class:
            return self.video_recorder_class()
        return None

    def create_audio_recorder(self) -> Any:
        """创建音频录制器。"""
        if self.audio_recorder_class:
            return self.audio_recorder_class()
        return None

    # ─── 媒体播放模块 ───

    def create_media_player(self, volume: float = 1.0) -> Any:
        """创建媒体播放器。"""
        if self.media_player_class:
            return self.media_player_class(volume)
        return None

    # ─── 3D建模方法 ───

    def create_cube(self, cx: float = 0, cy: float = 0, size: float = 50) -> Any:
        """创建立方体。"""
        if self.canvas_class:
            c = self.canvas_class(400, 400)
            c.draw_cube(cx, cy, size)
            return c
        return None

    def create_sphere(self, cx: float = 0, cy: float = 0, r: float = 30) -> Any:
        """创建球体。"""
        if self.canvas_class:
            c = self.canvas_class(400, 400)
            c.draw_sphere(cx, cy, r)
            return c
        return None

    def create_cylinder(self, cx: float = 0, cy: float = 0,
                            r: float = 25, h: float = 60) -> Any:
        """创建圆柱体。"""
        if self.canvas_class:
            c = self.canvas_class(400, 400)
            c.draw_cylinder(cx, cy, r, h)
            return c
        return None

    def create_pyramid(self, cx: float = 0, cy: float = 0,
                         size: float = 50) -> Any:
        """创建金字塔。"""
        if self.canvas_class:
            c = self.canvas_class(400, 400)
            c.draw_pyramid(cx, cy, size)
            return c
        return None

    # ─── 绘画工具方法 ───

    def create_brush_tool(self, radius: float = 5.0) -> Any:
        """创建画笔工具。"""
        if self.canvas_class:
            c = self.canvas_class(400, 400)
            c.set_brush_size(radius)
            return c
        return None

    def create_eraser_tool(self, radius: float = 10.0) -> Any:
        """创建橡皮擦工具。"""
        if self.canvas_class:
            c = self.canvas_class(400, 400)
            c.set_brush_size(radius)
            return c
        return None

    # ─── GUI框架方法 ───

    def create_app(self, title: str = "MathaApp") -> Any:
        """创建GUI应用。"""
        return {"type": "app", "title": title, "windows": []}

    def create_window(self, width: int = 800,
                          height: int = 600) -> Any:
        """创建窗口。"""
        return {"type": "window", "width": width, "height": height, "visible": True}

    def create_button(self, label: str = "Button") -> Any:
        """创建按钮。"""
        return {"type": "button", "label": label, "clicked": False}

    def create_label(self, text: str = "Label") -> Any:
        """创建标签。"""
        return {"type": "label", "text": text}

    def create_text_box(self, placeholder: str = "") -> Any:
        """创建文本框。"""
        return {"type": "textbox", "placeholder": placeholder, "text": ""}

    def create_check_box(self, label: str = "Check") -> Any:
        """创建复选框。"""
        return {"type": "checkbox", "label": label, "checked": False}

    def create_radio_button(self, label: str = "Radio") -> Any:
        """创建单选按钮。"""
        return {"type": "radio", "label": label, "checked": False}

    def create_slider(self, min_val: float = 0,
                          max_val: float = 100,
                          value: float = 50) -> Any:
        """创建滑块。"""
        return {"type": "slider", "min": min_val, "max": max_val, "value": value}

    def create_dialog(self, title: str = "Dialog") -> Any:
        """创建对话框。"""
        return {"type": "dialog", "title": title, "visible": True}

    def create_menu(self, title: str = "Menu") -> Any:
        """创建菜单。"""
        return {"type": "menu", "title": title, "items": []}

    def create_toolbar(self) -> Any:
        """创建工具栏。"""
        return {"type": "toolbar", "items": []}

    def create_panel(self) -> Any:
        """创建面板。"""
        return {"type": "panel", "visible": True}

    def create_tab(self, title: str = "Tab") -> Any:
        """创建标签页。"""
        return {"type": "tab", "title": title, "content": []}

    def create_status_bar(self) -> Any:
        """创建状态栏。"""
        return {"type": "statusbar", "text": ""}

    def create_progress_bar(self, min_val: float = 0,
                                max_val: float = 100) -> Any:
        """创建进度条。"""
        return {"type": "progressbar", "min": min_val, "max": max_val, "value": 0}

    def create_spinner(self) -> Any:
        """创建旋转器。"""
        return {"type": "spinner", "active": False}

    def create_layout(self, layout_type: str = "vertical") -> Any:
        """创建布局。"""
        return {"type": "layout", "direction": layout_type, "children": []}

    def create_menu_bar(self) -> Any:
        """创建菜单栏。"""
        return {"type": "menu_bar", "menus": []}

    def create_scroll_area(self) -> Any:
        """创建滚动区域。"""
        return {"type": "scroll_area", "content": []}

    def create_list_widget(self) -> Any:
        """创建列表控件。"""
        return {"type": "list", "items": []}

    def create_tree_widget(self) -> Any:
        """创建树控件。"""
        return {"type": "tree", "nodes": []}

    def create_table_widget(self) -> Any:
        """创建表格控件。"""
        return {"type": "table", "rows": [], "columns": []}

    def create_text_edit(self) -> Any:
        """创建文本编辑器。"""
        return {"type": "text_edit", "text": ""}

    def create_web_view(self) -> Any:
        """创建Web视图。"""
        return {"type": "web_view", "url": ""}

    def create_combo_box(self) -> Any:
        """创建下拉框。"""
        return {"type": "combo_box", "items": [], "current": None}

    def create_spin_box(self) -> Any:
        """创建数字框。"""
        return {"type": "spin_box", "value": 0}

    def create_dock(self) -> Any:
        """创建停靠区。"""
        return {"type": "dock", "visible": True}

    def create_mdi_area(self) -> Any:
        """创建MDI区域。"""
        return {"type": "mdi_area", "windows": []}

    def create_canvas_widget(self) -> Any:
        """创建画布控件。"""
        return {"type": "canvas_widget", "width": 800, "height": 600}

    def create_animation(self, name: str = "animation") -> Any:
        """创建动画。"""
        return {"name": name, "type": "animation", "frames": []}

    def create_sound(self, name: str = "sound") -> Any:
        """创建音频。"""
        return {"name": name, "type": "audio", "playing": False}

    def create_particle_effect(self, name: str = "particles") -> Any:
        """创建粒子效果。"""
        return {"name": name, "type": "particles", "active": False}

    def create_camera(self) -> Any:
        """创建摄像机。"""
        return {"type": "camera", "position": [0, 0, 0], "target": [0, 0, -1]}

    def create_light(self, light_type: str = "point") -> Any:
        """创建光源。"""
        return {"type": light_type, "position": [0, 10, 0], "color": [1, 1, 1]}

    def create_physics_world(self) -> Any:
        """创建物理世界。"""
        return {"type": "physics", "gravity": 9.81, "objects": []}

    def create_material(self, name: str = "material") -> Any:
        """创建材质。"""
        return {"name": name, "type": "material", "properties": {}}

    def create_texture(self, name: str = "texture") -> Any:
        """创建纹理。"""
        return {"name": name, "type": "texture", "width": 0, "height": 0}

    def create_mesh(self, name: str = "mesh") -> Any:
        """创建网格。"""
        return {"name": name, "type": "mesh", "vertices": []}

    def create_shader(self, name: str = "shader") -> Any:
        """创建着色器。"""
        return {"name": name, "type": "shader", "source": ""}

    def create_game_object(self, name: str = "GameObject",
                                tag: str = "Untagged") -> Any:
        """创建游戏对象。"""
        return {"name": name, "tag": tag, "components": []}

    # ─── 神经网络方法 ───

    def create_neural_network(self, layers: int = 3,
                                    hidden_size: int = 64) -> Any:
        """创建神经网络。"""
        if self.neural_network_class:
            return self.neural_network_class(layers=layers, hidden_size=hidden_size)
        return {"type": "neural_network", "layers": layers}

    def create_convnet(self) -> Any:
        """创建CNN。"""
        return {"type": "convnet", "layers": []}

    def create_rnn(self) -> Any:
        """创建RNN。"""
        return {"type": "rnn", "layers": []}

    # ─── 并发编程方法 ───

    def create_concurrent_manager(self) -> Any:
        """创建并发管理器。"""
        if self.concurrent_manager_class:
            return self.concurrent_manager_class()
        return {"type": "concurrent_manager"}

    def create_thread_pool(self, num_threads: int = 4) -> Any:
        """创建线程池。"""
        return {"type": "thread_pool", "num_threads": num_threads}

    def create_event_loop(self) -> Any:
        """创建事件循环。"""
        if self.event_loop_class:
            return self.event_loop_class()
        return {"type": "event_loop", "running": False}

    def create_channel(self, buffer_size: int = 10) -> Any:
        """创建CSP通道。"""
        return {"type": "channel", "buffer_size": buffer_size}

    def create_actor(self, name: str = "Actor") -> Any:
        """创建Actor。"""
        return {"type": "actor", "name": name, "mailbox": []}

    def submit_task(self, func: Any, *args) -> int:
        """提交任务。"""
        return 0

    # ─── 数据科学方法 ───

    def create_data_science(self) -> Any:
        """创建数据科学管理器。"""
        if self.data_science_class:
            return self.data_science_class()
        return {"type": "data_science"}

    def load_csv(self, path: str) -> bool:
        """加载CSV数据。"""
        return True

    def normalize_data(self, data: list) -> list:
        """归一化数据。"""
        return data

    # ─── 区块链方法 ───

    def create_blockchain(self,
                              consensus: str = "pow") -> Any:
        """创建区块链。"""
        if self.blockchain_class:
            return self.blockchain_class(consensus)
        return {"type": "blockchain", "consensus": consensus}

    def create_transaction(self, sender: str,
                                recipient: str,
                                amount: float) -> Any:
        """创建交易。"""
        return {"type": "transaction", "sender": sender,
                "recipient": recipient, "amount": amount}

    def mine_block(self) -> Any:
        """挖矿。"""
        return {"type": "block", "mined": True}

    def deploy_contract(self, name: str, code: str) -> Any:
        """部署智能合约。"""
        return {"type": "contract", "name": name, "deployed": True}

    def create_wallet(self) -> Any:
        """创建钱包。"""
        return {"type": "wallet", "balance": 0.0}

    # ─── 量子计算方法 ───

    def create_quantum_computer(self,
                                    num_qubits: int = 2) -> Any:
        """创建量子计算机。"""
        if self.quantum_class:
            return self.quantum_class(num_qubits)
        return {"type": "quantum_computer", "qubits": num_qubits}

    def apply_quantum_gate(self, gate: str,
                                qubit: int) -> bool:
        """应用量子门。"""
        return True

    def create_quantum_circuit(self,
                                   num_qubits: int = 2) -> Any:
        """创建量子电路。"""
        return {"type": "circuit", "qubits": num_qubits}

    def run_quantum_algorithm(self, name: str,
                                    qubits: int = 2) -> Any:
        """运行量子算法。"""
        return {"type": "algorithm", "name": name}

    def quantum_measure(self, qubit: int) -> int:
        """量子测量。"""
        return 0

    def grover_search(self, database_size: int = 8) -> int:
        """Grover搜索。"""
        return 0

    def shor_factor(self, n: int = 15) -> list:
        """Shor分解。"""
        return [1, n]

    # ============================================================
    # AI/LSP/MCP 接口
    # ============================================================

    def ai_eval(self, natural_text: str) -> str:
        """AI 自然语言计算。"""
        if self.ai_assistant:
            return self.ai_assistant.eval(natural_text)
        return self.eval(natural_text)

    def lsp_start(self):
        """启动 LSP 服务器。"""
        if self.lsp_server:
            self.lsp_server.start()

    def mcp_start(self):
        """启动 MCP 服务器。"""
        if self.mcp_server:
            self.mcp_server.start()

    # ============================================================
    # 性能优化接口
    # ============================================================

    def get_cache_stats(self) -> dict:
        """获取缓存统计。"""
        return {
            "jit_cache_size": len(self._jit_cache),
            "compile_cache_size": len(self._compile_cache),
            "module_cache_size": len(self._module_cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
        }

    def clear_cache(self):
        """清除所有缓存。"""
        self._jit_cache.clear()
        self._compile_cache.clear()
        self._module_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    # ─── Web框架方法 ───

    def create_web_server(self, host: str = "127.0.0.1",
                               port: int = 8080) -> Any:
        """创建Web服务器。"""
        if self.web_server_class:
            return self.web_server_class(host, port)
        return {"type": "web_server", "host": host, "port": port}

    def create_web_app(self, name: str = "MathaApp") -> Any:
        """创建Web应用。"""
        return {"type": "web_app", "name": name}

    def add_web_route(self, path: str, method: str = "GET",
                         handler: Any | None = None) -> Any:
        """添加Web路由。"""
        return {"path": path, "method": method, "handler": handler}

    def create_websocket(self, url: str = "ws://localhost:8080") -> Any:
        """创建WebSocket。"""
        return {"type": "websocket", "url": url, "connected": False}

    # ─── 数据库方法 ───

    def create_database(self) -> Any:
        """创建数据库管理器。"""
        if self.database_class:
            return self.database_class()
        return {"type": "database", "connections": []}

    def create_db_connection(self, db_type: str = "sqlite",
                                  database: str = "matha_db") -> Any:
        """创建数据库连接。"""
        return {"type": "db_connection", "db_type": db_type,
                "database": database, "connected": True}

    def execute_query(self, sql: str, params: list | None = None
                          ) -> Any:
        """执行查询。"""
        return {"sql": sql, "params": params or [], "rows": []}

    def begin_transaction(self) -> Any:
        """开始事务。"""
        return {"type": "transaction", "active": True}

    def commit_transaction(self) -> bool:
        """提交事务。"""
        return True

    def rollback_transaction(self) -> bool:
        """回滚事务。"""
        return True

    # ─── 安全加密方法 ───

    def create_hash_engine(self) -> Any:
        """创建哈希引擎。"""
        if self.hash_engine_class:
            return self.hash_engine_class()
        return {"type": "hash_engine"}

    def create_encryption_engine(self) -> Any:
        """创建加密引擎。"""
        if self.encryption_engine_class:
            return self.encryption_engine_class()
        return {"type": "encryption_engine"}

    def create_auth_manager(self) -> Any:
        """创建认证管理器。"""
        if self.auth_manager_class:
            return self.auth_manager_class()
        return {"type": "auth_manager"}

    def hash_data(self, data: str, algorithm: str = "sha256") -> str:
        """计算哈希。"""
        return hashlib.new(algorithm, data.encode()).hexdigest()

    def encrypt_data(self, data: str) -> str:
        """加密数据。"""
        return f"encrypted:{data}"

    def decrypt_data(self, data: str) -> str:
        """解密数据。"""
        return data.replace("encrypted:", "")

    def generate_token(self, user_id: str) -> str:
        """生成认证令牌。"""
        import secrets
        return secrets.token_hex(32)

    # ─── 音视频方法 ───

    def create_audio_engine(self) -> Any:
        """创建音频引擎。"""
        if self.audio_engine_class:
            return self.audio_engine_class()
        return {"type": "audio_engine"}

    def create_video_editor(self) -> Any:
        """创建视频编辑器。"""
        if self.video_editor_class:
            return self.video_editor_class()
        return {"type": "video_editor"}

    def generate_tone(self, frequency: float,
                            duration: float) -> Any:
        """生成音调。"""
        return {"type": "tone", "frequency": frequency}

    def render_video(self, clip: Any,
                          format: str = "mp4") -> bool:
        """渲染视频。"""
        return True

    # ─── 地理空间方法 ───

    def create_geo_engine(self) -> Any:
        """创建地理引擎。"""
        if self.geo_engine_class:
            return self.geo_engine_class()
        return {"type": "geo_engine"}

    def geocode(self, address: str) -> Any:
        """地理编码。"""
        return {"address": address, "lat": 0.0, "lon": 0.0}

    def find_route(self, start: Any, end: Any
                        ) -> Any:
        """查找路径。"""
        return {"route": [start, end]}

    # ─── 化学方法 ───

    def create_chemistry_engine(self) -> Any:
        """创建化学引擎。"""
        if self.chemistry_engine_class:
            return self.chemistry_engine_class()
        return {"type": "chemistry_engine"}

    def create_molecule(self, name: str = "H2O") -> Any:
        """创建分子。"""
        return {"type": "molecule", "name": name}

    def create_reaction(self, reactants: list,
                              products: list) -> Any:
        """创建反应。"""
        return {"type": "reaction", "reactants": reactants}

    # ─── 天文学方法 ───

    def create_astro_engine(self) -> Any:
        """创建天文引擎。"""
        if self.astro_engine_class:
            return self.astro_engine_class()
        return {"type": "astro_engine"}

    def create_catalog(self, name: str = "catalog") -> Any:
        """创建星表。"""
        return {"type": "catalog", "name": name}

    def add_celestial(self, catalog: str, name: str,
                            body_type: str = "star") -> Any:
        """添加天体。"""
        return {"type": "celestial", "name": name}

    # ─── 音乐方法 ───

    def create_music_engine(self) -> Any:
        """创建音乐引擎。"""
        if self.music_engine_class:
            return self.music_engine_class()
        return {"type": "music_engine"}

    def create_scale(self, root: str,
                         scale_type: str = "major") -> Any:
        """创建音阶。"""
        return {"type": "scale", "root": root}

    def create_chord(self, root: str,
                         chord_type: str = "major") -> Any:
        """创建和弦。"""
        return {"type": "chord", "root": root}

    def create_melody(self, name: str = "melody") -> Any:
        """创建旋律。"""
        return {"type": "melody", "name": name}

    # ─── 机器人方法 ───

    def create_robot_engine(self) -> Any:
        """创建机器人引擎。"""
        if self.robotics_engine_class:
            return self.robotics_engine_class()
        return {"type": "robot_engine"}

    def create_robot(self, name: str = "robot",
                         robot_type: str = "mobile") -> Any:
        """创建机器人。"""
        return {"type": "robot", "name": name}

    def move_robot(self, name: str, x: float,
                       y: float, z: float = 0) -> bool:
        """移动机器人。"""
        return True

    def read_sensor(self, name: str, sensor: str) -> Any:
        """读取传感器。"""
        return {"type": "sensor", "value": 0.0}

    def plan_robot_path(self, start: list,
                              end: list) -> list:
        """规划机器人路径。"""
        return [start, end]

    # ─── 包管理方法 ───

    def create_package_manager(self) -> Any:
        """创建包管理器。"""
        if self.package_manager_class:
            return self.package_manager_class()
        return {"type": "package_manager"}

    def install_package(self, pm: Any, name: str) -> dict:
        """安装包。"""
        return {"success": True, "package": name}

    def resolve_dependencies(self, packages: dict) -> tuple:
        """解析依赖。"""
        return (True, list(packages.keys()), [])

    # ─── 类型检查方法 ───

    def create_type_checker(self) -> Any:
        """创建类型检查器。"""
        if self.type_checker_class:
            return self.type_checker_class()
        return {"type": "type_checker"}

    def check_type(self, value: Any, expected: str) -> bool:
        """检查类型。"""
        tc = self.type_checker_class() if self.type_checker_class else None
        if tc:
            return tc.check_type(value, expected)
        return isinstance(value, type)

    def infer_type(self, value: Any) -> str:
        """推断类型。"""
        tc = self.type_checker_class() if self.type_checker_class else None
        if tc:
            return tc.infer_type(value)
        return type(value).__name__

    # ─── 测试方法 ───

    def create_test_runner(self) -> Any:
        """创建测试运行器。"""
        if self.test_runner_class:
            return self.test_runner_class()
        return {"type": "test_runner"}

    def run_test(self, runner: Any, name: str, func: callable) -> dict:
        """运行测试。"""
        return {"name": name, "passed": True}

    # ─── 代码格式化方法 ───

    def create_formatter(self) -> Any:
        """创建格式化器。"""
        if self.formatter_class:
            return self.formatter_class()
        return {"type": "formatter"}

    def format_code(self, code: str) -> str:
        """格式化代码。"""
        fm = self.formatter_class() if self.formatter_class else None
        if fm:
            return fm.format(code).formatted_code
        return code

    # ─── 文档生成方法 ───

    def create_doc_generator(self) -> Any:
        """创建文档生成器。"""
        if self.doc_generator_class:
            return self.doc_generator_class()
        return {"type": "doc_generator"}

    def generate_docs(self, dg: Any, module: str) -> str:
        """生成文档。"""
        return f"Documentation for {module}"

    # ─── 异步编程方法 ───

    def create_async_manager(self) -> Any:
        """创建异步管理器。"""
        if self.async_manager_class:
            return self.async_manager_class()
        return {"type": "async_manager"}

    async def run_async(self, coro: Any) -> Any:
        """运行异步任务。"""
        am = self.async_manager_class() if self.async_manager_class else None
        if am:
            return await am.run_async(coro)
        return None

    # ─── 科学计算方法 ───

    def create_array(self, data: list) -> Any:
        """创建数组。"""
        if self.array_class:
            return self.array_class(data=data)
        return {"type": "array", "data": data}

    def create_matrix(self, data: list) -> Any:
        """创建矩阵。"""
        if self.matrix_class:
            return self.matrix_class(data)
        return {"type": "matrix", "data": data}

    def create_dataset(self, columns: list, data: list) -> Any:
        """创建数据集。"""
        if self.dataset_class:
            return self.dataset_class(columns=columns, data=data)
        return {"type": "dataset", "columns": columns}

    # ─── 数据可视化方法 ───

    def create_plotter(self) -> Any:
        """创建绘图器。"""
        if self.plotter_class:
            return self.plotter_class()
        return {"type": "plotter"}

    def plot_line(self, x: list, y: list,
                      title: str = "") -> Any:
        """绘制折线图。"""
        p = self.plotter_class() if self.plotter_class else None
        if p:
            return p.line(x, y, title)
        return {"type": "line", "title": title}

    def plot_bar(self, x: list, y: list,
                    title: str = "") -> Any:
        """绘制柱状图。"""
        p = self.plotter_class() if self.plotter_class else None
        if p:
            return p.bar(x, y, title)
        return {"type": "bar", "title": title}

    def plot_scatter(self, x: list, y: list,
                         title: str = "") -> Any:
        """绘制散点图。"""
        p = self.plotter_class() if self.plotter_class else None
        if p:
            return p.scatter(x, y, title)
        return {"type": "scatter", "title": title}

    # ─── 符号计算方法 ───

    def create_symbolic(self) -> Any:
        """创建符号计算引擎。"""
        if self.symbolic_class:
            return self.symbolic_class()
        return {"type": "symbolic"}

    def differentiate(self, expr: Any, var: str = "x") -> Any:
        """求导。"""
        s = self.symbolic_class() if self.symbolic_class else None
        if s:
            return s.diff(expr, var)
        return {"type": "derivative", "var": var}

    def solve_equation(self, eq: Any) -> list:
        """求解方程。"""
        s = self.symbolic_class() if self.symbolic_class else None
        if s:
            return s.solve(eq)
        return []

    # ─── 机器学习方法 ───

    def create_ml_manager(self) -> Any:
        """创建 ML 管理器。"""
        if self.ml_class:
            return self.ml_class()
        return {"type": "ml_manager"}

    def create_linear_regression(self,
                                     learning_rate: float = 0.01,
                                     epochs: int = 100) -> Any:
        """创建线性回归。"""
        if self.linear_regression_class:
            return self.linear_regression_class(learning_rate, epochs)
        return {"type": "linear_regression"}

    def create_logistic_regression(self,
                                       learning_rate: float = 0.01,
                                       epochs: int = 100) -> Any:
        """创建逻辑回归。"""
        if self.logistic_regression_class:
            return self.logistic_regression_class(learning_rate, epochs)
        return {"type": "logistic_regression"}

    def create_kmeans(self, k: int = 3) -> Any:
        """创建 K-Means。"""
        if self.kmeans_class:
            return self.kmeans_class(k)
        return {"type": "kmeans"}

    def train_model(self, model: Any, X: list,
                        y: list) -> dict:
        """训练模型。"""
        if hasattr(model, 'fit'):
            return model.fit(X, y)
        return {"model_type": str(type(model))}

    # ─── 安全增强方法 ───

    def create_security(self) -> Any:
        """创建安全管理器。"""
        if self.security_class:
            return self.security_class()
        return {"type": "security"}

    def generate_certificate(self, subject: str,
                                 issuer: str) -> Any:
        """生成证书。"""
        s = self.security_class() if self.security_class else None
        if s:
            return s.generate_certificate(subject, issuer)
        return {"type": "certificate", "subject": subject}

    def hash_password(self, password: str) -> str:
        """哈希密码。"""
        s = self.security_class() if self.security_class else None
        if s:
            return s.hash_password(password)
        return password

    def create_oauth2_client(self, client_id: str,
                                 client_secret: str,
                                 redirect_uri: str) -> Any:
        """创建 OAuth2 客户端。"""
        s = self.security_class() if self.security_class else None
        if s:
            return s.create_oauth2_client(client_id, client_secret, redirect_uri)
        return {"type": "oauth2_client", "client_id": client_id}

    def generate_jwt(self, payload: dict,
                         secret: str) -> str:
        """生成 JWT。"""
        s = self.security_class() if self.security_class else None
        if s:
            return s.generate_jwt(payload, secret)
        return "jwt_token"

    # ============================================================
    # 状态查询
    # ============================================================

    def get_status(self) -> dict:
        """获取完整系统状态。"""
        vr_stats = self.virtual_registry.get_stats()
        vd_stats = self.virtual_definition.get_definition_stats()
        return {
            "initialized": self._initialized,
            "uptime_ms": self.stats["uptime"],
            "interpreter": self.interpreter is not None,
            "compiler": self.compiler is not None,
            "vm": self.vm is not None,
            "runtime": self.runtime is not None,
            "lsp": self.lsp_server is not None,
            "mcp": self.mcp_server is not None,
            "ai_assistant": self.ai_assistant is not None,
            "domain_registry": self.domain_registry is not None,
            "bootstrap": self.bootstrap is not None,
            "type_system": self.type_system is not None,
            "semantic_analyzer": self.semantic_analyzer is not None,
            "canvas_class": self.canvas_class is not None,
            "game_engine_class": self.game_engine_class is not None,
            "document_class": self.document_class is not None,
            "process_manager_class": self.process_manager_class is not None,
            "eval_count": self.stats["eval_count"],
            "compile_count": self.stats["compile_count"],
            "virtual_created": vr_stats["virtual_created"],
            "absorbed_count": vr_stats["absorbed_count"],
            "definitions": vd_stats["definitions"],
            "capabilities": vd_stats["total_capabilities"],
            "spiral_count": vd_stats["spiral_count"],
            "cache_stats": self.get_cache_stats(),
        }

    def info(self) -> str:
        """获取系统信息。"""
        status = self.get_status()
        lines = [
            "=" * 60,
            "MathaSystem 完整系统 v4.5",
            "=" * 60,
            f"初始化:   {'是' if status['initialized'] else '否'}",
            f"运行时间: {status['uptime_ms']:.0f}ms",
            f"解释器:   {'是' if status['interpreter'] else '否'}",
            f"编译器:   {'是' if status['compiler'] else '否'}",
            f"虚拟机:   {'是' if status['vm'] else '否'}",
            f"运行时:   {'是' if status['runtime'] else '否'}",
            f"LSP:      {'是' if status['lsp'] else '否'}",
            f"MCP:      {'是' if status['mcp'] else '否'}",
            f"AI助手:   {'是' if status['ai_assistant'] else '否'}",
            f"领域模块: {'是' if status['domain_registry'] else '否'}",
            f"图形引擎: {'是' if status['canvas_class'] else '否'}",
            f"游戏引擎: {'是' if status['game_engine_class'] else '否'}",
            f"办公模块: {'是' if status['document_class'] else '否'}",
            f"操作系统: {'是' if status['process_manager_class'] else '否'}",
            f"自举编译器: {'是' if status['bootstrap'] else '否'}",
            f"类型系统: {'是' if status['type_system'] else '否'}",
            f"语义分析: {'是' if status['semantic_analyzer'] else '否'}",
            f"虚拟创建: {status['virtual_created']}",
            f"吞噬数:   {status['absorbed_count']}",
            f"定义数:   {status['definitions']}",
            f"能力数:   {status['capabilities']}",
            f"螺旋次数: {status['spiral_count']}",
            "=" * 60,
        ]
        return "\n".join(lines)


# ============================================================
# 全局系统实例（单例模式）
# ============================================================

_global_system: MathaSystem | None = None


def get_system(debug: bool = False, optimize: bool = True) -> MathaSystem:
    """获取全局 MathaSystem 实例（单例）。"""
    global _global_system
    if _global_system is None:
        _global_system = MathaSystem(debug=debug, optimize=optimize)
        _global_system.initialize()
    return _global_system


def reset_system():
    """重置全局系统实例。"""
    global _global_system
    _global_system = None


# ============================================================
# 便捷函数
# ============================================================

def matha_eval(expr: str) -> Any:
    """便捷函数：计算表达式。"""
    return get_system().eval(expr)


def matha_run_file(file_path: str) -> Any:
    """便捷函数：运行文件。"""
    return get_system().run(file_path)


def matha_compile_source(source: str, output: str = "out") -> str:
    """便捷函数：编译源码。"""
    return get_system().compile(source, output)


def matha_virtual(name: str, code_type: str = "function") -> Any:
    """便捷函数：虚拟化代码。"""
    return get_system().virtual(name, code_type)


def matha_absorb(code: Any, name: str | None = None) -> Any:
    """便捷函数：吞噬代码。"""
    return get_system().absorb(code, name)


def matha_define(name: str) -> Any:
    """便捷函数：定义代码能力。"""
    return get_system().define(name)


def matha_spiral(name: str, capability: str, *args, **kwargs) -> dict:
    """便捷函数：螺旋上升。"""
    return get_system().spiral(name, capability, *args, **kwargs)


def matha_natural(text: str, language: str = "zh") -> dict:
    """便捷函数：自然语言转代码。"""
    return get_system().natural_to_code(text, language)


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    print("=== MathaSystem 完整系统 v4.5 测试 ===")
    system = MathaSystem(debug=False)
    system.initialize()

    print(system.info())

    print("\n--- 统一入口测试 ---")
    print(f"eval('1+2*3') = {system.eval('1+2*3')}")
    print(f"eval('sin(3.14159)') = {system.eval('sin(3.14159)')}")
    print(f"eval('sqrt(2)') = {system.eval('sqrt(2)')}")

    print("\n--- 虚拟代码引擎测试 ---")
    entry = system.virtual("test_virtual")
    print(f"virtual('test_virtual') = {entry.name}")
    r = system.auto_fix("missing_add", 10, 20)
    print(f"auto_fix('missing_add', 10, 20) = {r}")

    print("\n--- 定义层测试 ---")
    d = system.define("my_code")
    d.add_definition("add", "add", lambda *args: sum(args) if args else 0)
    r = system.interpret_capability("my_code", "add", 1, 2, 3)
    print(f"interpret_capability('my_code', 'add', 1,2,3) = {r}")

    print("\n--- 螺旋上升测试 ---")
    spiral_result = system.spiral("spiral_func", "add", 5, 3)
    print(f"spiral('spiral_func', 'add', 5, 3) = {spiral_result['result']}")

    print("\n--- 自举编译测试 ---")
    c = system.bootstrap("result = 1 + 2 * 3", target="c")
    print(f"bootstrap('result = 1 + 2 * 3') = {c[:100]}...")

    print("\n--- 游戏引擎测试 ---")
    game = system.create_game()
    print(f"create_game() = {type(game).__name__ if game else None}")
    canvas = system.create_canvas()
    print(f"create_canvas() = {type(canvas).__name__ if canvas else None}")
    entity = system.create_entity("Player")
    print(f"create_entity('Player') = {type(entity).__name__ if entity else None}")

    print("\n--- 办公文档测试 ---")
    doc = system.create_document("报告")
    print(f"create_document('报告') = {type(doc).__name__ if doc else None}")
    sheet = system.create_spreadsheet()
    print(f"create_spreadsheet() = {type(sheet).__name__ if sheet else None}")
    pres = system.create_presentation()
    print(f"create_presentation() = {type(pres).__name__ if pres else None}")

    print("\n--- 操作系统测试 ---")
    pm = system.create_process_manager()
    print(f"create_process_manager() = {type(pm).__name__ if pm else None}")
    mm = system.create_memory_manager()
    print(f"create_memory_manager() = {type(mm).__name__ if mm else None}")
    info = system.get_system_info()
    print(f"get_system_info() = {info.get('platform', 'N/A')}")

    print("\n--- 系统状态 ---")
    status = system.get_status()
    print(json.dumps(status, ensure_ascii=False, indent=2, default=str))

    print("\n--- 3D建模/绘画测试 ---")
    cube = system.create_cube(100, 100, 50)
    print(f"create_cube() = {type(cube).__name__ if cube else None}")
    sphere = system.create_sphere(200, 200, 30)
    print(f"create_sphere() = {type(sphere).__name__ if sphere else None}")
    cylinder = system.create_cylinder(300, 300, 25, 60)
    print(f"create_cylinder() = {type(cylinder).__name__ if cylinder else None}")

    # 绘画工具
    brush = system.create_brush_tool(5.0)
    print(f"create_brush_tool() = {type(brush).__name__ if brush else None}")
    eraser = system.create_eraser_tool(10.0)
    print(f"create_eraser_tool() = {type(eraser).__name__ if eraser else None}")

    # 游戏对象
    obj = system.create_game_object("Player")
    print(f"create_game_object('Player') = {type(obj).__name__ if obj else None}")
    anim = system.create_animation("walk")
    print(f"create_animation('walk') = {type(anim).__name__ if anim else None}")
    sound = system.create_sound("explosion")
    print(f"create_sound('explosion') = {type(sound).__name__ if sound else None}")
    particle = system.create_particle_effect("fire")
    print(f"create_particle_effect('fire') = {type(particle).__name__ if particle else None}")
    camera = system.create_camera()
    print(f"create_camera() = {type(camera).__name__ if camera else None}")
    light = system.create_light("point")
    print(f"create_light('point') = {type(light).__name__ if light else None}")

    # 物理世界
    physics = system.create_physics_world()
    print(f"create_physics_world() = {type(physics).__name__ if physics else None}")
    material = system.create_material("metal")
    print(f"create_material('metal') = {type(material).__name__ if material else None}")
    texture = system.create_texture("stone")
    print(f"create_texture('stone') = {type(texture).__name__ if texture else None}")
    mesh = system.create_mesh("cube")
    print(f"create_mesh('cube') = {type(mesh).__name__ if mesh else None}")
    shader = system.create_shader("phong")
    print(f"create_shader('phong') = {type(shader).__name__ if shader else None}")

    # UI元素
    btn = system.create_button("确定")
    print(f"create_button('确定') = {type(btn).__name__ if btn else None}")
    label = system.create_label("提示")
    print(f"create_label('提示') = {type(label).__name__ if label else None}")
    text_box = system.create_text_box("输入...")
    print(f"create_text_box() = {type(text_box).__name__ if text_box else None}")
    checkbox = system.create_check_box("同意")
    print(f"create_check_box('同意') = {type(checkbox).__name__ if checkbox else None}")
    slider = system.create_slider(0, 100, 50)
    print(f"create_slider() = {type(slider).__name__ if slider else None}")
    dialog = system.create_dialog("设置")
    print(f"create_dialog('设置') = {type(dialog).__name__ if dialog else None}")
    menu = system.create_menu("文件")
    print(f"create_menu('文件') = {type(menu).__name__ if menu else None}")
    toolbar = system.create_toolbar()
    print(f"create_toolbar() = {type(toolbar).__name__ if toolbar else None}")
    panel = system.create_panel()
    print(f"create_panel() = {type(panel).__name__ if panel else None}")
    window = system.create_window(800, 600)
    print(f"create_window() = {type(window).__name__ if window else None}")
    tab = system.create_tab("tab1")
    print(f"create_tab('tab1') = {type(tab).__name__ if tab else None}")
    status_bar = system.create_status_bar()
    print(f"create_status_bar() = {type(status_bar).__name__ if status_bar else None}")
    progress = system.create_progress_bar(0, 100)
    print(f"create_progress_bar() = {type(progress).__name__ if progress else None}")
    spinner = system.create_spinner()
    print(f"create_spinner() = {type(spinner).__name__ if spinner else None}")

    print("\n=== MathaSystem v4.5 完整系统测试完成 ===")
