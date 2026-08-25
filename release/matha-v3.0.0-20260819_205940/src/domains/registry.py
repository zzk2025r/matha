# -*- coding: utf-8 -*-
"""
Matha 领域注册中心：统一管理所有学科/专业/应用领域的扩展模块。

支持动态注册、热加载、领域查询、领域级优化 Pass 集成。

架构：
  DomainRegistry          领域注册表
  ├── AI_DataScience      人工智能与数据科学
  ├── SoftwareAppDev      软件与应用程序开发
  ├── GameImmersion       游戏与沉浸式体验开发
  ├── Automation          自动化与效率提升
  ├── IoTHardware         物联网与硬件控制
  ├── OSNetwork           底层系统与网络安全
  ├── BlockchainWeb3      区块链与Web3开发
  ├── AudioVideo          音视频与多媒体处理
  ├── GraphicsRender      图形学与渲染技术
  ├── HPC                 科学计算与高性能计算
  ├── FinTech             金融科技与量化交易
  ├── AutonomousDriving   自动驾驶与具身智能
  ├── AerospaceDefense    航空航天与国防工业
  ├── BioComputing        生物计算与合成生物学
  ├── HardwareReverse     极客硬件与逆向工程
  ├── SpatialMeta         空间计算与元宇宙基础设施
  ├── AlgoTrading         算法交易与高频撮合引擎
  ├── CompChem            计算化学与材料科学
  ├── GreenTech           绿色科技
  ├── MetaverseArch       元宇宙与虚拟世界的建筑师
  ├── DigitalRights       数字版权与去中心化信任
  ├── CreativeCoding      创意编程与艺术表达
  ├── GeekGray            极客文化与灰产边缘
  ├── GeneticAlgorithm    遗传算法与AI编写代码
  ├── QuantumComputing    量子计算
  ├── ChaosFractal        混沌理论与分型
  ├── ComputationalLaw    计算法学
  └── CustomDomain        自定义领域（用户扩展）

使用示例：
  registry = DomainRegistry()
  registry.register_domain("AI", "ai_data_science")
  result = registry.run("math", target="c", domain="AI")
"""
from __future__ import annotations
import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


# ============================================================
# 领域元数据
# ============================================================

@dataclass
class DomainMeta:
    """领域元数据。"""
    name: str
    display_name: str
    description: str
    module: str
    functions: list[str] = field(default_factory=list)
    constants: dict = field(default_factory=dict)
    optimization_passes: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=lambda: ["c", "python", "matha"])
    category: str = "general"  # general / science / engineering / creative / frontier

    def load_module(self) -> Any:
        """动态加载领域模块。"""
        return importlib.import_module(self.module)

    def get_builtins(self) -> dict:
        """获取领域内置函数。"""
        try:
            mod = self.load_module()
            return {f: getattr(mod, f) for f in self.functions if hasattr(mod, f)}
        except (ImportError, AttributeError):
            return {}


# ============================================================
# 领域注册表
# ============================================================

class DomainRegistry:
    """领域注册中心：统一管理所有学科/专业/应用领域。"""

    # 预定义领域模板
    _DOMAIN_TEMPLATES: dict[str, dict] = {
        # ─── 核心应用领域 ───
        "AI_DataScience": {
            "display_name": "人工智能与数据科学",
            "description": "机器学习、深度学习、数据挖掘、统计分析",
            "module": "src.domains.ai_data_science",
            "functions": [
                "sigmoid", "relu", "softmax", "cross_entropy",
                "mse", "mae", "log_loss", "accuracy",
                "linear_regression", "logistic_regression",
                "gradient_descent", "adam_update",
                "forward_prop", "backward_prop",
                "relu_deriv", "sigmoid_deriv",
                "dot_product", "matrix_mult", "transpose",
            ],
            "constants": {
                "LR": 0.001,        # 学习率默认值
                "EPOCHS": 100,      # 默认训练轮数
                "BATCH_SIZE": 32,   # 默认批次大小
            },
            "optimization_passes": ["MathaDNNOptPass", "MathaGradientOptPass"],
            "category": "science",
            "targets": ["python", "c", "matha"],
        },
        "SoftwareAppDev": {
            "display_name": "软件与应用程序开发",
            "description": "Web后端、API设计、数据库、架构模式",
            "module": "src.domains.software_app",
            "functions": [
                "http_get", "http_post", "http_put", "http_delete",
                "db_query", "db_insert", "db_update", "db_delete",
                "jwt_decode", "jwt_encode", "bcrypt_hash",
                "middleware_chain", "route_register",
                "cache_get", "cache_set", "cache_invalidate",
                "queue_enqueue", "queue_dequeue",
            ],
            "constants": {
                "DEFAULT_PORT": 8080,
                "CONN_POOL_SIZE": 10,
                "REQUEST_TIMEOUT": 30.0,
            },
            "optimization_passes": ["MathaAPIOptPass"],
            "category": "engineering",
            "targets": ["python", "c", "wasm"],
        },
        "GameImmersion": {
            "display_name": "游戏与沉浸式体验开发",
            "description": "2D/3D游戏、物理引擎、粒子系统、VR/AR",
            "module": "src.domains.game_dev",
            "functions": [
                "game_loop", "sprite_create", "sprite_move", "sprite_collide",
                "particle_emitter", "physics_apply_force", "physics_gravity",
                "audio_play", "audio_stop", "audio_volume",
                "render_2d", "render_3d", "camera_look_at",
                "input_key", "input_mouse", "input_gamepad",
            ],
            "constants": {
                "DEFAULT_FPS": 60,
                "GRAVITY": 9.81,
                "FPS_TARGET": 60.0,
            },
            "optimization_passes": ["MathaGameOptPass", "MathaPhysicsOptPass"],
            "category": "creative",
            "targets": ["wasm", "c", "python"],
        },
        "Automation": {
            "display_name": "自动化与效率提升",
            "description": "工作流自动化、RPA、任务调度、数据处理管道",
            "module": "src.domains.automation",
            "functions": [
                "workflow_run", "task_schedule", "task_retry",
                "pipeline_process", "pipeline_filter", "pipeline_map",
                "file_watch", "auto_backup", "report_generate",
                "cron_add", "cron_remove", "cron_list",
            ],
            "constants": {
                "MAX_RETRIES": 3,
                "RETRY_DELAY": 1.0,
                "DEFAULT_SCHEDULE": "0 * * * *",
            },
            "optimization_passes": ["MathaWorkflowOptPass"],
            "category": "engineering",
            "targets": ["python", "c"],
        },
        "IoTHardware": {
            "display_name": "物联网与硬件控制",
            "description": "传感器、执行器、MQTT、边缘计算、物联网协议",
            "module": "src.domains.iot_hardware",
            "functions": [
                "mqtt_publish", "mqtt_subscribe", "mqtt_connect",
                "sensor_read", "sensor_calibrate",
                "actuator_control", "actuator_pwm",
                "gpio_setup", "gpio_write", "gpio_read",
                "i2c_read", "i2c_write", "spi_transfer",
                "edge_compute", "ota_update",
            ],
            "constants": {
                "MQTT_QOS": 1,
                "SENSOR_SAMPLE_RATE": 100.0,
                "GPIO_PINS": 28,
            },
            "optimization_passes": ["MathaIoTOptPass"],
            "category": "engineering",
            "targets": ["c", "rust", "wasm"],
        },
        "OSNetwork": {
            "display_name": "底层系统与网络安全",
            "description": "操作系统、网络协议、加密、渗透测试",
            "module": "src.domains.os_network",
            "functions": [
                "syscall_exec", "syscall_read", "syscall_write",
                "socket_bind", "socket_listen", "socket_accept",
                "tcp_handshake", "tls_encrypt", "tls_decrypt",
                "hash_md5", "hash_sha256", "hash_blake3",
                "encrypt_aes", "decrypt_aes",
                "packet_parse", "packet_construct",
            ],
            "constants": {
                "PAGE_SIZE": 4096,
                "TCP_PORT_MAX": 65535,
                "AES_KEY_SIZE": 32,
            },
            "optimization_passes": ["MathaSysOptPass"],
            "category": "science",
            "targets": ["c", "rust", "kernel"],
        },
        "BlockchainWeb3": {
            "display_name": "区块链与Web3开发",
            "description": "智能合约、共识算法、加密钱包、DeFi",
            "module": "src.domains.blockchain",
            "functions": [
                "block_create", "block_verify", "chain_validate",
                "hash_block", "merkle_root",
                "sign_transaction", "verify_signature",
                "poW_mine", "poS_validate",
                "smart_contract_deploy", "smart_contract_call",
                "token_transfer", "token_balance",
            ],
            "constants": {
                "BLOCK_TIME": 12.0,
                "DIFFICULTY_ADJUST": 2016,
                "SIG_KEY_SIZE": 256,
            },
            "optimization_passes": ["MathaBlockOptPass"],
            "category": "frontier",
            "targets": ["c", "wasm", "python"],
        },
        "AudioVideo": {
            "display_name": "音视频与多媒体处理",
            "description": "音频合成、视频编码、图像处理、信号处理",
            "module": "src.domains.audio_video",
            "functions": [
                "fft", "ifft", "dft",
                "wav_generate", "wav_parse",
                "huffman_encode", "huffman_decode",
                "jpeg_compress", "png_decode",
                "convolve", "filter_fir", "filter_iir",
                "sample_rate_convert",
            ],
            "constants": {
                "SAMPLE_RATE": 44100.0,
                "BIT_DEPTH": 16,
                "FFT_SIZE": 1024,
            },
            "optimization_passes": ["MathaDSPOptPass", "MathaFFTOptPass"],
            "category": "science",
            "targets": ["c", "python", "wasm"],
        },
        "GraphicsRender": {
            "display_name": "图形学与渲染技术",
            "description": "光线追踪、光栅化、着色器、3D变换",
            "module": "src.domains.graphics",
            "functions": [
                "ray_intersect", "ray_trace", "shade_phong",
                "matrix_translate", "matrix_rotate", "matrix_scale",
                "matrix_multiply", "matrix_invert",
                "triangle_rasterize", "barycentric_interp",
                "texture_sample", "normal_transform",
                "project_perspective", "project_orthographic",
            ],
            "constants": {
                "NEAR_PLANE": 0.1,
                "FAR_PLANE": 1000.0,
                "FOV": 60.0,
            },
            "optimization_passes": ["MathaRenderOptPass"],
            "category": "science",
            "targets": ["c", "wasm", "gpu"],
        },
        "HPC": {
            "display_name": "科学计算与高性能计算",
            "description": "并行计算、矩阵运算、数值方法、MPI/OpenMP",
            "module": "src.domains.hpc",
            "functions": [
                "matrix_mul", "matrix_add", "matrix_transpose",
                "matrix_inverse", "matrix_det",
                "gauss_elim", "gauss_seidel",
                "laplace_solve", "wave_solve", "heat_solve",
                "parallel_reduce", "parallel_scan",
                "fft_parallel", "mpi_bcast", "mpi_send", "mpi_recv",
            ],
            "constants": {
                "DEFAULT_THREADS": 4,
                "BLOCK_SIZE": 64,
                "CONV_TOLERANCE": 1e-10,
            },
            "optimization_passes": ["MathaHPCOptPass", "MathaSIMDPass"],
            "category": "science",
            "targets": ["c", "fortran", "rust"],
        },
        "FinTech": {
            "display_name": "金融科技与量化交易",
            "description": "定价模型、风险管理、回测引擎、风险分析",
            "module": "src.domains.fintech",
            "functions": [
                "black_scholes", "binomial_option",
                "black_scholes_greeks",
                "var_calculate", "cvar_calculate",
                "portfolio_optimize", "夏普比率",
                "backtest_strategy", "monte_carlo_pricer",
                "yield_curve", "duration_convexity",
            ],
            "constants": {
                "RISK_FREE_RATE": 0.03,
                "POSITION_LIMIT": 1000000.0,
                "STOP_LOSS": 0.02,
            },
            "optimization_passes": ["MathaFinOptPass"],
            "category": "science",
            "targets": ["python", "c", "rust"],
        },
        "AutonomousDriving": {
            "display_name": "自动驾驶与具身智能",
            "description": "感知、规划、控制、SLAM、运动学",
            "module": "src.domains.autonomous",
            "functions": [
                "pid_control", "pure_pursuit", "mpc_predict",
                "kalman_filter", "ekf_update", "ukf_predict",
                "kinematics_bicycle", "kinematics_invert",
                "path_planning_rrt", "path_planning_a_star",
                "obstacle_detect", "lane_detect",
                "lidar_point_cloud", "camera_projection",
            ],
            "constants": {
                "MAX_SPEED": 30.0,
                "LOOKAHEAD_DIST": 5.0,
                "CONTROL_FREQ": 100.0,
            },
            "optimization_passes": ["MathaAutoOptPass"],
            "category": "frontier",
            "targets": ["c", "rust", "python"],
        },
        "AerospaceDefense": {
            "display_name": "航空航天与国防工业",
            "description": "轨道力学、弹道、飞行控制、遥测",
            "module": "src.domains.aerospace",
            "functions": [
                "orbit_period", "orbit_velocity", "hohmann_transfer",
                "ballistic_trajectory", "drag_force",
                "thrust_required", "delta_v_budget",
                "attitude_control", "gain_scheduler",
                "telemetry_decode", "error_correction",
            ],
            "constants": {
                "GM_EARTH": 3.986e14,
                "R_EARTH": 6371000.0,
                "MU_EARTH": 1.458e-4,
            },
            "optimization_passes": ["MathaAeroOptPass"],
            "category": "frontier",
            "targets": ["c", "rust"],
        },
        "BioComputing": {
            "display_name": "生物计算与合成生物学",
            "description": "基因组学、蛋白质折叠、代谢网络、系统生物学",
            "module": "src.domains.bio_computing",
            "functions": [
                "dna_translate", "rna_fold", "gc_content",
                "protein_mass", "isoelectric_point",
                "metabolic_flux", "enzyme_kinetics",
                "population_growth", "epidemic_sir",
                "phylogenetic_distance",
            ],
            "constants": {
                "NUCLEOTIDE_MW": 330.0,
                "AMINO_ACID_AVG_MW": 110.0,
                "BOLTZMANN": 1.380649e-23,
            },
            "optimization_passes": ["MathaBioOptPass"],
            "category": "science",
            "targets": ["python", "c"],
        },
        "HardwareReverse": {
            "display_name": "极客硬件与逆向工程",
            "description": "固件提取、协议分析、芯片调试、信号捕获",
            "module": "src.domains.hardware_reverse",
            "functions": [
                "crc32_calculate", "crc16_calculate",
                "bit_field_extract", "bit_field_insert",
                "uart_decode", "uart_encode",
                "spi_parse", "i2c_scan",
                "jtag_read", "jtag_write",
                "firmware_extract", "entropy_check",
            ],
            "constants": {
                "UART_BAUD": 115200,
                "SPI_CLK_MAX": 1000000.0,
                "I2C_ADDR_BITS": 7,
            },
            "optimization_passes": ["MathaHWOptPass"],
            "category": "frontier",
            "targets": ["c", "python"],
        },
        "SpatialMeta": {
            "display_name": "空间计算与元宇宙基础设施",
            "description": "3D空间定位、空间锚点、数字孪生、空间索引",
            "module": "src.domains.spatial_meta",
            "functions": [
                "spatial_anchor_create", "spatial_anchor_get",
                "point_cloud_register", "mesh_reconstruct",
                "occlusion_query", "depth_estimate",
                "spatial_hash", "octree_build", "octree_query",
                "digital_twin_sync",
            ],
            "constants": {
                "ANCHOR_MAX": 1024,
                "POINT_CLOUD_RES": 0.01,
                "OCTREE_DEPTH": 8,
            },
            "optimization_passes": ["MathaSpatialOptPass"],
            "category": "frontier",
            "targets": ["wasm", "c", "python"],
        },
        "AlgoTrading": {
            "display_name": "算法交易与高频撮合引擎",
            "description": "订单簿、撮合引擎、做市策略、延迟优化",
            "module": "src.domains.algo_trading",
            "functions": [
                "orderbook_add", "orderbook_remove", "orderbook_match",
                "orderbook_depth", "orderbook_spread",
                "market_order", "limit_order", "stop_order",
                "maker_fee", "taker_fee",
                "latency_estimate", "throughput_max",
            ],
            "constants": {
                "MATCH_INTERVAL_NS": 100,
                "MAX_ORDER_DEPTH": 1000,
                "MIN_TICK_SIZE": 0.01,
            },
            "optimization_passes": ["MathaTradeOptPass"],
            "category": "frontier",
            "targets": ["c", "rust"],
        },
        "CompChem": {
            "display_name": "计算化学与材料科学",
            "description": "分子模拟、量子化学、晶体学、分子动力学",
            "module": "src.domains.comp_chem",
            "functions": [
                "hartree_fock_iter", "dft_energy",
                "molecular_orbital", "homo_lumo_gap",
                "radial_distribution", "pair_correlation",
                "lattice_energy", "bragg_angle",
                "reaction_rate", "activation_energy",
            ],
            "constants": {
                "PLANCK": 6.62607015e-34,
                "AVOGADRO": 6.02214076e23,
                "BOLTZMANN": 1.380649e-23,
            },
            "optimization_passes": ["MathaChemOptPass"],
            "category": "science",
            "targets": ["c", "fortran", "python"],
        },
        "GreenTech": {
            "display_name": "绿色科技",
            "description": "可再生能源、碳排放、能效优化、环境建模",
            "module": "src.domains.green_tech",
            "functions": [
                "solar_irradiance", "wind_power",
                "battery_capacity", "battery_soc",
                "carbon_footprint", "emission_factor",
                "energy_return_on_investment",
                "thermodynamic_efficiency",
                "hydro_flow", "hydro_power",
            ],
            "constants": {
                "SOLAR_CONSTANT": 1361.0,
                "CO2_PER_KWH": 0.475,
                "WIND_ROTOR_AREA_DEFAULT": 1225.0,
            },
            "optimization_passes": ["MathaGreenOptPass"],
            "category": "science",
            "targets": ["python", "c"],
        },
        "MetaverseArch": {
            "display_name": "元宇宙与虚拟世界的建筑师",
            "description": "虚拟世界构建、经济系统、社交引擎、内容创作",
            "module": "src.domains.metaverse_arch",
            "functions": [
                "world_create", "world_spawn", "world_destroy",
                "avatar_move", "avatar_animate",
                "economy_issue", "economy_transfer", "economy_balance",
                "social_connect", "social_message",
                "asset_mint", "asset_transfer", "assetBurn",
            ],
            "constants": {
                "MAX_AVALARS_PER_WORLD": 10000,
                "TICK_RATE": 30.0,
                "GAS_LIMIT": 21000,
            },
            "optimization_passes": ["MathaMetaOptPass"],
            "category": "frontier",
            "targets": ["wasm", "c", "python"],
        },
        "DigitalRights": {
            "display_name": "数字版权与去中心化信任",
            "description": "数字版权管理、零知识证明、信任网络、NFT",
            "module": "src.domains.digital_rights",
            "functions": [
                "drm_license", "drm_verify",
                "zk_proof_generate", "zk_proof_verify",
                "nft_mint", "nft_transfer", "nft_metadata",
                "trust_score", "reputation_accumulate",
                " watermark_embed", "watermark_extract",
            ],
            "constants": {
                "ZK_CIRCUIT_SIZE": 1024,
                "NFT_GAS_LIMIT": 150000,
                "TRUST_MIN": 0.5,
            },
            "optimization_passes": ["MathaDRMOptPass"],
            "category": "frontier",
            "targets": ["wasm", "c", "python"],
        },
        "CreativeCoding": {
            "display_name": "创意编程与艺术表达",
            "description": "生成艺术、数据可视化、交互艺术、创意计算",
            "module": "src.domains.creative_coding",
            "functions": [
                "noise_2d", "noise_3d", "perlin_noise",
                "flow_field", "particle_system", "attraction_force",
                "fractal_dim", "mandelbrot_iter", "julius_iter",
                "color_hsl_to_rgb", "color_lerp",
                "audio_reactive", "visual_midi",
            ],
            "constants": {
                "CANVAS_WIDTH": 800,
                "CANVAS_HEIGHT": 600,
                "PALETTE_SIZE": 16,
            },
            "optimization_passes": ["MathaCreativeOptPass"],
            "category": "creative",
            "targets": ["wasm", "python", "c"],
        },
        "GeneticAlgorithm": {
            "display_name": "遗传算法与AI编写代码",
            "description": "进化计算、遗传算法、神经进化、自动编程",
            "module": "src.domains.genetic_algo",
            "functions": [
                "ga_evolve", "ga_select", "ga_crossover", "ga_mutate",
                "fitness_eval", "elitism_preserve",
                "neuro_evolve", "nesma_estimate",
                "code_generation", "code_optimizer",
                "hyperparameter_search",
            ],
            "constants": {
                "POPULATION_SIZE": 100,
                "MUTATION_RATE": 0.01,
                "CROSSOVER_RATE": 0.8,
            },
            "optimization_passes": ["MathaGAOptPass"],
            "category": "frontier",
            "targets": ["python", "c"],
        },
        "QuantumComputing": {
            "display_name": "量子计算",
            "description": "量子门、量子电路、量子算法、量子纠错",
            "module": "src.domains.quantum_compute",
            "functions": [
                "hadamard", "pauli_x", "pauli_y", "pauli_z",
                "cnot", "toffoli", "swap",
                "quantum_fourier", "grover_iter",
                "shor_period", "quantum_teleport",
                "bell_state", "ghz_state",
                "gate_decompose", "circuit_depth",
            ],
            "constants": {
                "QUBITS_MAX": 30,
                "DECOHERENCE_TIME": 1e-3,
                "ERROR_RATE": 1e-3,
            },
            "optimization_passes": ["MathaQuantumOptPass"],
            "category": "frontier",
            "targets": ["python", "c"],
        },
        "ChaosFractal": {
            "display_name": "混沌理论与分型",
            "description": "混沌系统、分形几何、吸引子、非线性动力学",
            "module": "src.domains.chaos_fractal",
            "functions": [
                "lorenz_attractor", "lorenz_deriv",
                "henon_map", "logistic_map",
                "mandelbrot_set", "julia_set",
                "fractal_dimension", "lyapunov_exp",
                "bifurcation_diagram", "attractor_draw",
            ],
            "constants": {
                "LORENZ_SIGMA": 10.0,
                "LORENZ_RHO": 28.0,
                "LORENZ_BETA": 8.0/3.0,
            },
            "optimization_passes": ["MathaChaosOptPass"],
            "category": "science",
            "targets": ["python", "wasm", "c"],
        },
        "ComputationalLaw": {
            "display_name": "计算法学",
            "description": "法律推理、案例匹配、法规分析、智能合约审计",
            "module": "src.domains.computational_law",
            "functions": [
                "case_match", "precedent_search",
                "regulation_analyze", "clause_extract",
                "contract_verify", "compliance_check",
                "sentencing_range", "liability_assess",
                "legal_reasoning", "argument_builder",
            ],
            "constants": {
                "MAX_CASES": 1000,
                "SIMILARITY_THRESHOLD": 0.7,
                "MAX_CLAUSE_DEPTH": 5,
            },
            "optimization_passes": ["MathaLawOptPass"],
            "category": "frontier",
            "targets": ["python", "c"],
        },
        "GeekGray": {
            "display_name": "极客文化与灰产边缘",
            "description": "CTF、漏洞研究、安全审计、渗透测试",
            "module": "src.domains.geek_gray",
            "functions": [
                "buffer_overflow_check", "format_string_detect",
                "xor_decode", "base64_decode", "rot_n",
                "stack_canary_check", "aslr_entropy",
                "shellcode_search", "payload_generate",
                "exploit_simplify", "reverse_engineer",
            ],
            "constants": {
                "MAX_PAYLOAD_SIZE": 4096,
                "STACK_CANARY_LEN": 8,
                "ASLR_BITS": 28,
            },
            "optimization_passes": ["MathaGeekOptPass"],
            "category": "frontier",
            "targets": ["c", "python"],
        },
    }

    def __init__(self) -> None:
        self._domains: dict[str, DomainMeta] = {}
        self._loaded_modules: dict[str, Any] = {}
        self._events: dict[str, list[Callable]] = {}

    def register(self, domain_key: str, meta: Optional[DomainMeta] = None) -> bool:
        """注册领域。"""
        if domain_key in self._DOMAIN_TEMPLATES:
            tpl = self._DOMAIN_TEMPLATES[domain_key]
            meta = DomainMeta(
                name=domain_key,
                display_name=tpl["display_name"],
                description=tpl["description"],
                module=tpl["module"],
                functions=tpl["functions"],
                constants=tpl["constants"],
                optimization_passes=tpl["optimization_passes"],
                targets=tpl["targets"],
                category=tpl["category"],
            )
        if meta:
            self._domains[domain_key] = meta
            return True
        return False

    def unregister(self, domain_key: str) -> bool:
        """注销领域。"""
        if domain_key in self._domains:
            del self._domains[domain_key]
            self._loaded_modules.pop(domain_key, None)
            return True
        return False

    def get(self, domain_key: str) -> Optional[DomainMeta]:
        """获取领域元数据。"""
        return self._domains.get(domain_key)

    def load(self, domain_key: str) -> Optional[Any]:
        """加载领域模块。"""
        if domain_key not in self._domains:
            return None
        if domain_key not in self._loaded_modules:
            try:
                mod = self._domains[domain_key].load_module()
                self._loaded_modules[domain_key] = mod
            except ImportError:
                return None
        return self._loaded_modules.get(domain_key)

    def get_builtins(self, domain_key: str) -> dict:
        """获取领域内置函数。"""
        mod = self.load(domain_key)
        if not mod:
            return {}
        meta = self._domains[domain_key]
        return {f: getattr(mod, f, None) for f in meta.functions if hasattr(mod, f)}

    def list_domains(self, category: Optional[str] = None) -> list[dict]:
        """列出所有领域。"""
        result = []
        for key, meta in self._domains.items():
            if category is None or meta.category == category:
                loaded = key in self._loaded_modules
                result.append({
                    "key": key,
                    "name": meta.display_name,
                    "category": meta.category,
                    "functions": len(meta.functions),
                    "loaded": loaded,
                    "targets": meta.targets,
                })
        return result

    def add_callback(self, event: str, callback: Callable) -> None:
        """注册事件回调。"""
        if event not in self._events:
            self._events[event] = []
        self._events[event].append(callback)

    def fire(self, event: str, **kwargs) -> None:
        """触发事件。"""
        for cb in self._events.get(event, []):
            try:
                cb(**kwargs)
            except Exception:
                pass

    def get_stats(self) -> dict:
        """获取注册表统计。"""
        loaded = sum(1 for k in self._domains if k in self._loaded_modules)
        return {
            "total_domains": len(self._domains),
            "loaded_domains": loaded,
            "categories": {
                cat: sum(1 for d in self._domains.values() if d.category == cat)
                for cat in {"general", "science", "engineering", "creative", "frontier"}
            },
        }


# ============================================================
# 单例注册表
# ============================================================

_registry: Optional[DomainRegistry] = None


def get_registry() -> DomainRegistry:
    """获取全局领域注册表。"""
    global _registry
    if _registry is None:
        _registry = DomainRegistry()
        # 注册所有预定义领域
        for key in DomainRegistry._DOMAIN_TEMPLATES:
            _registry.register(key)
    return _registry


def domain_compile(source: str, target: str, domain: Optional[str] = None) -> str:
    """使用指定领域编译源码。"""
    registry = get_registry()
    if domain and domain in registry._domains:
        # 加载领域内置函数
        builtins = registry.get_builtins(domain)
        # 这里可以扩展编译器的 builtins 注册
    from src.mir_converter import convert
    return convert(source, "matha", target)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "DomainMeta",
    "DomainRegistry",
    "get_registry",
    "domain_compile",
]
