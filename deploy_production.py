# -*- coding: utf-8 -*-
"""Matha v4.4 生产环境部署配置脚本

本脚本提供完整的部署配置，包括：
  1. 依赖安装（核心依赖 + 可选依赖）
  2. 环境变量设置
  3. 性能配置优化
  4. 日志配置
  5. 健康检查

用法：
  # 安装所有依赖
  python deploy_production.py --install all

  # 安装核心依赖
  python deploy_production.py --install core

  # 安装可选依赖（NumPy, SymPy 等）
  python deploy_production.py --install optional

  # 设置环境变量
  python deploy_production.py --setup-env

  # 运行健康检查
  python deploy_production.py --health-check

  # 完整部署流程
  python deploy_production.py --full-setup
"""
import sys
import os
import subprocess
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
PYTHON_VERSION = sys.version_info


class DeployConfig:
    """部署配置类。"""

    # 核心依赖（必须安装）
    CORE_REQUIREMENTS = [
        'sympy>=1.14.0',
    ]

    # 可选依赖（推荐安装）
    OPTIONAL_REQUIREMENTS = [
        'numpy>=1.24.0',      # 高性能矩阵运算
        'scipy>=1.10.0',      # 科学计算
        'numba>=0.57.0',      # JIT 编译优化
    ]

    # 开发依赖
    DEV_REQUIREMENTS = [
        'pytest>=7.0.0',
        'pytest-cov>=4.0.0',
        'black>=23.0.0',
        'flake8>=6.0.0',
    ]

    # 环境变量模板
    ENVIRONMENT_VARS = {
        # 应用配置
        'MATHA_ENV': 'production',
        'MATHA_LOG_LEVEL': 'INFO',
        'MATHA_CACHE_SIZE': '1000',
        'MATHA_MAX_WORKERS': '4',
        'MATHA_SPARSE_THRESHOLD': '0.9',

        # 性能优化
        'MATHA_NUMPY_AVAILABLE': 'true',
        'MATHA_SYMPY_AVAILABLE': 'true',
        'MATHA_SVD_USE_NUMPY': 'true',
        'MATHA_SVD_MAX_ITER': '100',

        # 并行计算
        'MATHA_PARALLEL_ENABLED': 'true',
        'MATHA_THREAD_POOL_SIZE': '4',

        # 日志配置
        'MATHA_LOG_FORMAT': 'json',
        'MATHA_LOG_FILE': 'logs/matha.log',
        'MATHA_LOG_MAX_SIZE': '10MB',
        'MATHA_LOG_BACKUP_COUNT': '5',
    }

    # 性能配置
    PERFORMANCE_CONFIG = {
        'cache_max_size': 1000,
        'sparse_threshold': 0.9,
        'svd_max_iter': 100,
        'parallel_workers': 4,
        'benchmark_iterations': 10,
        'benchmark_warmup': 3,
    }


def check_python_version() -> bool:
    """检查 Python 版本。"""
    logger.info(f"检查 Python 版本: {PYTHON_VERSION.major}.{PYTHON_VERSION.minor}.{PYTHON_VERSION.micro}")
    if PYTHON_VERSION.major < 3 or (PYTHON_VERSION.major == 3 and PYTHON_VERSION.minor < 8):
        logger.error("需要 Python 3.8 或更高版本")
        return False
    logger.info("Python 版本检查通过")
    return True


def install_dependencies(requirements: List[str], verbose: bool = False) -> bool:
    """安装依赖。"""
    logger.info(f"开始安装 {len(requirements)} 个依赖...")

    for req in requirements:
        pkg = req.split('>=')[0].split('==')[0]
        logger.info(f"安装: {req}")

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', req, '-q'],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"安装失败: {req}")
                logger.error(f"错误: {result.stderr[:500]}")
                return False
            else:
                logger.info(f"安装成功: {req}")

        except subprocess.TimeoutExpired:
            logger.error(f"安装超时: {req}")
            return False
        except Exception as e:
            logger.error(f"安装异常: {req}, 错误: {e}")
            return False

    logger.info("所有依赖安装完成")
    return True


def verify_installation() -> Dict[str, bool]:
    """验证安装状态。"""
    results = {
        'python': True,
        'sympy': False,
        'numpy': False,
        'scipy': False,
        'numba': False,
    }

    # 检查 Python
    results['python'] = check_python_version()

    # 检查 SymPy
    try:
        import sympy
        results['sympy'] = True
        logger.info(f"SymPy 已安装: {sympy.__version__}")
    except ImportError:
        logger.warning("SymPy 未安装")

    # 检查 NumPy
    try:
        import numpy
        results['numpy'] = True
        logger.info(f"NumPy 已安装: {numpy.__version__}")
    except ImportError:
        logger.warning("NumPy 未安装（可选依赖）")

    # 检查 SciPy
    try:
        import scipy
        results['scipy'] = True
        logger.info(f"SciPy 已安装: {scipy.__version__}")
    except ImportError:
        logger.warning("SciPy 未安装（可选依赖）")

    # 检查 Numba
    try:
        import numba
        results['numba'] = True
        logger.info(f"Numba 已安装: {numba.__version__}")
    except ImportError:
        logger.warning("Numba 未安装（可选依赖）")

    return results


def setup_environment_variables() -> bool:
    """设置环境变量。"""
    logger.info("设置环境变量...")

    success = True
    for key, value in DeployConfig.ENVIRONMENT_VARS.items():
        try:
            os.environ[key] = value
            logger.debug(f"设置环境变量: {key}={value}")
        except Exception as e:
            logger.error(f"设置环境变量失败: {key}, 错误: {e}")
            success = False

    # 写入 .env 文件
    env_file = PROJECT_ROOT / '.env'
    with open(env_file, 'w', encoding='utf-8') as f:
        for key, value in DeployConfig.ENVIRONMENT_VARS.items():
            f.write(f"{key}={value}\n")

    logger.info(f"环境变量已写入: {env_file}")
    logger.info("环境变量设置完成")
    return success


def create_directories() -> bool:
    """创建必要目录。"""
    directories = [
        PROJECT_ROOT / 'logs',
        PROJECT_ROOT / 'data',
        PROJECT_ROOT / 'cache',
        PROJECT_ROOT / 'tests' / 'output',
    ]

    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"创建目录: {dir_path}")

    logger.info("目录创建完成")
    return True


def generate_config_file() -> Path:
    """生成配置文件。"""
    config = {
        'version': '4.4.0',
        'environment': 'production',
        'performance': DeployConfig.PERFORMANCE_CONFIG,
        'dependencies': {
            'core': DeployConfig.CORE_REQUIREMENTS,
            'optional': DeployConfig.OPTIONAL_REQUIREMENTS,
            'dev': DeployConfig.DEV_REQUIREMENTS,
        },
        'environment_variables': DeployConfig.ENVIRONMENT_VARS,
    }

    config_path = PROJECT_ROOT / 'config' / 'production.json'
    config_path.parent.mkdir(parents=True, exist_ok=True)

    import json
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    logger.info(f"配置文件已生成: {config_path}")
    return config_path


def run_health_check() -> bool:
    """运行健康检查。"""
    logger.info("运行健康检查...")

    checks = {
        'python_version': check_python_version(),
        'sympy_installed': False,
        'numpy_installed': False,
        'environment_variables': False,
        'directories': False,
    }

    # 检查 SymPy
    try:
        import sympy
        checks['sympy_installed'] = True
        logger.info(f"  ✓ SymPy: {sympy.__version__}")
    except ImportError:
        logger.warning("  ✗ SymPy 未安装")

    # 检查 NumPy
    try:
        import numpy
        checks['numpy_installed'] = True
        logger.info(f"  ✓ NumPy: {numpy.__version__}")
    except ImportError:
        logger.warning("  ✗ NumPy 未安装（可选）")

    # 检查环境变量
    all_env_set = all(key in os.environ for key in DeployConfig.ENVIRONMENT_VARS.keys())
    checks['environment_variables'] = all_env_set
    logger.info(f"  {'✓' if all_env_set else '✗'} 环境变量: {'全部设置' if all_env_set else '部分缺失'}")

    # 检查目录
    directories_exist = all(d.exists() for d in [
        PROJECT_ROOT / 'logs',
        PROJECT_ROOT / 'data',
        PROJECT_ROOT / 'cache',
    ])
    checks['directories'] = directories_exist
    logger.info(f"  {'✓' if directories_exist else '✗'} 目录: {'存在' if directories_exist else '部分缺失'}")

    # 运行基本功能测试
    try:
        from src.stdlib.linear_algebra import Matrix, matrix_multiply
        A = Matrix([[1, 2], [3, 4]])
        B = Matrix([[5, 6], [7, 8]])
        C = matrix_multiply(A, B)
        logger.info(f"  ✓ 矩阵乘法测试通过: C = {C}")
    except Exception as e:
        logger.error(f"  ✗ 矩阵乘法测试失败: {e}")
        checks['basic_functionality'] = False

    # 总结
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    logger.info(f"健康检查结果: {passed}/{total} 通过")

    if passed == total:
        logger.info("✓ 健康检查通过")
        return True
    else:
        logger.warning("✗ 健康检查部分失败，请检查上述输出")
        return False


def generate_deployment_report(results: Dict) -> str:
    """生成部署报告。"""
    report = []
    report.append("=" * 60)
    report.append("  Matha v4.4 生产环境部署报告")
    report.append("=" * 60)
    report.append("")

    report.append("## 环境信息")
    report.append(f"- Python 版本: {PYTHON_VERSION.major}.{PYTHON_VERSION.minor}.{PYTHON_VERSION.micro}")
    report.append(f"- 项目根目录: {PROJECT_ROOT}")
    report.append("")

    report.append("## 依赖安装状态")
    for dep, installed in results.items():
        status = "✓ 已安装" if installed else "✗ 未安装"
        report.append(f"- {dep}: {status}")
    report.append("")

    report.append("## 性能配置")
    for key, value in DeployConfig.PERFORMANCE_CONFIG.items():
        report.append(f"- {key}: {value}")
    report.append("")

    report.append("## 环境变量")
    for key, value in DeployConfig.ENVIRONMENT_VARS.items():
        report.append(f"- {key}={value}")
    report.append("")

    report.append("=" * 60)
    report.append("  部署完成时间: {}".format(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    report.append("=" * 60)

    return "\n".join(report)


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description="Matha v4.4 生产环境部署配置脚本")
    parser.add_argument('--install', choices=['core', 'optional', 'all'], default='all',
                       help='安装依赖类型（默认: all）')
    parser.add_argument('--setup-env', action='store_true', help='设置环境变量')
    parser.add_argument('--health-check', action='store_true', help='运行健康检查')
    parser.add_argument('--full-setup', action='store_true', help='完整部署流程')
    parser.add_argument('--report', action='store_true', help='生成部署报告')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    logger.info("开始 Matha v4.4 生产环境部署...")

    results = {'python': True, 'sympy': False, 'numpy': False, 'scipy': False, 'numba': False}

    # 完整部署流程
    if args.full_setup:
        logger.info("执行完整部署流程...")

        # 1. 安装依赖
        logger.info("步骤 1: 安装依赖")
        if args.install == 'all' or args.install == 'core':
            install_dependencies(DeployConfig.CORE_REQUIREMENTS)
        if args.install == 'all' or args.install == 'optional':
            install_dependencies(DeployConfig.OPTIONAL_REQUIREMENTS)

        # 2. 验证安装
        logger.info("步骤 2: 验证安装")
        results = verify_installation()

        # 3. 创建目录
        logger.info("步骤 3: 创建目录")
        create_directories()

        # 4. 设置环境变量
        logger.info("步骤 4: 设置环境变量")
        setup_environment_variables()

        # 5. 生成配置文件
        logger.info("步骤 5: 生成配置文件")
        generate_config_file()

        # 6. 健康检查
        logger.info("步骤 6: 健康检查")
        run_health_check()

    # 单独运行各步骤
    else:
        if args.install:
            logger.info(f"安装依赖: {args.install}")
            if args.install == 'core':
                install_dependencies(DeployConfig.CORE_REQUIREMENTS)
            elif args.install == 'optional':
                install_dependencies(DeployConfig.OPTIONAL_REQUIREMENTS)
            elif args.install == 'all':
                install_dependencies(DeployConfig.CORE_REQUIREMENTS)
                install_dependencies(DeployConfig.OPTIONAL_REQUIREMENTS)

        if args.setup_env:
            logger.info("设置环境变量")
            setup_environment_variables()

        if args.health_check:
            logger.info("运行健康检查")
            run_health_check()

    # 生成报告
    if args.report or args.full_setup:
        report = generate_deployment_report(results)
        print("\n" + report)

        # 保存报告
        report_path = PROJECT_ROOT / 'docs' / 'DEPLOYMENT_REPORT.md'
        report_path.write_text(report, encoding='utf-8')
        logger.info(f"部署报告已保存: {report_path}")

    logger.info("部署完成")


if __name__ == "__main__":
    main()
