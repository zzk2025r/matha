# Matha 社区指南

## 社区愿景

Matha 社区致力于构建一个自举式、领域专用、可独立运行的编程语言系统。我们相信，当虚拟代码引擎足够强大时，任何自然语言都可以直接当代码使用。

## 社区规模

- **GitHub Stars**: 持续增长
- **贡献者**: 欢迎所有开发者
- **文档**: 完整的 API 文档、教程、示例
- **测试**: 21+ 套测试套件，100% 通过率

## 如何参与

### 1. 报告问题

使用 GitHub Issues 报告 Bug 或请求功能：
- 描述问题现象
- 提供复现步骤
- 附带 Matha 版本信息

### 2. 提交代码

```bash
# Fork 仓库
git clone https://github.com/zzk2025r/matha.git
cd matha

# 创建分支
git checkout -b feature/my-feature

# 提交更改
git add .
git commit -m "feat: 添加新功能"

# 推送并创建 PR
git push origin feature/my-feature
```

### 3. 贡献领域模块

每个领域模块放在 `src/domains/` 目录下：
- 包含完整的类定义
- 包含 `_register_*` 函数
- 包含测试用例
- 在 `registry.py` 中注册

### 4. 文档改进

- 修复错别字
- 添加代码示例
- 翻译文档
- 更新 API 文档

## 社区规范

### 代码风格

- 使用 Python 3.10+ 语法
- 遵循 PEP 8
- 所有新代码必须有类型注解
- 中文标识符命名规范

### 提交规范

- 使用 Conventional Commits 格式
- 提交信息清晰描述变更
- 每个 PR 只解决一个问题

### 行为准则

- 尊重所有社区成员
- 禁止骚扰、歧视
- 建设性讨论
- 友好互助

## 社区资源

| 资源 | 链接 |
|------|------|
| GitHub | https://github.com/zzk2025r/matha |
| Issues | https://github.com/zzk2025r/matha/issues |
| Wiki | https://github.com/zzk2025r/matha/wiki |
| 对比分析 | MATHA_COMPARISON.md |

## 社区活动

- **月度发布** - 每月发布新版本
- **Hackathon** - 季度编程马拉松
- **文档冲刺** - 定期文档改进活动
- **领域模块挑战** - 添加新领域模块

## 贡献者榜单

| 贡献者 | 贡献 |
|--------|------|
| zzkk2025r | 创始人、核心开发 |
| 社区贡献者 | 领域模块、测试、文档 |

## 致谢

感谢所有为 Matha 做出贡献的人！

---

*Matha v4.5 | 社区指南 | 2026*