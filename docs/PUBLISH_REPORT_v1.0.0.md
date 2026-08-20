# matha-auth 发布验证报告

> 版本: v1.0.0 | 生成时间: 2026-08-20

---

## 1. 发布脚本模拟（dry-run）

```
============================================================
  matha-auth 发布工具
============================================================

  当前版本: 1.0.0
  升级级别: patch
  新版本  : 1.0.1

  [dry-run] 以下操作将被执行：
    1. 更新版本号 → 1.0.1
    2. git commit + tag v1.0.1
    3. git push
    4. pip install build twine
    5. python setup.py sdist bdist_wheel
    6. twine upload
============================================================
  ✓ 发布模拟完成（无实际执行）
```

---

## 2. 实际构建日志

### 2.1 构建命令
```bash
cd packages && python setup.py sdist bdist_wheel
```

### 2.2 构建输出摘要
```
running sdist
running egg_info
creating matha_auth.egg-info
writing matha_auth.egg-info\PKG-INFO
writing dependency_links to matha_auth.egg-info\dependency_links.txt
writing requirements to matha_auth.egg-info\requires.txt
writing top-level names to matha_auth.egg-info\top_level.txt
writing manifest file 'matha_auth.egg-info\SOURCES.txt'

copying files to matha_auth-1.0.0...
copying pyproject.toml -> matha_auth-1.0.0
copying setup.py -> matha_auth-1.0.0
copying .\matha_auth\__init__.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\_version.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\api.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\exceptions.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\jwt.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\models.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\password.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\rbac.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\server.py -> matha_auth-1.0.0\.\matha_auth
copying .\matha_auth\service.py -> matha_auth-1.0.0\.\matha_auth
copying tests\test_concurrent.py -> matha_auth-1.0.0\tests
copying tests\test_integration.py -> matha_auth-1.0.0\tests
copying tests\test_permission_api.py -> matha_auth-1.0.0\tests
copying tests\test_rbac_middleware.py -> matha_auth-1.0.0\tests
copying tests\test_session_manager.py -> matha_auth-1.0.0\tests
Writing matha_auth-1.0.0\setup.cfg
creating dist
Creating tar archive
removing 'matha_auth-1.0.0' (and everything under it)

running bdist_wheel
running build
running build_py
creating build\bdist.win-amd64\wheel\matha_auth
...
creating 'dist\matha_auth-1.0.0-py3-none-any.whl'
adding 'matha_auth/__init__.py'
adding 'matha_auth/_version.py'
adding 'matha_auth/api.py'
adding 'matha_auth/exceptions.py'
adding 'matha_auth/jwt.py'
adding 'matha_auth/models.py'
adding 'matha_auth/password.py'
adding 'matha_auth/rbac.py'
adding 'matha_auth/server.py'
adding 'matha_auth/service.py'
adding 'matha_auth-1.0.0.dist-info/METADATA'
adding 'matha_auth-1.0.0.dist-info/WHEEL'
adding 'matha_auth-1.0.0.dist-info/top_level.txt'
adding 'matha_auth-1.0.0.dist-info/RECORD'
```

### 2.3 构建产物
| 文件 | 类型 | 大小估算 |
|---|---|---|
| `dist/matha_auth-1.0.0.tar.gz` | sdist | ~20KB |
| `dist/matha_auth-1.0.0-py3-none-any.whl` | wheel | ~15KB |

### 2.4 构建警告（需修复）
| 警告 | 影响 | 修复建议 |
|---|---|---|
| `scripts` defined outside of `pyproject.toml` | 低 | 在 pyproject.toml 中添加 `[project.scripts]` |
| `README.md` cannot be found | 中 | 在 packages/ 根目录创建 README.md |
| `project.license` as TOML table deprecated | 低 | 改用 SPDX 字符串 `license = "MIT"` |
| `extras_require` overwritten in pyproject.toml | 低 | 保留 `[project.optional-dependencies]` |

---

## 3. 构建产物验证

```bash
# 查看构建产物
ls -la dist/

# 验证 wheel 内容
python -m zipfile -l dist/matha_auth-1.0.0-py3-none-any.whl

# 验证 sdist 内容
tar -tzf dist/matha_auth-1.0.0.tar.gz | head -30
```

---

## 4. 发布命令

### 4.1 发布到私有 PyPI
```bash
cd packages
pip install build twine
python -m build
twine upload dist/* \
  --repository-url https://pypi.your-company.com/simple/ \
  --skip-existing
```

### 4.2 使用发布脚本
```bash
# patch 升级 (1.0.0 → 1.0.1)
python publish.py

# minor 升级 (1.0.0 → 1.1.0)
python publish.py minor

# major 升级 (1.0.0 → 2.0.0)
python publish.py major

# 仅打印计划（不执行）
python publish.py --dry-run
```

### 4.3 环境变量
```bash
export PYPI_TOKEN="your-private-pypi-token"
export PYPI_URL="https://pypi.your-company.com/simple/"
```

---

## 5. 测试验证

```
Python auth tests:     132/132 OK
matha-auth 包测试:     108/108 OK
集成测试:              123/123 OK
──────────────────────────
总计:                  363/363 全部通过
```

---

## 6. 发布后验证步骤

```bash
# 1. 安装测试
pip install matha-auth==1.0.0

# 2. 验证导入
python -c "from matha_auth import SessionManager, RBACMiddleware; print('OK')"

# 3. 验证 CLI
matha-auth --help

# 4. 运行测试套件
python -m unittest packages.tests.test_session_manager \
                   packages.tests.test_rbac_middleware \
                   packages.tests.test_permission_api \
                   packages.tests.test_concurrent \
                   packages.tests.test_integration -v
```

---

## 7. 下一步

| 任务 | 状态 |
|---|---|
| 修复 README.md 缺失警告 | ⏳ 待处理 |
| 修复 scripts 配置警告 | ⏳ 待处理 |
| 修复 license 格式警告 | ⏳ 待处理 |
| 实际发布到私有 PyPI | ⏳ 待执行 |
| 生成 CHANGELOG | ⏳ 待处理 |
