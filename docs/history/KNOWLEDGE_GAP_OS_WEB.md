# Matha 操作系统与Web应用 知识补充清单

## 一、操作系统（OS）— 优先级: ● 高

### 1.1 进程管理数学

| 编号 | 公式/算法 | Matha实现示例 | 用途 |
|---|---|---|---|
| OS-01 | 周转时间 = 完成时间 - 到达时间 | `func 周转时间(完成: Float, 到达: Float) -> Float = (完成, 到达) => 完成 - 到达` | 调度评估 |
| OS-02 | 等待时间 = 周转时间 - 服务时间 | `func 等待时间(周转: Float, 服务: Float) -> Float = (周转, 服务) => 周转 - 服务` | 调度评估 |
| OS-03 | 平均周转时间 = Σ周转时间 / n | `func 平均周转时间(列表: List) -> Float = (列表) => 求和(列表) / len(列表)` | 性能评估 |
| OS-04 | CPU利用率 = 忙碌时间 / 总时间 | `func CPU利用率(忙碌: Float, 空闲: Float) -> Float = (忙碌, 空闲) => 忙碌 / (忙碌 + 空闲)` | 系统监控 |
| OS-05 | 吞吐量 = 进程数 / 总时间 | `func 吞吐量(进程数: Int, 总时间: Float) -> Float = (进程数, 总时间) => 进程数 / 总时间` | 性能评估 |
| OS-06 | 响应时间比 = 响应时间 / 要求时间 | `func 响应时间比(响应: Float, 要求: Float) -> Float = (响应, 要求) => 响应 / 要求` | 交互性 |
| OS-07 | 进程状态转移矩阵 | `case (当前状态, 事件) of ...` | 状态机 |

### 1.2 调度算法数学

| 编号 | 算法 | 核心公式 | Matha实现思路 |
|---|---|---|---|
| OS-10 | **FCFS** | T_wait[i] = ΣT_burst[0..i-1] | 累加到达后的Burst时间 |
| OS-11 | **SJF（非抢占）** | 选择min(T_burst)的进程执行 | 按Burst排序后FCFS |
| OS-12 | **优先级调度** | T_priority = Σ(w_i × T_i) / Σw_i | 权重加权平均 |
| OS-13 | **轮转RR** | T_context = n × T_cs | 上下文切换开销 |
| OS-14 | **HRRN** | 响应比 = 1 + 等待时间 / 服务时间 | 见WEB-01 |
| OS-15 | **SRT（抢占式SJF）** | 抢占当 T_remaining_new < T_remaining_cur | 比较剩余时间 |

### 1.3 内存管理数学

| 编号 | 公式 | Matha实现 |
|---|---|---|
| OS-20 | 页表项数 = 内存大小 / 页大小 | `func 页表项数(内存: Int, 页大小: Int) -> Int = (内存, 页大小) => 内存 / 页大小` |
| OS-21 | EAO = hit_rate×T_hit + (1-hit_rate)×T_fault | `func EAO(命中率: Float, 命中时间: Float, 缺页时间: Float) -> Float = (命中率, 命中时间, 缺页时间) => 命中率*命中时间 + (1-命中率)*缺页时间` |
| OS-22 | 缺页率 = 缺页次数 / 总访问次数 | `func 缺页率(缺页: Int, 总访问: Int) -> Float = (缺页, 总访问) => 缺页 / 总访问` |
| OS-23 | 外部碎片率 = (总空闲-最大连续)/总空闲 | `func 外部碎片率(总空闲: Int, 最大连续: Int) -> Float = (总空闲, 最大连续) => 1.0 - 最大连续/总空闲` |
| OS-24 | 逻辑地址 = 页号×页大小 + 页内偏移 | `func 逻辑地址(页号: Int, 页内偏移: Int, 页大小: Int) -> Int = (页号, 页内偏移, 页大小) => 页号*页大小 + 页内偏移` |
| OS-25 | 分段地址 = 段基址 + 段内偏移 | `func 分段地址(段基址: Int, 段偏移: Int) -> Int = (段基址, 段偏移) => 段基址 + 段偏移` |

### 1.4 文件系统数学

| 编号 | 公式 | Matha实现 |
|---|---|---|
| OS-30 | 磁盘访问 = 寻道 + 旋转延迟 + 传输 | `func 磁盘访问(寻道: Float, 旋转: Float, 传输: Float) -> Float = (寻道, 旋转, 传输) => 寻道 + 旋转 + 传输` |
| OS-31 | 平均寻道 ≈ 2/3 × 最大寻道 | `func 平均寻道(最大寻道: Float) -> Float = (最大寻道) => 最大寻道 * 2.0 / 3.0` |
| OS-32 | 旋转延迟 = 1/(RPM×60) | `func 旋转延迟(RPM: Float) -> Float = (RPM) => 1.0 / (RPM * 60.0)` |
| OS-33 | inode最大文件尺寸 = (直接+间接)×块大小 | `func inode最大文件尺寸(块大小: Int) -> Int = (块大小) => (12 + 块大小/4 + (块大小/4)^2 + (块大小/4)^3) * 块大小` |
| OS-34 | FAT表项数 = 磁盘大小 / 簇大小 | `func FAT表项数(磁盘大小: Int, 簇大小: Int) -> Int = (磁盘大小, 簇大小) => 磁盘大小 / 簇大小` |

### 1.5 死锁与同步数学

| 编号 | 公式/判定 | Matha实现 |
|---|---|---|
| OS-40 | 死锁充分条件: 互斥∧持有等待∧非抢占∧循环等待 | `func 死锁条件(互斥: Bool, 持有: Bool, 非抢占: Bool, 循环: Bool) -> Bool = (互斥, 持有, 非抢占, 循环) => 互斥 and 持有 and 非抢占 and 循环` |
| OS-41 | 银行家安全性: 存在安全序列 | 图遍历检测 |
| OS-42 | 信号量wait: S<=0?阻塞:S-- | `func 信号量wait(S: Int) -> Int = (S) => if S <= 0 then -1 else S - 1` |
| OS-43 | 生产者-消费者平衡 | 生产速率×items = 消费速率×items |

---

## 二、Web应用 — 优先级: ● 高

### 2.1 HTTP协议数学

| 编号 | 概念 | 公式/规则 | Matha实现 |
|---|---|---|---|
| WEB-01 | 状态码分类 | 2xx成功, 3xx重定向, 4xx客户端错误, 5xx服务器错误 | `func HTTP分类(代码: Int) -> String = (代码) => case 代码 of 2xx->"成功", 3xx->"重定向", ...` |
| WEB-02 | URI编码 | %HH where HH=hex(ord(ch)) | `func URI编码(ch: String) -> String = (ch) => "%" + hex(ord(ch[0]))` |
| WEB-03 | Content-Length | body字节数 | `func 内容长度(body: String) -> Int = (body) => len(body)` |
| WEB-04 | Cookie格式 | Name=Value; Path=/; Max-Age=秒数 | `func Cookie构建(名称: String, 值: String, 秒数: Int) -> String = (名称, 值, 秒数) => 名称 + "=" + 值 + "; Max-Age=" + str(秒数)` |

### 2.2 前端状态管理数学

| 编号 | 概念 | 公式 | Matha实现 |
|---|---|---|---|
| WEB-20 | 不可变更新开销 | O(depth) 路径复制 | `func 状态更新深度(状态树深度: Int) -> Int = (状态树深度) => 状态树深度` |
| WEB-21 | Redux reduce复合 | reducer(state, action) = prev → next | 函数组合 |
| WEB-22 | 虚拟DOM diff | O(n) 树比较 | 递归比较 |

### 2.3 本地存储数学

| 编号 | 概念 | 公式 | Matha实现 |
|---|---|---|---|
| WEB-30 | localStorage容量 | ~5MB/源 | `func localStorage上限() -> Float = () => 5.0` |
| WEB-31 | JSON序列化开销 | JSON.stringify(obj)大小 | `func JSON大小(obj: String) -> Int = (obj) => len(obj)` |
| WEB-32 | Cache Storage | cache.addAll([urls]) | URL列表 |

### 2.4 网络协议数学

| 编号 | 概念 | 公式 | Matha实现 |
|---|---|---|---|
| WEB-40 | TCP三次握手 | SYN→SYN-ACK→ACK | 状态机 |
| WEB-41 | WebSocket帧开销 | 2-10字节头+payload+mask | `func WebSocket帧大小(payload: Int) -> Int = (payload) => 帧头(payload) + payload` |
| WEB-42 | HTTP/2多路复用 | 单TCP连接多stream | 流ID管理 |
| WEB-43 | 带宽延迟积 | BDP = bandwidth × RTT | `func BDP(带宽: Float, RTT: Float) -> Float = (带宽, RTT) => 带宽 * RTT` |
| WEB-44 | TTFB = DNS + TCP + TLS + server | `func TTFB(DNS: Float, TCP: Float, TLS: Float, 服务器: Float) -> Float = (DNS, TCP, TLS, 服务器) => DNS + TCP + TLS + 服务器` |

### 2.5 安全认证数学

| 编号 | 概念 | 公式 | Matha实现 |
|---|---|---|---|
| WEB-50 | JWT结构 | header.payload.signature (Base64URL) | 三段拼接 |
| WEB-51 | JWT签名验证 | HMACSHA256(header.payload, secret) | 哈希运算 |
| WEB-52 | JWT过期检查 | exp > now → valid | `func JWT有效(exp: Int, now: Int) -> Bool = (exp, now) => exp > now` |
| WEB-53 | CSRF Token | 服务端生成随机token | 随机数 |
| WEB-54 | XSS防护 | 输入编码 + 输出转义 | `func XSS编码(ch: String) -> String = (ch) => "&#" + str(ord(ch)) + ";"` |
| WEB-55 | 会话ID熵 | entropy = log2(可能组合数) ≥ 128bit | `func 会话熵(bit数: Int) -> Int = (bit数) => 2 ^ bit数` |

### 2.6 API设计数学

| 编号 | 概念 | 公式 | Matha实现 |
|---|---|---|---|
| WEB-60 | 分页计算 | offset = (page-1)×limit, total = ceil(count/limit) | `func 总页数(总数: Int, 每页: Int) -> Int = (总数, 每页) => (总数 + 每页 - 1) / 每页` |
| WEB-61 | 速率限制 | tokens = rate × (now - last_refill) | `func 令牌桶剩余(容量: Int, 速率: Float, 已用: Int,  elapsed: Float) -> Int = (容量, 速率, 已用, elapsed) => min(容量, 已用 - int(速率*elapsed))` |
| WEB-62 | GraphQL复杂度 | O(depth × fanout) per field | 深度×分支 |

### 2.7 性能优化数学

| 编号 | 概念 | 公式 | Matha实现 |
|---|---|---|---|
| WEB-70 | LCP (最大内容绘制) | 最大内容元素渲染时间 | 时间测量 |
| WEB-71 | CLS (累积布局偏移) | Σ(layout_shift_score) | 偏移累加 |
| WEB-72 | 懒加载阈值 | 视口外200px开始加载 | `func 懒加载可见(滚动位置: Int, 元素位置: Int) -> Bool = (滚动位置, 元素位置) => 元素位置 < 滚动位置 + 视口高 + 200` |
| WEB-73 | 防抖 | 最后一次调用后delay执行 | 定时器 |
| WEB-74 | 虚拟滚动窗口 | visible_start = floor(scrollTop / rowHeight) | `func 可见起始(滚动: Int, 行高: Int) -> Int = (滚动, 行高) => 滚动 / 行高` |

---

## 三、已实现的模块清单

### 已创建的OS模块 (5个)

| 文件 | 函数数 | 覆盖内容 |
|---|---|---|
| [os/process_math.matha](file:///D:/trae/matha/resource/os/process_math.matha) | ~25 | 周转时间、等待时间、CPU利用率、进程状态转移 |
| [os/scheduling_math.matha](file:///D:/trae/matha/resource/os/scheduling_math.matha) | ~20 | FCFS/SJF/RR/HRRN调度、平均等待时间 |
| [os/memory_math.matha](file:///D:/trae/matha/resource/os/memory_math.matha) | ~15 | 页表开销、EAO、缺页率、碎片率、地址合成 |
| [os/filesystem_math.matha](file:///D:/trae/matha/resource/os/filesystem_math.matha) | ~15 | 磁盘访问、inode索引、FAT表、目录树 |
| [os/deadlock_sync_math.matha](file:///D:/trae/matha/resource/os/deadlock_sync_math.matha) | ~10 | 死锁条件、银行家算法、信号量、生产者-消费者 |

### 已创建的Web模块 (2个)

| 文件 | 函数数 | 覆盖内容 |
|---|---|---|
| [web/web_math.matha](file:///D:/trae/matha/resource/web/web_math.matha) | ~20 | HTTP状态码、URI编码、分页、JWT、CORS、缓存 |
| [web/network_math.matha](file:///D:/trae/matha/resource/web/network_math.matha) | ~15 | TCP握手、WebSocket帧、XSS防护、会话管理 |

---

## 四、待补充模块（优先级排序）

### ● 高优先级

| 模块 | 关键公式/算法 | 预计函数数 |
|---|---|---|
| `os/cpu_scheduling_advanced.matha` | SRT抢占调度、多级反馈队列、CPU亲和性 | ~15 |
| `web/api_design.matha` | REST路由、GraphQL查询、OpenAPI规范 | ~12 |
| `web/performance.matha` | LCP/CLS/FID指标、虚拟滚动、懒加载优化 | ~10 |

### ◐ 中优先级

| 模块 | 关键公式/算法 | 预计函数数 |
|---|---|---|
| `web/state_management.matha` | Redux/reducer模式、选择器缓存、不可变更新 | ~10 |
| `web/storage.matha` | IndexedDB事务、Cache Storage、配额计算 | ~8 |
| `os/advanced_memory.matha` | 逐页置换、工作集模型、抖动检测 | ~10 |

### ○ 低优先级

| 模块 | 关键公式/算法 | 预计函数数 |
|---|---|---|
| `web/security_advanced.matha` | BCrypt哈希、OAuth2流程、CSP策略 | ~8 |
| `os/advanced_scheduling.matha` | 实时调度、硬实时约束、调度器选型 | ~8 |

---

## 五、Matha语法约束提醒

编写新知识模块时需注意：

1. **类型标注必须**: `func f(x: Int, y: Int) -> Int = (x, y) => ...`
2. **调用方式**: 使用柯里化 `f(x)(y)`，**不可**用逗号 `f(x, y)`
3. **零参函数**: `func f() -> T = () => x` 定义可以，但**调用** `f()` 会失败（解释器限制）
4. **递归多参**: 函数体内避免逗号调用，使用 `f(a % b)(b)` 而非 `f(a % b, b)`
5. **标识符**: 可用ASCII、CJK、希腊字母（θ λ ω μ）
6. **模块内定义**: `module Name { func ... }` 完全支持

---

## 六、测试验证命令

```bash
# 运行构建能力测试
python -m tests.test_build_capability

# 运行多参边界测试
python -m tests.test_multiParam_boundary

# 运行知识库测试
python -m tests.test_knowledge_lib

# 运行资源库测试
python -m tests.test_resource_lib
```
