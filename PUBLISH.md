# Matha v4.3 发布脚本

> 一键发布 Matha v4.3 到 GitHub

---

## 快速开始

```bash
# 1. 安装环境工具
python install_tools.py

# 2. 检查环境
python check_git.py
python check_files.py

# 3. 安装依赖（如需要）
python install_dependencies.py --all

# 4. 预览发布流程
python publish_oneclick.py --dry-run

# 5. 运行测试
python -m unittest discover -s tests -v

# 6. 执行发布
python publish_oneclick.py
```

---

## 脚本说明

### install_tools.py — 环境安装

自动检测操作系统并安装 Git 和 GitHub CLI。

```bash
python install_tools.py              # 安装所有工具
python install_tools.py --git        # 仅安装 Git
python install_tools.py --gh         # 仅安装 GitHub CLI
python install_tools.py --verify     # 仅验证安装
```

**支持的平台**：
- Windows：Scoop / Chocolatey / 手动下载
- macOS：Homebrew
- Linux：apt / dnf / pacman

### publish_oneclick.py — 一键发布

自动创建 Git 标签、推送、创建 GitHub Release。

```bash
python publish_oneclick.py              # 执行发布
python publish_oneclick.py --dry-run    # 预览模式
python publish_oneclick.py --verbose    # 详细日志
python publish_oneclick.py --version 4.3.1  # 指定版本
```

**执行流程**：
1. 检查前置条件（Git、gh CLI、Release Notes）
2. 创建 Git 标签
3. 推送标签到远程
4. 创建 GitHub Release
5. 生成发布摘要

### run_all.py — 一键执行

自动完成所有发布步骤。

```bash
python run_all.py                      # 完整流程
python run_all.py --test-only          # 仅运行测试
python run_all.py --publish            # 执行发布
python run_all.py --dry-run            # 预览发布流程
python run_all.py --skip-tests         # 跳过测试
python run_all.py --install            # 安装环境工具
```

---

## CI/CD 配置

**文件**：[.github/workflows/release.yml](.github/workflows/release.yml)

**触发条件**：
- 推送标签（v*.*.*）
- 手动触发（workflow_dispatch）

**工作流步骤**：
1. 构建与测试（多平台：Ubuntu / Windows / macOS）
2. 代码质量检查（预检 / 文件检查 / Git 检查）
3. 创建 GitHub Release
4. 发布 VS Code 插件（VS Marketplace / Open VSX）
5. 发送通知（钉钉）

**所需 Secrets**：
- `GITHUB_TOKEN`（自动提供）
- `VSCE_PAT`（VS Marketplace 发布令牌）
- `OVSX_PAT`（Open VSX 发布令牌）
- `DINGTALK_WEBHOOK`（钉钉通知 Webhook）

---

## 已知问题

| 编号 | 问题 | 解决方案 |
|---|---|---|
| KNP-001 | LLM 需要 API Key | `pip install anthropic` ✅ 已完成 |
| KNP-002 | VS Code 插件需编译 | `python install_dependencies.py --vscode` |
| KNP-003 | Jupyter 需 IPython | `python install_dependencies.py --jupyter` |
| KNP-004 | Git 未安装 | `python install_tools.py --git` |
| KNP-005 | GitHub CLI 未安装 | `python install_tools.py --gh` |

完整列表见 [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)

---

## 发布检查清单

- [ ] 运行 `python install_tools.py`
- [ ] 运行 `python check_git.py`
- [ ] 运行 `python check_files.py`
- [ ] 运行 `python -m unittest discover -s tests -v`
- [ ] 运行 `python publish_oneclick.py --dry-run`（预览）
- [ ] 运行 `python publish_oneclick.py`（正式发布）

---

**发布状态：✅ 就绪（等待环境安装）**
