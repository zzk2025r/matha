# 高级教程

## 教程 11：并发编程进阶

### Future/Promise 模式

```matha
# 创建 Future
f = Future()

# 设置结果（在其他线程中）
f.set_result(42)

# 获取结果
print(f.result)  # 42

# 使用 Promise
p = Promise()
future = p.resolve(100)
print(future.result)  # 100
```

### Mutex/Semaphore

```matha
# 互斥锁
m = Mutex()
if m.acquire():
    # 临界区
    m.release()

# 信号量
s = Semaphore(2)  # 允许2个并发
s.acquire()
s.release()
```

### 并行计算

```matha
# 并行映射
results = Parallel.map(lambda x: x * x, [1, 2, 3, 4, 5])
# [1, 4, 9, 16, 25]

# 并行过滤
filtered = Parallel.filter(lambda x: x > 2, [1, 2, 3, 4, 5])
# [3, 4, 5]

# 并行归约
total = Parallel.reduce(lambda acc, x: acc + x, [1, 2, 3, 4, 5], 0)
# 15

# 工作窃取
tasks = [lambda: i*2 for i in range(10)]
results = Parallel.work_stealing(tasks)
```

## 教程 12：LSP 增强开发

### 代码补全

```matha
# LSP 补全支持上下文感知
lsp = MathaLSPEnhanced()
completions = lsp.complete("fib(", (0, 4))
# 返回所有以 fib 开头的函数补全
```

### 签名帮助

```matha
sig = lsp.signature_help("fib(x, y)", (0, 3))
# 返回函数签名信息
```

### 代码格式化

```matha
formatted = lsp.format_document(source_code)
# 返回格式化后的代码
```

### 代码操作

```matha
actions = lsp.code_actions(source, range)
# 返回重构建议（提取函数、修复导入等）
```

## 教程 13：图形渲染进阶

### 着色器

```matha
canvas = Canvas(800, 600)
shader = canvas.create_shader("vertex_fragment")
# 创建自定义着色器
```

### 帧缓冲

```matha
fb = canvas.create_framebuffer(512, 512)
canvas.bind_framebuffer(fb)
# 渲染到帧缓冲
```

### 计算着色器

```matha
compute = canvas.compute_shader(256, 256)
# 运行通用计算
```

### Mipmap 和视口

```matha
canvas.generate_mipmap()  # 生成多层次纹理
canvas.set_viewport(0, 0, 800, 600)  # 设置视口
canvas.clear_buffers()  # 清除所有缓冲
```

## 教程 14：物理引擎进阶

### 物理世界

```matha
# 创建物理世界
world = PhysicsWorld(gravity=Vec2(0, -9.8))

# 添加刚体
body = RigidBody(velocity=Vec2(0, 0))
world.add_body(body)

# 物理步进
world.step(0.016)  # 60 FPS

# 检测碰撞
collisions = world.check_collisions()

# 获取统计
stats = world.get_stats()
```

## 教程 15：标准库扩展

### 列表操作

```matha
# 长度
len([1, 2, 3])  # 3

# 反转
reverse([1, 2, 3])  # [3, 2, 1]

# 排序
sort([3, 1, 2])  # [1, 2, 3]

# 映射
map(lambda x: x * 2, [1, 2, 3])  # [2, 4, 6]

# 过滤
filter(lambda x: x > 1, [1, 2, 3])  # [2, 3]

# 归约
reduce(lambda a, b: a + b, [1, 2, 3], 0)  # 6
```

### 字符串操作

```matha
join(",", ["a", "b", "c"])  # "a,b,c"
split(",", "a,b,c")  # ["a", "b", "c"]
upper("hello")  # "HELLO"
lower("WORLD")  # "world"
contains("hello", "ell")  # True
startswith("hello", "he")  # True
endswith("hello", "lo")  # True
slice("hello", 1, 3)  # "el"
```

### JSON 和随机

```matha
# JSON
json_dumps({"a": 1})  # '{"a": 1}'
json_loads('{"a":1}')  # {"a": 1}

# 随机数
random_int(1, 100)  # 1-100 随机整数
random_float()  # 0-1 随机浮点
random_choice(["a", "b", "c"])  # 随机选择
shuffle([1, 2, 3])  # 打乱列表
```

## 教程 16：区块链开发

```matha
# 创建区块链
blockchain = create_blockchain()

# 创建交易
tx = create_transaction(from_addr="Alice", to_addr="Bob", amount=100)

# 挖矿
block = mine_block(blockchain)

# 部署智能合约
contract = deploy_smart_contract(blockchain, "MyContract", ...)
```

## 教程 17：量子计算

```matha
# 创建量子计算机
qc = create_quantum_computer(num_qubits=4)

# 创建量子电路
circuit = create_quantum_circuit()

# 应用量子门
apply_gate(circuit, "H", 0)
apply_gate(circuit, "CNOT", 0, 1)

# 运行算法
result = run_algorithm(circuit, "grover")
```

---

*Matha v4.5 | 高级教程*