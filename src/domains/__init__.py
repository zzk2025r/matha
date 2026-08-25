# -*- coding: utf-8 -*-
"""
Matha 领域模块包：所有学科/专业/应用领域。

领域分类：
  - science: 科学计算（AI、数据科学、HPC、化学、物理、生物、混沌）
  - engineering: 工程开发（软件、自动化、IoT、OS、网络安全）
  - creative: 创意领域（游戏、图形、音视频、创意编程）
  - frontier: 前沿领域（区块链、量子、自动驾驶、元宇宙、法律、GA）
  - general: 通用领域

注意：各子模块使用自己的命名规范（部分使用中文前缀），
直接 import 各子模块即可，不要在此 __init__ 中做大量导入。
"""
from __future__ import annotations

# 核心功能通过 sub-module import 访问：
#   from src.domains import ai_data_science, blockchain, chaos_fractal, ...

__all__ = [
    # AI/数据科学
    "ai_data_science",
    # 软件/应用开发
    "software_app",
    # 游戏开发
    "game_dev",
    # 区块链/Web3
    "blockchain",
    # 量子计算
    "quantum_compute",
    # 混沌/分型
    "chaos_fractal",
    # 遗传算法
    "genetic_algo",
    # 创意编程
    "creative_coding",
    # 领域注册中心
    "registry",
    # 现有领域
    "computer_science",
    "biology",
    "quantum",
    "real_hardware",
    "kernel",
    "kernel_math",
    "mechanics",
    "thermo",
    "fluid",
    "structural",
    "electrical",
    "embedded",
    "medical",
    "chemistry",
    "economics",
    "architecture",
    "acoustics",
    "anatomy",
    "building_struct",
    "celestial",
    "dynamics",
    "em",
    "extended_modeling",
    "fluid_exp",
    "mech_design",
    "medtools",
    "nuclear",
    "optics",
    "statmech",
]
