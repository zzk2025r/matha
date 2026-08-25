#!/bin/bash
# ============================================================
# Matha CI/CD 钉钉通知脚本
#
# 可复用配置，所有 workflow 统一引用此脚本
#
# 用法:
#   bash .github/configs/dingtalk_templates.sh success
#   bash .github/configs/dingtalk_templates.sh failure
#   bash .github/configs/dingtalk_templates.sh performance_alert
#
# 环境变量:
#   DINGTALK_WEBHOOK    - 必填：钉钉机器人 Webhook URL
#   DINGTALK_SECRET     - 可选：加签密钥
#   MATHA_ENV          - 可选：环境标识 (dev/staging/prod)
#   GITHUB_REF_NAME    - GitHub 分支名
#   GITHUB_SHA         - GitHub commit SHA
#   GITHUB_RUN_ID      - GitHub Actions 运行 ID
#   GITHUB_SERVER_URL  - GitHub 服务器 URL
#   GITHUB_REPOSITORY  - GitHub 仓库名
#   CURRENT_THROUGHPUT - 当前吞吐量 (ops/sec)
#   BASELINE_THROUGHPUT - 基准吞吐量 (ops/sec)
# ============================================================

set -euo pipefail

ACTION="${1:-}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# ============================================================
# 工具函数
# ============================================================

# 生成签名 URL（支持加签）
sign_webhook() {
    local webhook="$1"
    local secret="${DINGTALK_SECRET:-}"

    if [ -z "$secret" ]; then
        echo "$webhook"
        return
    fi

    local timestamp=$(date +%s000)
    local string_to_sign="${timestamp}"$'\n'"${secret}"
    local hmac_code=$(echo -n "$string_to_sign" | openssl dgst -sha256 -hmac "$secret" -binary)
    local sign=$(echo -n "$hmac_code" | base64 | tr '+/' '-_' | tr -d '=')

    echo "${webhook}&timestamp=${timestamp}&sign=${sign}"
}

# 发送钉钉消息
send_dingtalk() {
    local webhook_url
    webhook_url=$(sign_webhook "$DINGTALK_WEBHOOK")

    local payload="$1"
    curl -s -X POST "$webhook_url" \
        -H 'Content-Type: application/json' \
        -d "$payload"
}

# ============================================================
# 通知模板
# ============================================================

# 成功通知
notify_success() {
    local env="${MATHA_ENV:-production}"
    local run_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-matha-lang/matha}/actions/runs/${GITHUB_RUN_ID:-unknown}"

    local content="## ✅ HAL 测试通过

**环境**: ${env}
**分支**: ${GITHUB_REF_NAME:-main}
**Commit**: \`${GITHUB_SHA:-unknown:0:8}\`
**时间**: ${TIMESTAMP}
**运行**: [GitHub Actions](${run_url})"

    send_dingtalk "{
      \"msgtype\": \"markdown\",
      \"markdown\": {
        \"title\": \"HAL 测试通过\",
        \"text\": \"${content}\"
      }
    }"
}

# 失败通知
notify_failure() {
    local env="${MATHA_ENV:-production}"
    local run_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-matha-lang/matha}/actions/runs/${GITHUB_RUN_ID:-unknown}"

    local content="## ❌ HAL 测试失败

**环境**: ${env}
**分支**: ${GITHUB_REF_NAME:-main}
**Commit**: \`${GITHUB_SHA:-unknown:0:8}\`
**时间**: ${TIMESTAMP}
**作业**: ${GITHUB_JOB:-unknown}
**运行**: [查看日志](${run_url})

请尽快检查！"

    send_dingtalk "{
      \"msgtype\": \"markdown\",
      \"markdown\": {
        \"title\": \"HAL 测试失败\",
        \"text\": \"${content}\"
      }
    }"
}

# 性能告警通知
notify_performance_alert() {
    local env="${MATHA_ENV:-production}"
    local current="${CURRENT_THROUGHPUT:-0}"
    local baseline="${BASELINE_THROUGHPUT:-100000}"
    local degradation=$(python3 -c "print(max(0, (1 - ${current}/${baseline}) * 100))" 2>/dev/null || echo "0")

    local run_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-matha-lang/matha}/actions/runs/${GITHUB_RUN_ID:-unknown}"

    local content="## ⚠️ HAL 性能下降告警

**环境**: ${env}
**当前吞吐**: ${current} ops/sec
**基准吞吐**: ${baseline} ops/sec
**下降比例**: ${degradation}%
**分支**: ${GITHUB_REF_NAME:-main}
**Commit**: \`${GITHUB_SHA:-unknown:0:8}\`

建议检查最近的代码变更。"

    send_dingtalk "{
      \"msgtype\": \"markdown\",
      \"markdown\": {
        \"title\": \"HAL 性能告警\",
        \"text\": \"${content}\"
      }
    }"
}

# ============================================================
# 主入口
# ============================================================

case "$ACTION" in
    success)
        notify_success
        ;;
    failure)
        notify_failure
        ;;
    performance_alert)
        notify_performance_alert
        ;;
    all)
        # 发送所有通知（用于测试）
        echo "测试通知..."
        notify_success
        notify_failure
        notify_performance_alert
        ;;
    *)
        echo "用法: $0 {success|failure|performance_alert|all}"
        echo ""
        echo "环境变量:"
        echo "  DINGTALK_WEBHOOK    - 钉钉机器人 Webhook URL（必填）"
        echo "  DINGTALK_SECRET     - 加签密钥（可选）"
        echo "  MATHA_ENV           - 环境标识 (dev/staging/prod)"
        echo "  GITHUB_REF_NAME     - GitHub 分支名"
        echo "  GITHUB_SHA          - GitHub commit SHA"
        echo "  GITHUB_RUN_ID       - GitHub Actions 运行 ID"
        echo "  CURRENT_THROUGHPUT  - 当前吞吐量"
        echo "  BASELINE_THROUGHPUT - 基准吞吐量"
        exit 1
        ;;
esac
