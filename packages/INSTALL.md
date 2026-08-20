# matha-auth 安装指南

## 从 PyPI 私有仓库安装

### 配置私有仓库

```bash
# 设置 PyPI 仓库地址（替换为你的仓库 URL）
pip config set global.index-url https://pypi.your-company.com/simple/

# 如果需要使用认证
pip config set global.username your-username
pip config set global.password your-password
```

### 安装

```bash
# 安装最新版本
pip install matha-auth

# 安装指定版本
pip install matha-auth==1.0.0

# 安装开发依赖
pip install matha-auth[dev]
```

## 从源码安装

```bash
cd packages
pip install -e .
```

## 验证安装

```python
from matha_auth import SessionManager, RBACMiddleware, PermissionChangeAPI

mgr = SessionManager()
user = mgr.register("alice", "alice@example.com", "AlicePass1")
session = mgr.login("alice", "AlicePass1")
print(f"Token: {session.token[:50]}...")

rbac = RBACMiddleware()
print(f"Admin has doc:write: {rbac.has_permission(['admin'], 'doc:write')}")
```

## CLI 工具

```bash
# 生成密码哈希
matha-auth hash-password MySecurePass1

# 验证密码
matha-auth verify-password MySecurePass1 <hash>

# 签发 JWT
matha-auth jwt-encode alice --roles '["admin"]'

# 解码 JWT
matha-auth jwt-decode <token>
```

## 运行测试

```bash
cd packages
python -m unittest discover -s tests -v
```
