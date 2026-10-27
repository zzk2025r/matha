# matha-auth 生产环境 Helm Chart 部署清单
> 版本: v1.0.0 | 生成时间: 2026-08-20

---

## 1. 前置条件检查清单

### 1.1 基础设施
- [ ] Kubernetes 集群版本 ≥ 1.28
- [ ] Helm 版本 ≥ 3.14
- [ ] `kubectl` 已配置并连接到目标集群
- [ ] 私有容器镜像仓库已就绪（如 Harbor / ECR / GCR）
- [ ] TLS 证书已签发（或 cert-manager 已安装）

### 1.2 Kubernetes 资源
```bash
# 创建命名空间
kubectl create namespace matha-auth

# 创建 Secret（JWT 密钥）
kubectl create secret generic matha-auth-secrets \
  --namespace matha-auth \
  --from-literal=jwt-secret="$(openssl rand -base64 64)"

# 创建 TLS Secret（如使用 cert-manager 可跳过）
kubectl create secret tls auth-tls-secret \
  --namespace matha-auth \
  --cert=tls.crt --key=tls.key
```

### 1.3 Ingress Controller
```bash
# 检查 nginx-ingress 是否已安装
kubectl get deployment nginx-ingress-controller -n ingress-nginx
# 如未安装:
# helm install ingress-nginx ingress-nginx/ingress-nginx \
#   --namespace ingress-nginx --create-namespace
```

---

## 2. 部署配置

### 2.1 镜像构建 & 推送
```bash
# 构建 Docker 镜像
docker build -t docker.your-company.com/matha-auth:1.0.0 \
  -f packages/Dockerfile .

# 推送至私有仓库
docker push docker.your-company.com/matha-auth:1.0.0
```

### 2.2 Helm 部署
```bash
# 使用生产覆盖配置
helm upgrade --install matha-auth ./charts/matha-auth \
  --namespace matha-auth \
  --create-namespace \
  --values charts/matha-auth/values-prod.yaml \
  --set jwtSecret="$(kubectl get secret matha-auth-secrets \
    --namespace matha-auth --output=jsonpath='{.data.jwt-secret}' | base64 -d)"
```

---

## 3. 资源配置详情

### 3.1 Deployment
| 字段 | 值 | 说明 |
|---|---|---|
| `replicaCount` | 3 | 避免单点故障 |
| `strategy.type` | RollingUpdate | 滚动更新，零停机 |
| `strategy.rollingUpdate.maxSurge` | 1 | 最多超出 1 个副本 |
| `strategy.rollingUpdate.maxUnavailable` | 0 | 不允许不可用 |

### 3.2 资源限制（Limits & Requests）
| 容器 | Request | Limit | 说明 |
|---|---|---|---|
| CPU | 250m | 1000m | 1 核上限，防 CPU 饥饿 |
| Memory | 256Mi | 512Mi | 2x 缓冲比，防 OOM |

### 3.3 探针配置
| 探针类型 | 路径 | 端口 | 初始延迟 | 间隔 | 超时 | 失败阈值 | 成功阈值 |
|---|---|---|---|---|---|---|---|
| Liveness | `/health` | 8000 | 10s | 15s | 5s | 3 | - |
| Readiness | `/health` | 8000 | 5s | 10s | 5s | 3 | 1 |

> **Liveness**: 连续 3 次失败（45s）后重启 Pod，防止僵尸进程。
> **Readiness**: 连续 3 次失败后移除 Service 端点，流量逐步切走。

### 3.4 HPA（可选，推荐启用）
```yaml
# charts/matha-auth/templates/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: matha-auth
  namespace: matha-auth
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: matha-auth
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

---

## 4. 部署后验证

### 4.1 资源状态检查
```bash
# 查看所有资源状态
kubectl get all -n matha-auth

# 预期输出:
# NAME                            READY   STATUS    RESTARTS   AGE
# pod/matha-auth-xxx-abc          1/1     Running   0          2m
# pod/matha-auth-xxx-def          1/1     Running   0          2m
# pod/matha-auth-xxx-ghi          1/1     Running   0          2m
# NAME               TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE
# service/matha-auth ClusterIP  10.96.0.100   <none>        80/TCP    2m
# NAME                       READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/matha-auth 3/3     3            3           2m
```

### 4.2 健康检查
```bash
# 验证 /health 端点
kubectl port-forward svc/matha-auth 8000:8000 -n matha-auth &
curl -s http://localhost:8000/health | jq

# 验证登录流程
TOKEN=$(curl -s -X POST 'http://localhost:8000/login?username=admin&password=Admin1234' \
  | jq -r '.access_token')
curl -s http://localhost:8000/roles/admin \
  -H "Authorization: Bearer $TOKEN" | jq
```

### 4.3 日志检查
```bash
# 查看启动日志
kubectl logs -n matha-auth -l app=matha-auth --tail=50

# 预期日志:
# 2026-08-20 10:00:00 [INFO] matha_auth.server: Starting matha-auth v1.0.0
# 2026-08-20 10:00:00 [INFO] matha_auth.service: SessionManager 初始化完成
# 2026-08-20 10:00:00 [INFO] matha_auth.rbac: 内置角色加载完成: admin, editor, viewer, guest
```

---

## 5. 安全加固清单

| 检查项 | 状态 | 说明 |
|---|---|---|
| [ ] TLS 已启用 | | Ingress 配置 TLS Secret |
| [ ] JWT 密钥 ≥ 64 字符 | | 使用 openssl rand 生成 |
| [ ] pbkdf2Rounds ≥ 12 | | 防止暴力破解 |
| [ ] accessTokenExp ≤ 2h | | 减少泄露窗口 |
| [ ] 审计日志已启用 | | `/audit` 端点可查 |
| [ ] 非 root 容器运行 | | Dockerfile USER 设置 |
| [ ] 镜像签名验证 | | cosign/notation |
| [ ] Pod 安全标准 | | PSP/PSA 限制 |
| [ ] 网络策略 | | 限制入站/出站流量 |
| [ ] Secret 加密存储 | | Sealed Secrets / KMS |

---

## 6. 回滚方案

```bash
# 查看部署历史
helm history matha-auth -n matha-auth

# 回滚到上一版本
helm rollback matha-auth 1 -n matha-auth

# 强制重启（故障恢复）
kubectl rollout restart deployment/matha-auth -n matha-auth
```

---

## 7. 监控告警配置（Prometheus + Grafana）

### 7.1 PodMonitor
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: matha-auth
  namespace: matha-auth
spec:
  selector:
    matchLabels:
      app: matha-auth
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
```

### 7.2 告警规则（Prometheus Rule）
```yaml
groups:
  - name: matha-auth
    rules:
      - alert: MathaAuthHighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels: { severity: critical }
        annotations:
          summary: "matha-auth 错误率 > 5%"

      - alert: MathaAuthHighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "matha-auth P99 延迟 > 1s"

      - alert: MathaAuthPodCrashLoop
        expr: kube_pod_status_phase{phase="CrashLoopBackOff"} == 1
        for: 2m
        labels: { severity: critical }
        annotations:
          summary: "matha-auth Pod 进入 CrashLoop"
```

---

## 8. 一键部署脚本

```bash
#!/bin/bash
set -euo pipefail

NAMESPACE="matha-auth"
VERSION="1.0.0"
CHART_DIR="./charts/matha-auth"
VALUES_FILE="${CHART_DIR}/values-prod.yaml"

echo "=== matha-auth 生产部署 ==="
echo "版本: $VERSION"
echo "命名空间: $NAMESPACE"

# 1. 前置检查
echo "[1/6] 检查前置条件..."
kubectl cluster-info > /dev/null || { echo "✗ kubectl 连接失败"; exit 1; }
helm version --short > /dev/null || { echo "✗ helm 未安装"; exit 1; }

# 2. 创建命名空间和 Secret
echo "[2/6] 创建命名空间和 Secret..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic matha-auth-secrets \
  --namespace "$NAMESPACE" \
  --from-literal=jwt-secret="$(openssl rand -base64 64)" \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. 部署 Helm Chart
echo "[3/6] 部署 Helm Chart..."
helm upgrade --install matha-auth "$CHART_DIR" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  --values "$VALUES_FILE" \
  --timeout 5m

# 4. 等待就绪
echo "[4/6] 等待 Pod 就绪..."
kubectl rollout status deployment/matha-auth -n "$NAMESPACE" --timeout=300s

# 5. 验证健康
echo "[5/6] 验证健康检查..."
sleep 10
READY=$(kubectl get pods -n "$NAMESPACE" -l app=matha-auth \
  --output=jsonpath='{.items[*].status.containerStatuses[0].ready}' | tr ' ' '\n' | grep -c true)
TOTAL=$(kubectl get pods -n "$NAMESPACE" -l app=matha-auth --no-headers | wc -l)
echo "  就绪: $READY/$TOTAL"

# 6. 生成报告
echo "[6/6] 生成部署报告..."
kubectl get all -n "$NAMESPACE" -o wide > "docs/DEPLOY_REPORT_$(date +%Y%m%d_%H%M%S).md"

echo "✓ 部署完成！"
echo "  服务地址: https://auth.your-company.com"
echo "  文档地址: https://auth.your-company.com/docs"
```
