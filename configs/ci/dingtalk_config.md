# CI/CD 钉钉通知配置

> 可复用配置，支持多环境部署  
> 版本：v1.0  
> 更新时间：2025-07-26

---

## 一、配置说明

本配置文件定义 Matha CI/CD 流水线的钉钉通知模板，可在多个 workflow 中复用。

---

## 二、环境变量

```bash
# GitHub Secrets 配置
DINGTALK_WEBHOOK        # 必填：钉钉机器人 Webhook URL
DINGTALK_SECRET         # 可选：加签密钥（推荐开启）
DINGTALK_AT_MOBILE     # 可选：@指定手机号
DINGTALK_AT_ALL        # 可选：@所有人 (true/false)
MATHA_ENV              # 可选：环境标识 (dev/staging/prod)
```

---

## 三、通知模板

### 3.1 成功通知

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "HAL 测试通过",
    "text": "## ✅ HAL 压力测试通过\n\n"
          + "**环境**: ${MATHA_ENV:-production}\n"
          + "**分支**: ${GITHUB_REF_NAME}\n"
          + "**Commit**: ${GITHUB_SHA}\n"
          + "**时间**: $(date '+%Y-%m-%d %H:%M:%S')\n"
          + "**运行**: [GitHub Actions](${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID})\n"
  }
}
```

### 3.2 失败通知

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "HAL 测试失败",
    "text": "## ❌ HAL 压力测试失败\n\n"
          + "**环境**: ${MATHA_ENV:-production}\n"
          + "**分支**: ${GITHUB_REF_NAME}\n"
          + "**Commit**: ${GITHUB_SHA}\n"
          + "**时间**: $(date '+%Y-%m-%d %H:%M:%S')\n"
          + "**失败作业**: ${GITHUB_JOB}\n"
          + "**运行**: [查看日志](${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID})\n"
          + "\n请尽快检查！"
  }
}
```

### 3.3 警告通知（性能下降）

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "HAL 性能告警",
    "text": "## ⚠️ HAL 性能下降告警\n\n"
          + "**环境**: ${MATHA_ENV:-production}\n"
          + "**分支**: ${GITHUB_REF_NAME}\n"
          + "**当前吞吐**: ${CURRENT_THROUGHPUT} ops/sec\n"
          + "**基准吞吐**: ${BASELINE_THROUGHPUT} ops/sec\n"
          + "**下降比例**: ${DEGRADATION_PERCENT}%\n"
          + "建议检查最近的代码变更。"
  }
}
```

---

## 四、复用方式

### 4.1 GitHub Actions 中引用

```yaml
# 在所有需要通知的 workflow 中添加
env:
  DINGTALK_WEBHOOK: ${{ secrets.DINGTALK_WEBHOOK }}
  DINGTALK_SECRET: ${{ secrets.DINGTALK_SECRET }}
  MATHA_ENV: ${{ matrix.env }}  # dev/staging/prod

# 成功通知
- name: 钉钉通知 - 成功
  if: success()
  run: |
    curl -X POST "$DINGTALK_WEBHOOK" \
      -H 'Content-Type: application/json' \
      -d "$(cat .github/configs/dingtalk_success.json | envsubst)"

# 失败通知
- name: 钉钉通知 - 失败
  if: failure()
  run: |
    curl -X POST "$DINGTALK_WEBHOOK" \
      -H 'Content-Type: application/json' \
      -d "$(cat .github/configs/dingtalk_failure.json | envsubst)"
```

### 4.2 多环境配置

```yaml
# .github/workflows/stress_test.yml
jobs:
  test-dev:
    env:
      MATHA_ENV: dev
    # 使用不同的 webhook（可选）

  test-staging:
    env:
      MATHA_ENV: staging
    # 使用 staging webhook

  test-prod:
    env:
      MATHA_ENV: prod
    # 使用 prod webhook
```

---

## 五、安全配置

### 5.1 加签验证（推荐）

在钉钉机器人设置中开启"加签"，获取 secret：

```bash
# Python 加签计算
import hmac
import hashlib
import base64
import urllib.parse

timestamp = str(round(time.time() * 1000))
secret = "YOUR_SECRET"
string_to_sign = timestamp + '\n' + secret
hmac_code = hmac.new(string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).digest()
sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

# 请求 URL
url = f"{WEBHOOK}&timestamp={timestamp}&sign={sign}"
```

### 5.2 权限控制

- Webhook URL 必须存储在 GitHub Secrets 中
- 禁止在代码中硬编码 Webhook
- 定期轮换 Secret

---

## 六、测试验证

```bash
# 测试通知是否可用
curl -X POST "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"msgtype":"text","text":{"content":"🧪 Matha HAL CI 通知测试"}}'
```

---

## 七、故障排查

| 问题 | 原因 | 解决方案 |
|---|---|---|
| 通知未发送 | Webhook 错误 | 检查 Secrets 配置 |
| 签名验证失败 | Secret 不匹配 | 重新生成加签 |
| 消息格式错误 | JSON 格式问题 | 检查模板语法 |
| 多环境混乱 | 环境变量未设置 | 检查 matrix 配置 |
