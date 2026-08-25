# -*- coding: utf-8 -*-
"""matha-pkg 依赖解析逻辑检查

检查项：
1. 循环依赖检测
2. 依赖解析正确性
3. 版本约束冲突检测
4. 优化建议
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pkg_manager import MathaPackage, DependencyResolver, PackageMeta, Version


def check_circular_dependencies(pkg_manager: MathaPackage):
    """检测循环依赖。"""
    print("\n" + "=" * 60)
    print("  循环依赖检测")
    print("=" * 60)

    resolver = DependencyResolver()
    circular_deps = []

    for pkg_name, pkg in pkg_manager.registry.items():
        visited = set()
        stack = [(pkg_name, [pkg_name])]

        while stack:
            current, path = stack.pop()

            if current in visited:
                continue
            visited.add(current)

            if current in pkg_manager.registry:
                current_pkg = pkg_manager.registry[current]
                for dep in current_pkg.dependencies:
                    if dep in path:
                        circular_deps.append(path + [dep])
                    else:
                        stack.append((dep, path + [dep]))

    if circular_deps:
        print("  ❌ 发现循环依赖:")
        for cycle in circular_deps:
            print(f"    {' -> '.join(cycle)}")
    else:
        print("  ✅ 未发现循环依赖")

    return len(circular_deps) == 0


def check_dependency_resolution(pkg_manager: MathaPackage):
    """检查依赖解析正确性。"""
    print("\n" + "=" * 60)
    print("  依赖解析测试")
    print("=" * 60)

    resolver = DependencyResolver()
    errors = []

    # 测试各包的依赖解析
    for pkg_name in ['arithmetic', 'algebra', 'calculus', 'logic', 'intent', 'compiler']:
        if pkg_name not in pkg_manager.registry:
            continue

        pkg = pkg_manager.registry[pkg_name]
        try:
            deps = resolver.resolve(pkg, pkg_manager.registry)
            print(f"  ✅ {pkg_name}: {len(deps)} 个依赖")
        except Exception as e:
            errors.append(f"  ❌ {pkg_name}: {e}")
            print(f"  ❌ {pkg_name}: {e}")

    return len(errors) == 0


def check_version_constraints(pkg_manager: MathaPackage):
    """检查版本约束。"""
    print("\n" + "=" * 60)
    print("  版本约束测试")
    print("=" * 60)

    resolver = DependencyResolver()

    # 测试版本约束
    test_cases = [
        (Version(1, 2, 3), '==1.2.3', True),
        (Version(1, 2, 3), '!=1.2.4', True),
        (Version(1, 2, 3), '>=1.2.0', True),
        (Version(1, 2, 3), '<=1.3.0', True),
        (Version(1, 2, 3), '>1.0.0', True),
        (Version(1, 2, 3), '<2.0.0', True),
        (Version(1, 2, 3), '~=1.2', True),
        (Version(1, 2, 3), '^1.2.0', True),
        (Version(1, 2, 3), '>=2.0.0', False),
        (Version(2, 0, 0), '<1.5.0', False),
    ]

    all_passed = True
    for version, constraint, expected in test_cases:
        result = resolver.check_constraint(version, constraint)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_passed = False
        print(f"  {status} {version} {constraint} = {result} (期望 {expected})")

    return all_passed


def generate_optimization_suggestions(pkg_manager: MathaPackage):
    """生成优化建议。"""
    print("\n" + "=" * 60)
    print("  优化建议")
    print("=" * 60)

    suggestions = []

    # 1. 依赖缓存
    suggestions.append({
        'item': '依赖缓存',
        'severity': 'P1',
        'description': '当前每次安装都重新解析依赖树，建议缓存解析结果。',
        'suggestion': '添加 DependencyCache 类，缓存已解析的依赖树。'
    })

    # 2. 并行解析
    suggestions.append({
        'item': '并行依赖解析',
        'severity': 'P2',
        'description': '当前依赖解析是串行的，对于大型项目较慢。',
        'suggestion': '使用 ThreadPoolExecutor 并行解析独立子树。'
    })

    # 3. 依赖冲突优化
    suggestions.append({
        'item': '依赖冲突解决',
        'severity': 'P1',
        'description': '当前遇到版本冲突时直接抛出异常，无自动解决策略。',
        'suggestion': '实现版本兼容分析，自动选择满足所有约束的版本。'
    })

    # 4. 离线模式
    suggestions.append({
        'item': '离线安装模式',
        'severity': 'P2',
        'description': '当前需要联网获取包信息。',
        'suggestion': '支持从本地缓存安装，适合离线环境。'
    })

    # 5. 锁定文件
    suggestions.append({
        'item': 'lock 文件支持',
        'severity': 'P1',
        'description': '缺少 lock 文件，导致不同环境的依赖版本不一致。',
        'suggestion': '添加 matha.lock 文件，锁定所有依赖的精确版本。'
    })

    for i, s in enumerate(suggestions, 1):
        print(f"\n  [{s['severity']}] {s['item']}")
        print(f"    问题: {s['description']}")
        print(f"    建议: {s['suggestion']}")

    return suggestions


def main():
    """主入口。"""
    print("\n" + "=" * 60)
    print("  matha-pkg 依赖解析逻辑检查")
    print("=" * 60)

    pkg_manager = MathaPackage()

    # 运行检查
    results = {
        'circular_deps': check_circular_dependencies(pkg_manager),
        'dependency_resolution': check_dependency_resolution(pkg_manager),
        'version_constraints': check_version_constraints(pkg_manager),
    }

    # 生成建议
    suggestions = generate_optimization_suggestions(pkg_manager)

    # 总结
    print("\n" + "=" * 60)
    print("  检查总结")
    print("=" * 60)

    all_passed = all(results.values())
    for check, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")

    if all_passed:
        print("\n  ✅ 所有检查通过!")
    else:
        print("\n  ⚠️  存在需要修复的问题")

    print(f"\n  优化建议: {len(suggestions)} 条")
    print("=" * 60)


if __name__ == "__main__":
    main()
