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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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
        # ─── IO系统 ───
        "IOSystem": {
            "display_name": "IO系统",
            "description": "文件读写、标准IO、流操作、数据序列化",
            "module": "src.domains.io_system",
            "functions": [
                "文件读取", "文件写入", "文件追加", "文件存在",
                "文件大小", "文件删除", "文件列表", "创建目录",
                "文件信息", "标准输出", "标准错误", "标准输入",
                "输出缓冲区", "JSON编码", "JSON解码",
                "Base64编码", "Base64解码",
                "内存流打开", "内存流写入", "内存流读取", "内存流重置",
            ],
            "constants": {"DEFAULT_ENCODING": "utf-8", "BUFFER_SIZE": 4096},
            "optimization_passes": [],
            "category": "engineering",
            "targets": ["python", "c", "wasm"],
        },
        # ─── 文件系统 ───
        "FileSystem": {
            "display_name": "文件系统",
            "description": "路径操作、目录管理、权限、符号链接",
            "module": "src.domains.filesystem",
            "functions": [
                "路径拼接", "路径基名", "路径目录", "路径扩展名",
                "路径规范化", "路径绝对化", "路径解析", "路径存在",
                "路径是否为文件", "路径是否为目录",
                "创建目录", "删除目录", "递归删除目录", "目录列表",
                "目录树", "磁盘使用", "文件权限", "修改权限",
                "创建符号链接", "解析符号链接", "路径信息",
            ],
            "constants": {"DEFAULT_PERMISSION": "755", "PAGE_SIZE": 4096},
            "optimization_passes": [],
            "category": "engineering",
            "targets": ["python", "c"],
        },
        # ─── 网络 ───
        "Networking": {
            "display_name": "网络通信",
            "description": "Socket通信、HTTP客户端、DNS、URL处理",
            "module": "src.domains.networking",
            "functions": [
                "网络连接", "网络绑定", "HTTP_GET", "HTTP_POST",
                "HTTP请求", "URL解析", "URL构建", "URL编码", "URL解码",
                "DNS解析", "DNS查询", "网络状态", "Ping检测",
            ],
            "constants": {"DEFAULT_TIMEOUT": 10.0, "MAX_CONNECTIONS": 100},
            "optimization_passes": ["MathaNetOptPass"],
            "category": "engineering",
            "targets": ["python", "c", "wasm"],
        },
        # ─── 时间 ───
        "TimeModule": {
            "display_name": "时间模块",
            "description": "时间日期操作、计时器、时区、调度",
            "module": "src.domains.time_module",
            "functions": [
                "获取时间戳", "获取日期", "获取日期时间", "获取UTC时间",
                "格式化时间", "解析时间", "当前时间", "当前日期",
                "日期加减", "日期差", "星期几", "闰年判断",
                "月份天数", "创建计时器", "时区偏移", "时区转换",
                "注册任务", "执行待办", "待办列表",
            ],
            "constants": {"DEFAULT_FPS": 60, "MAX_TASKS": 100},
            "optimization_passes": [],
            "category": "general",
            "targets": ["python", "c"],
        },
        # ─── 图形引擎 ───
        "GraphicsEngine": {
            "display_name": "图形引擎",
            "description": "Canvas绘图、2D图形、颜色系统、字体渲染",
            "module": "src.domains.graphics_engine",
            "functions": [
                "创建画布", "清除画布", "设置填充", "设置描边",
                "填充矩形", "描边矩形", "填充圆形", "描边圆形",
                "画线", "画文字", "画布JSON", "保存画布",
                "颜色红", "颜色绿", "颜色蓝", "颜色白", "颜色黑",
                "颜色从十六进制", "创建渐变", "创建字体", "创建渲染器",
            ],
            "constants": {"DEFAULT_WIDTH": 800, "DEFAULT_HEIGHT": 600},
            "optimization_passes": ["MathaRenderOptPass"],
            "category": "creative",
            "targets": ["wasm", "python", "c"],
        },
        # ─── 办公文档 ───
        "OfficeDocs": {
            "display_name": "办公文档",
            "description": "文档处理、电子表格、演示文稿、数据分析",
            "module": "src.domains.office_docs",
            "functions": [
                "创建文档", "文档添加文本", "文档添加标题",
                "文档加粗", "文档斜体", "文档列表",
                "文档转Markdown", "文档转HTML",
                "创建表格", "表格设置", "表格获取", "表格公式",
                "表格计算", "表格导出CSV",
                "创建演示文稿", "添加幻灯片", "添加列表幻灯片",
                "下一张幻灯片", "数据分析", "柱状图", "折线图", "饼图",
            ],
            "constants": {"DEFAULT_ROWS": 100, "DEFAULT_COLS": 26},
            "optimization_passes": [],
            "category": "engineering",
            "targets": ["python", "wasm"],
        },
        # ─── 操作系统 ───
        "OSModule": {
            "display_name": "操作系统",
            "description": "进程管理、内存管理、线程、信号量、系统信息",
            "module": "src.domains.os_module",
            "functions": [
                "创建进程管理器", "创建进程", "终止进程", "获取进程",
                "进程列表", "创建内存管理器", "内存分配", "内存释放",
                "内存信息", "创建线程管理器", "创建线程", "线程列表",
                "创建信号量", "信号量获取", "信号量释放",
                "创建事件", "事件设置", "事件等待",
                "创建互斥锁", "互斥加锁", "互斥解锁",
                "获取系统信息", "获取CPU信息", "获取内存信息",
                "获取环境变量", "设置环境变量", "执行命令", "运行脚本",
            ],
            "constants": {"DEFAULT_MEMORY": 1048576, "MAX_PROCESSES": 256},
            "optimization_passes": ["MathaSysOptPass"],
            "category": "engineering",
            "targets": ["python", "c"],
        },
        # ─── 显示器 ───
        "DisplayMonitor": {
            "display_name": "显示器管理",
            "description": "显示器配置、分辨率管理、多屏、渲染管线",
            "module": "src.domains.display_monitor",
            "functions": [
                "创建显示器管理器", "创建分辨率", "添加显示器",
                "获取分辨率", "设置分辨率", "设置显示模式",
                "获取显示器数量", "列出显示器", "截图",
                "显示统计", "管线统计",
            ],
            "constants": {"DEFAULT_WIDTH": 1920, "DEFAULT_HEIGHT": 1080},
            "optimization_passes": ["MathaDisplayOptPass"],
            "category": "creative",
            "targets": ["python", "c"],
        },
        # ─── 媒体录制 ───
        "MediaRecorder": {
            "display_name": "媒体录制",
            "description": "屏幕录制、视频捕获、音频录制、编码",
            "module": "src.domains.media_recorder",
            "functions": [
                "创建视频录制器", "创建音频录制器",
                "开始录制", "暂停录制", "恢复录制", "停止录制",
                "录制状态", "录制统计", "列出片段",
                "开始录音", "停止录音", "录音状态",
                "设置音频源", "编码片段",
            ],
            "constants": {"DEFAULT_FORMAT": "mp4", "DEFAULT_FPS": 30},
            "optimization_passes": ["MathaMediaOptPass"],
            "category": "creative",
            "targets": ["python", "c"],
        },
        # ─── 媒体播放 ───
        "MediaPlayer": {
            "display_name": "媒体播放",
            "description": "视频/音频播放、播放控制、播放列表、均衡器",
            "module": "src.domains.media_player",
            "functions": [
                "创建媒体播放器", "创建音轨", "加载音轨",
                "播放", "暂停", "停止", "跳转",
                "设置音量", "设置速度", "设置均衡器",
                "添加字幕", "获取统计", "获取位置",
                "创建播放列表", "下一曲", "上一曲",
            ],
            "constants": {"DEFAULT_VOLUME": 1.0, "DEFAULT_SPEED": 1.0},
            "optimization_passes": ["MathaPlayerOptPass"],
            "category": "creative",
            "targets": ["python", "c"],
        },
        # ─── Web框架 ───
        "WebFramework": {
            "display_name": "Web框架",
            "description": "HTTP服务器、路由、中间件、模板、WebSocket",
            "module": "src.domains.web_framework",
            "functions": [
                "创建Web服务器", "创建Web应用",
                "添加路由", "添加GET", "添加POST",
                "添加中间件", "启动服务器", "停止服务器",
                "处理请求", "添加模板", "渲染模板",
                "创建WebSocket", "获取统计",
            ],
            "constants": {"DEFAULT_PORT": 8080, "DEFAULT_HOST": "127.0.0.1"},
            "optimization_passes": ["MathaWebOptPass"],
            "category": "engineering",
            "targets": ["python", "c"],
        },
        # ─── 数据库 ───
        "Database": {
            "display_name": "数据库连接",
            "description": "数据库连接、查询构建器、事务、ORM",
            "module": "src.domains.database",
            "functions": [
                "创建数据库", "创建连接", "连接数据库",
                "执行查询", "执行SQL",
                "开始事务", "提交事务", "回滚事务",
                "注册模型", "获取统计",
            ],
            "constants": {"DEFAULT_DB": "sqlite", "POOL_SIZE": 5},
            "optimization_passes": ["MathaDBOptPass"],
            "category": "engineering",
            "targets": ["python", "c"],
        },
        # ─── 安全加密 ───
        "Security": {
            "display_name": "加密安全",
            "description": "哈希、加密、签名、认证、随机数",
            "module": "src.domains.security",
            "functions": [
                "创建哈希引擎", "创建加密引擎", "创建签名引擎",
                "创建认证管理器", "创建安全随机数",
                "MD5哈希", "SHA256哈希", "SHA512哈希",
                "生成密钥", "加密数据", "解密数据",
                "签名", "验证签名",
                "生成令牌", "验证令牌", "生成随机数",
            ],
            "constants": {"DEFAULT_HASH": "sha256", "DEFAULT_ENC": "aes-256"},
            "optimization_passes": ["MathaSecOptPass"],
            "category": "engineering",
            "targets": ["python", "c"],
        },
        # ─── 神经网络 ───
        "NeuralNetwork": {
            "display_name": "神经网络",
            "description": "前馈网络、卷积、循环、训练",
            "module": "src.domains.neural_network",
            "functions": [
                "创建神经网络", "创建CNN", "创建RNN",
                "添加层", "前向传播", "训练模型", "预测",
                "添加卷积层", "添加池化", "添加LSTM", "添加GRU",
            ],
            "constants": {"DEFAULT_LAYERS": 3, "DEFAULT_HIDDEN": 64},
            "optimization_passes": ["MathaNNOptPass"],
            "category": "frontier",
            "targets": ["python", "c"],
        },
        # ─── 并发编程 ───
        "Concurrent": {
            "display_name": "并发编程",
            "description": "线程池、异步、CSP、Actor模型",
            "module": "src.domains.concurrent",
            "functions": [
                "创建并发管理器", "创建线程池", "创建事件循环",
                "创建通道", "创建Actor",
                "提交任务", "等待所有", "获取并发统计",
                "启动事件循环", "停止事件循环",
            ],
            "constants": {"DEFAULT_THREADS": 4, "DEFAULT_BUFFER": 10},
            "optimization_passes": ["MathaConcOptPass"],
            "category": "engineering",
            "targets": ["python", "c"],
        },
        # ─── 数据科学 ───
        "DataScience": {
            "display_name": "数据科学",
            "description": "数据集、特征工程、统计分析、模型评估",
            "module": "src.domains.data_science",
            "functions": [
                "创建数据科学", "创建数据集", "创建特征提取器",
                "评估模型", "加载CSV", "归一化",
                "划分训练测试", "准确率",
            ],
            "constants": {"DEFAULT_FEATURES": 10, "DEFAULT_SAMPLES": 100},
            "optimization_passes": ["MathaDSOptPass"],
            "category": "science",
            "targets": ["python", "c"],
        },
        # ─── 区块链 ───
        "Blockchain": {
            "display_name": "区块链",
            "description": "区块链、交易、智能合约、共识、钱包",
            "module": "src.domains.blockchain",
            "functions": [
                "创建区块链", "创建交易", "挖矿",
                "部署合约", "创建钱包", "验证链", "获取余额",
            ],
            "constants": {"DEFAULT_CONSENSUS": "pow", "MAX_TXS": 1000},
            "optimization_passes": ["MathaBCOptPass"],
            "category": "frontier",
            "targets": ["python", "c"],
        },
        # ─── 量子计算 ───
        "Quantum": {
            "display_name": "量子计算",
            "description": "量子比特、量子门、量子电路、量子算法",
            "module": "src.domains.quantum",
            "functions": [
                "创建量子计算机", "创建量子比特", "应用量子门",
                "创建量子电路", "运行算法", "测量",
                "量子纠缠", "Grover搜索", "Shor分解",
            ],
            "constants": {"DEFAULT_QUBITS": 2, "MAX_DEPTH": 100},
            "optimization_passes": ["MathaQOptPass"],
            "category": "frontier",
            "targets": ["python", "c"],
        },
        # ─── 音视频 ───
        "AudioVideo": {
            "display_name": "音视频处理",
            "description": "音频合成、视频编辑、特效、转码",
            "module": "src.domains.audio_video",
            "functions": [
                "创建音频引擎", "创建视频编辑器",
                "生成音调", "添加特效", "混音", "导出音频",
                "加载视频", "剪辑视频", "渲染视频", "合并视频",
            ],
            "constants": {"DEFAULT_FPS": 30, "DEFAULT_SAMPLE_RATE": 44100},
            "optimization_passes": ["MathaAVOptPass"],
            "category": "creative",
            "targets": ["python", "c"],
        },
        # ─── 化学 ───
        "Chemistry": {
            "display_name": "化学",
            "description": "分子结构、化学反应、量子化学、周期表",
            "module": "src.domains.chemistry",
            "functions": [
                "创建化学引擎", "创建分子", "添加原子",
                "添加化学键", "创建反应", "获取元素", "计算能量",
            ],
            "constants": {"DEFAULT_TEMPERATURE": 298},
            "optimization_passes": ["MathaChemOptPass"],
            "category": "science",
            "targets": ["python", "c"],
        },
        # ─── 天文学 ───
        "Astronomy": {
            "display_name": "天文学",
            "description": "星体、轨道、望远镜、星座",
            "module": "src.domains.astronomy",
            "functions": [
                "创建天文引擎", "创建星表", "添加天体",
                "计算轨道", "查找星座", "追踪天体",
            ],
            "constants": {"DEFAULT_FOCUS": 1000},
            "optimization_passes": ["MathaAstroOptPass"],
            "category": "science",
            "targets": ["python", "c"],
        },
        # ─── 音乐 ───
        "Music": {
            "display_name": "音乐",
            "description": "音阶、和弦、音乐合成、MIDI",
            "module": "src.domains.music",
            "functions": [
                "创建音乐引擎", "创建音阶", "创建和弦",
                "创建旋律", "添加音符", "播放", "生成MIDI", "移调",
            ],
            "constants": {"DEFAULT_TEMPO": 120},
            "optimization_passes": ["MathaMusicOptPass"],
            "category": "creative",
            "targets": ["python", "c"],
        },
        # ─── 包管理 ───
        "PackageManager": {
            "display_name": "包管理",
            "description": "包安装、依赖解析、版本管理",
            "module": "src.package_manager",
            "functions": [
                "创建包管理器", "解析依赖", "安装包",
                "卸载包", "列出包", "注册包",
            ],
            "constants": {"DEFAULT_VERSION": "1.0.0"},
            "optimization_passes": ["MathaPkgOptPass"],
            "category": "tooling",
            "targets": ["python", "c"],
        },
        # ─── 类型检查 ───
        "TypeChecker": {
            "display_name": "类型检查",
            "description": "静态类型推断、类型验证",
            "module": "src.type_checker",
            "functions": [
                "检查类型", "推断类型", "定义类型",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "tooling",
            "targets": ["python"],
        },
        # ─── 测试框架 ───
        "TestFramework": {
            "display_name": "测试框架",
            "description": "单元测试、断言、测试套件",
            "module": "src.test_framework",
            "functions": [
                "创建测试运行器", "断言相等", "断言为真", "断言为假",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "tooling",
            "targets": ["python"],
        },
        # ─── 代码格式化 ───
        "CodeFormatter": {
            "display_name": "代码格式化",
            "description": "代码自动格式化",
            "module": "src.code_formatter",
            "functions": [
                "格式化代码",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "tooling",
            "targets": ["python"],
        },
        # ─── 文档生成 ───
        "DocGenerator": {
            "display_name": "文档生成",
            "description": "自动生成API文档",
            "module": "src.doc_generator",
            "functions": [
                "创建文档生成器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "tooling",
            "targets": ["python"],
        },
        # ─── 异步编程 ───
        "AsyncSupport": {
            "display_name": "异步编程",
            "description": "async/await、协程、事件循环",
            "module": "src.async_support",
            "functions": [
                "创建异步管理器", "运行异步", "并行运行", "异步等待",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "tooling",
            "targets": ["python"],
        },
        # ─── 科学计算 ───
        "Science": {
            "display_name": "科学计算",
            "description": "数组运算、矩阵操作、数值分析",
            "module": "src.science",
            "functions": [
                "创建数组", "创建矩阵", "创建数据集",
                "矩阵乘法", "均值", "标准差", "方差", "线性空间",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "science",
            "targets": ["python"],
        },
        # ─── 数据可视化 ───
        "Visualization": {
            "display_name": "数据可视化",
            "description": "图表生成、数据可视化",
            "module": "src.visualization",
            "functions": [
                "创建图表", "折线图", "柱状图", "散点图", "直方图",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "science",
            "targets": ["python"],
        },
        # ─── 符号计算 ───
        "Symbolic": {
            "display_name": "符号计算",
            "description": "符号推导、解析求值、方程求解",
            "module": "src.symbolic",
            "functions": [
                "创建符号", "解析表达式", "求导", "求解方程",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "science",
            "targets": ["python"],
        },
        # ─── 机器学习 ───
        "ML": {
            "display_name": "机器学习",
            "description": "分类、回归、聚类",
            "module": "src.ml",
            "functions": [
                "创建线性回归", "创建逻辑回归", "创建KMeans",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "ai",
            "targets": ["python"],
        },
        # ─── 安全增强 ───
        "SecurityEnhanced": {
            "display_name": "安全增强",
            "description": "TLS/SSL、OAuth2、JWT",
            "module": "src.security_enhanced",
            "functions": [
                "创建SSL上下文", "生成证书", "哈希密码",
                "创建OAuth2客户端", "生成JWT",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "security",
            "targets": ["python"],
        },
        "HTTPServer": {
            "display_name": "HTTP服务器",
            "description": "HTTP/HTTPS服务、反向代理、WebSocket",
            "module": "src.http_server",
            "functions": [
                "创建HTTP服务器", "创建反向代理", "创建WebSocket处理器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "web",
            "targets": ["python"],
        },
        "GitVersionControl": {
            "display_name": "Git版本控制",
            "description": "版本控制、分支管理、合并",
            "module": "src.git",
            "functions": [
                "创建Git仓库", "创建Git配置",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "devops",
            "targets": ["python"],
        },
        "BuildSystem": {
            "display_name": "构建系统",
            "description": "Make/CMake兼容构建工具",
            "module": "src.build_system",
            "functions": [
                "创建构建管理器", "创建Makefile", "创建CMakeLists",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "devops",
            "targets": ["python"],
        },
        "DatabaseEngine": {
            "display_name": "数据库引擎",
            "description": "SQL引擎、事务、索引、查询优化",
            "module": "src.database_engine",
            "functions": [
                "创建数据库", "创建数据库连接池",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "data",
            "targets": ["python"],
        },
        "AIFramework": {
            "display_name": "AI框架",
            "description": "自动微分、计算图、神经网络、深度学习",
            "module": "src.ai_framework",
            "functions": [
                "创建张量", "创建模型", "创建线性层", "创建ReLU",
                "创建Softmax", "创建Dropout", "创建BatchNorm",
                "创建Adam", "创建SGD", "创建训练器",
                "创建神经网络", "创建自动微分",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "ai",
            "targets": ["python"],
        },
        "CompilerBackend": {
            "display_name": "编译器后端",
            "description": "LLVM、WASM、AOT编译、JIT编译",
            "module": "src.compiler_backend",
            "functions": [
                "创建编译器", "创建WASM编译器", "创建AOT编译器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "compiler",
            "targets": ["python"],
        },
        "GameEngine": {
            "display_name": "游戏引擎",
            "description": "3D渲染、物理、音频、动画",
            "module": "src.game_engine_extended",
            "functions": [
                "创建渲染器", "创建物理世界", "创建音频引擎",
                "创建动画控制器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "game",
            "targets": ["python"],
        },
        "SecurityComplete": {
            "display_name": "完整安全",
            "description": "bcrypt、Argon2、libsodium、密码学全栈",
            "module": "src.security_complete",
            "functions": [
                "创建哈希管理器", "创建bcrypt", "创建Argon2",
                "创建scrypt", "创建加密器", "创建HMAC",
                "创建证书", "创建SSL上下文", "创建JWT",
                "创建密钥管理器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "security",
            "targets": ["python"],
        },
        "UIFramework": {
            "display_name": "UI框架",
            "description": "React/Vue/Svelte兼容声明式UI",
            "module": "src.ui_framework",
            "functions": [
                "创建组件", "创建元素", "创建容器",
                "创建按钮", "创建输入", "创建路由",
                "创建状态管理器", "创建事件发射器",
                "创建虚拟DOM", "创建CSS",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "frontend",
            "targets": ["python"],
        },
        "DevOps": {
            "display_name": "DevOps工具",
            "description": "CI/CD、监控、日志、服务发现",
            "module": "src.devops",
            "functions": [
                "创建流水线运行器", "创建日志聚合器",
                "创建指标收集器", "创建告警管理器",
                "创建健康检查", "创建服务发现",
                "创建配置管理器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "devops",
            "targets": ["python"],
        },
        "BlockchainFull": {
            "display_name": "区块链引擎",
            "description": "EVM、智能合约、共识机制、代币",
            "module": "src.blockchain_full",
            "functions": [
                "创建区块链", "创建智能合约引擎", "创建代币",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "blockchain",
            "targets": ["python"],
        },
        "AudioVideoFull": {
            "display_name": "音视频引擎",
            "description": "编解码、流媒体、特效",
            "module": "src.audio_video_full",
            "functions": [
                "创建视频编码器", "创建音频编码器",
                "创建视频解码器", "创建音频解码器",
                "创建滤镜图", "创建媒体播放器",
                "创建RTMP流媒体",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "media",
            "targets": ["python"],
        },
        "Geospatial": {
            "display_name": "地理空间",
            "description": "GIS、坐标转换、空间分析",
            "module": "src.geospatial_full",
            "functions": [
                "创建坐标转换器", "创建空间分析器",
                "创建矢量图层", "创建栅格数据",
                "创建瓦片管理器", "创建GeoJSON",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "geospatial",
            "targets": ["python"],
        },
        "Robotics": {
            "display_name": "机器人引擎",
            "description": "ROS、运动规划、SLAM、传感器",
            "module": "src.robotics_full",
            "functions": [
                "创建机器人", "创建运动规划器", "创建SLAM",
                "创建传感器驱动", "创建控制器",
                "创建轨迹", "创建夹爪",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "robotics",
            "targets": ["python"],
        },
        "OSEXT": {
            "display_name": "操作系统扩展",
            "description": "虚拟内存、共享内存、信号量、消息队列、管道",
            "module": "src.os_extended",
            "functions": [
                "创建虚拟内存", "创建共享内存",
                "创建信号量", "创建消息队列", "创建管道",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "os",
            "targets": ["python"],
        },
        "OSKERNEL": {
            "display_name": "操作系统内核",
            "description": "进程调度、内存管理、文件系统、网络栈、设备驱动",
            "module": "src.os_kernel",
            "functions": [
                "创建调度器", "创建内存管理器",
                "创建文件系统", "创建网络栈",
                "创建设备驱动", "创建进程间通信",
                "创建信号管理器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "os",
            "targets": ["python"],
        },
        "HAL": {
            "display_name": "硬件抽象层",
            "description": "CPU、中断、DMA、定时器、I/O端口",
            "module": "src.hal",
            "functions": [
                "创建CPU", "创建中断控制器",
                "创建DMA控制器", "创建定时器",
                "创建PIC", "创建HAL",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "hardware",
            "targets": ["python"],
        },
        "STORAGE": {
            "display_name": "存储引擎",
            "description": "B+树、LSM树、WAL、缓冲池",
            "module": "src.storage_engine",
            "functions": [
                "创建B+树", "创建LSM树",
                "创建WAL", "创建B树数据库",
                "创建缓冲池",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "storage",
            "targets": ["python"],
        },
        "RUNTIME": {
            "display_name": "运行时",
            "description": "垃圾回收、字节码、JIT、异常处理",
            "module": "src.runtime_foundation",
            "functions": [
                "创建垃圾回收器", "创建字节码解释器",
                "创建JIT编译器", "创建异常处理器",
                "创建运行时",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "runtime",
            "targets": ["python"],
        },
        "NETWORK_DRIVER": {
            "display_name": "网络驱动",
            "description": "TCP/IP协议栈、路由、DNS、套接字",
            "module": "src.network_driver",
            "functions": [
                "创建网络驱动",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "network",
            "targets": ["python"],
        },
        "FS_DRIVER": {
            "display_name": "文件系统驱动",
            "description": "FAT/NTFS/ext4、分区管理、卷管理",
            "module": "src.fs_driver",
            "functions": [
                "创建文件系统驱动",
                "创建分区管理器",
                "创建卷管理器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "storage",
            "targets": ["python"],
        },
        "DEVICE_DRIVER": {
            "display_name": "设备驱动框架",
            "description": "GPU/音频/USB/SSD/网卡驱动",
            "module": "src.device_driver",
            "functions": [
                "创建GPU设备", "创建音频设备",
                "创建USB控制器", "创建固态硬盘",
                "创建网卡设备", "创建驱动注册表",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "hardware",
            "targets": ["python"],
        },
        "OS_API": {
            "display_name": "操作系统API",
            "description": "POSIX/Win32/VFS/进程表/系统调用",
            "module": "src.os_api",
            "functions": [
                "创建POSIX库", "创建Win32接口",
                "创建系统调用表", "创建虚拟文件系统",
                "创建进程表", "创建操作系统API",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "system",
            "targets": ["python"],
        },
        "GRAPHICS_DRIVER": {
            "display_name": "图形驱动",
            "description": "OpenGL/Vulkan/D3D12、向量矩阵",
            "module": "src.graphics_driver",
            "functions": [
                "创建图形上下文", "创建Vulkan实例",
                "创建D3D12设备", "创建三维向量",
                "创建四阶矩阵",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "graphics",
            "targets": ["python"],
        },
        "CRYPTO_FOUNDATION": {
            "display_name": "密码学基座",
            "description": "哈希/对称加密/非对称/PKI/TLS",
            "module": "src.crypto_foundation",
            "functions": [
                "创建密码学系统", "创建哈希引擎",
                "创建对称加密", "创建公钥基础设施",
                "创建TLS会话", "创建密钥交换",
                "创建机密存储",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "security",
            "targets": ["python"],
        },
        "MATH_FOUNDATION": {
            "display_name": "数学基座",
            "description": "大数/FFT/线性代数/特殊函数/数值分析",
            "module": "src.math_foundation",
            "functions": [
                "创建数学基座", "创建大整数",
                "创建高精度浮点", "创建四元数",
                "创建快速傅里叶变换", "创建线性代数",
                "创建数值分析",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "math",
            "targets": ["python"],
        },
        "BROWSER": {
            "display_name": "浏览器内核",
            "description": "HTML解析/CSS层叠/盒布局/JS引擎/软件光栅",
            "module": "src.browser_engine",
            "functions": [
                "创建浏览器内核", "创建HTML解析器",
                "创建CSS解析器", "创建布局引擎",
                "创建JS解释器", "创建渲染器",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "frontend",
            "targets": ["python"],
        },
        "MOBILE": {
            "display_name": "移动SDK",
            "description": "iOS/Android生命周期/组件/传感器/推送",
            "module": "src.mobile_sdk",
            "functions": [
                "创建移动应用", "创建组件构建器",
                "创建弹性布局", "创建传感器中枢",
                "创建权限管理器", "创建导航栈",
                "创建应用包",
            ],
            "constants": {},
            "optimization_passes": [],
            "category": "frontend",
            "targets": ["python"],
        },
    }

    def __init__(self) -> None:
        self._domains: dict[str, DomainMeta] = {}
        self._loaded_modules: dict[str, Any] = {}
        self._events: dict[str, list[Callable]] = {}

    def register(self, domain_key: str, meta: DomainMeta | None = None) -> bool:
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

    def get(self, domain_key: str) -> DomainMeta | None:
        """获取领域元数据。"""
        return self._domains.get(domain_key)

    def load(self, domain_key: str) -> Any | None:
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
        builtins = {f: getattr(mod, f, None) for f in meta.functions if hasattr(mod, f)}
        # Try calling _register_* functions for Chinese-named builtins
        if mod and hasattr(mod, '_register_graphics'):
            reg = {}
            mod._register_graphics(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_display'):
            reg = {}
            mod._register_display(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_recorder'):
            reg = {}
            mod._register_recorder(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_player'):
            reg = {}
            mod._register_player(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_game'):
            reg = {}
            mod._register_game(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_office'):
            reg = {}
            mod._register_office(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_os'):
            reg = {}
            mod._register_os(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_networking'):
            reg = {}
            mod._register_networking(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_io'):
            reg = {}
            mod._register_io(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_time'):
            reg = {}
            mod._register_time(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_web'):
            reg = {}
            mod._register_web(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_database'):
            reg = {}
            mod._register_database(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_security'):
            reg = {}
            mod._register_security(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_nn'):
            reg = {}
            mod._register_nn(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_concurrent'):
            reg = {}
            mod._register_concurrent(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_data_science'):
            reg = {}
            mod._register_data_science(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_blockchain'):
            reg = {}
            mod._register_blockchain(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_quantum'):
            reg = {}
            mod._register_quantum(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_av'):
            reg = {}
            mod._register_av(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_geo'):
            reg = {}
            mod._register_geo(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_chemistry'):
            reg = {}
            mod._register_chemistry(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_astro'):
            reg = {}
            mod._register_astro(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_music'):
            reg = {}
            mod._register_music(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_robot'):
            reg = {}
            mod._register_robot(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_av'):
            reg = {}
            mod._register_av(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_package'):
            reg = {}
            mod._register_package(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_type_checker'):
            reg = {}
            mod._register_type_checker(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_test_framework'):
            reg = {}
            mod._register_test_framework(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_formatter'):
            reg = {}
            mod._register_formatter(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_doc_generator'):
            reg = {}
            mod._register_doc_generator(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_async'):
            reg = {}
            mod._register_async(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_science'):
            reg = {}
            mod._register_science(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_visualization'):
            reg = {}
            mod._register_visualization(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_symbolic'):
            reg = {}
            mod._register_symbolic(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_ml'):
            reg = {}
            mod._register_ml(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_security_enhanced'):
            reg = {}
            mod._register_security_enhanced(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_http_server'):
            reg = {}
            mod._register_http_server(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_git'):
            reg = {}
            mod._register_git(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_build_system'):
            reg = {}
            mod._register_build_system(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_database'):
            reg = {}
            mod._register_database(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_ai_framework'):
            reg = {}
            mod._register_ai_framework(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_compiler_backend'):
            reg = {}
            mod._register_compiler_backend(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_game_engine'):
            reg = {}
            mod._register_game_engine(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_security_complete'):
            reg = {}
            mod._register_security_complete(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_ui_framework'):
            reg = {}
            mod._register_ui_framework(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_devops'):
            reg = {}
            mod._register_devops(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_blockchain'):
            reg = {}
            mod._register_blockchain(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_audio_video'):
            reg = {}
            mod._register_audio_video(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_geospatial'):
            reg = {}
            mod._register_geospatial(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_robotics'):
            reg = {}
            mod._register_robotics(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_symbolic'):
            reg = {}
            mod._register_symbolic(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_os_module'):
            reg = {}
            mod._register_os_module(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_compiler_full'):
            reg = {}
            mod._register_compiler_full(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_web_framework'):
            reg = {}
            mod._register_web_framework(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_frontend'):
            reg = {}
            mod._register_frontend(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_science_full'):
            reg = {}
            mod._register_science_full(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_ml_full'):
            reg = {}
            mod._register_ml_full(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_quantum'):
            reg = {}
            mod._register_quantum(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_toolchain'):
            reg = {}
            mod._register_toolchain(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_graphics'):
            reg = {}
            mod._register_graphics(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_general'):
            reg = {}
            mod._register_general(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_os_extended'):
            reg = {}
            mod._register_os_extended(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_sql_engine'):
            reg = {}
            mod._register_sql_engine(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_os_kernel'):
            reg = {}
            mod._register_os_kernel(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_hal'):
            reg = {}
            mod._register_hal(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_storage_engine'):
            reg = {}
            mod._register_storage_engine(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_runtime'):
            reg = {}
            mod._register_runtime(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_network_driver'):
            reg = {}
            mod._register_network_driver(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_fs_driver'):
            reg = {}
            mod._register_fs_driver(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_device_driver'):
            reg = {}
            mod._register_device_driver(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_os_api'):
            reg = {}
            mod._register_os_api(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_graphics_driver'):
            reg = {}
            mod._register_graphics_driver(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_crypto_foundation'):
            reg = {}
            mod._register_crypto_foundation(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_math_foundation'):
            reg = {}
            mod._register_math_foundation(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_browser'):
            reg = {}
            mod._register_browser(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_mobile'):
            reg = {}
            mod._register_mobile(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_computational_law'):
            reg = {}
            mod._register_computational_law(reg)
            builtins.update(reg)
        if mod and hasattr(mod, '_register_geek_gray'):
            reg = {}
            mod._register_geek_gray(reg)
            builtins.update(reg)
        if mod and not builtins:
            reg = {}
            if self._dispatch_register(domain_key, mod, reg):
                builtins.update(reg)
        return builtins

    @staticmethod
    def _normalize_name(name: str) -> str:
        return "".join(ch for ch in name.lower() if ch.isalnum())

    def _dispatch_register(self, domain_key: str, mod: Any,
                           reg: dict) -> bool:
        """回退分发：按领域键匹配模块内的 _register_* 钩子。"""
        hooks = [a for a in dir(mod)
                 if a.startswith("_register_")
                 and callable(getattr(mod, a, None))]
        if not hooks:
            return False
        want = self._normalize_name(domain_key)
        exact = [a for a in hooks
                 if self._normalize_name(a[len("_register_"):]) == want]
        chosen = exact or (hooks if len(hooks) == 1 else [])
        for name in chosen:
            try:
                getattr(mod, name)(reg)
            except Exception:
                continue
            if reg:
                return True
        return False

    def list_domains(self, category: str | None = None) -> list[dict]:
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

_registry: DomainRegistry | None = None


def get_registry() -> DomainRegistry:
    """获取全局领域注册表。"""
    global _registry
    if _registry is None:
        _registry = DomainRegistry()
        # 注册所有预定义领域
        for key in DomainRegistry._DOMAIN_TEMPLATES:
            _registry.register(key)
    return _registry


def domain_compile(source: str, target: str, domain: str | None = None) -> str:
    """使用指定领域编译源码。"""
    registry = get_registry()
    if domain and domain in registry._domains:
        # 加载领域内置函数
        registry.get_builtins(domain)
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
