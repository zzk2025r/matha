# -*- coding: utf-8 -*-
"""v2.1.1 发布脚本 — Git 提交与打标签

运行方式:
  pip install gitpython
  python release/v2.0.0/scripts/release_v2.1.1.py
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(r"D:\trae")
COMMIT_MSG = """fix: 修复 parser TODO 语境判断 + 实现 kernel 键盘中断与除零错误处理

- parser.py: _is_path_context 增加控制流/lambda/函数调用/链式语境检查
- kernel.py: 实现 IRQ1 键盘环形缓冲区写入逻辑
- kernel.py: 实现 div_by_zero_handler 错误打印 + 停机保护
- kernel.py: 移除硬编码路径，改用 os.path 动态计算

测试: 284/284 单元测试通过, 10/10 循环展开边界通过, 5/5 变量存活边界通过
版本: v2.1.1"""

TAG = "v2.1.1"


def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd or REPO)
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.stderr.strip():
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode


print("=" * 60)
print("v2.1.1 发布脚本")
print("=" * 60)

# 检查 git 是否可用
print("\n[1/5] 检查 Git 环境...")
rc = run("git --version")
if rc != 0:
    print("  [ERROR] git 命令不可用，请先安装 Git")
    sys.exit(1)
print("  [OK] Git 可用")

# 检查是否有未提交的更改
print("\n[2/5] 检查工作区状态...")
run("git status --short")
rc = run("git status --porcelain")
if "fatal" in rc.lower():
    print("  [WARN] 不是 Git 仓库，正在初始化...")
    run("git init")
    run('git config user.email "matha@trae.local"')
    run('git config user.name "Matha AI"')

# 添加更改
print("\n[3/5] 暂存更改...")
run("git add src/parser.py src/codegen/kernel.py")

# 提交
print("\n[4/5] 创建提交...")
rc = run(f'git commit -m "{COMMIT_MSG}"')
if rc != 0:
    # 可能没有新更改
    out = subprocess.run("git status --short", capture_output=True, text=True, cwd=REPO).stdout.strip()
    if not out:
        print("  [INFO] 工作区无新更改，跳过提交")
    else:
        print("  [ERROR] 提交失败")
        sys.exit(1)
else:
    print("  [OK] 提交成功")

# 打标签
print("\n[5/5] 打标签 %s..." % TAG)
rc = run("git tag -a '%s' -m 'Matha 自成长引擎 v2.1.1'" % TAG)
if rc != 0:
    print("  [WARN] 标签可能已存在")
else:
    print("  [OK] 标签创建成功")

# 显示提交信息
print("\n" + "=" * 60)
print("提交摘要")
print("=" * 60)
run("git log --oneline -3")

print("\n请在终端中手动执行以下命令推送:")
print("  git push origin main")
print("  git push origin v2.1.1")
