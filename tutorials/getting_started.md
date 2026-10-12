# Matha 教程

## 教程 1：Hello World

Matha 的 Hello World 非常简单：

```matha
print("Hello, World!")
```

运行：
```bash
matha eval '"Hello, World!"'
```

## 教程 2：变量和数据类型

```matha
# 数字
年龄 = 25
价格 = 9.99

# 字符串
名称 = "Matha"

# 列表
数字 = [1, 2, 3, 4, 5]

# 布尔值
是有效的 = True
```

## 教程 3：函数定义

```matha
def 相加(a, b):
    return a + b

结果 = 相加(3, 5)
print(结果)  # 8
```

## 教程 4：列表操作

```matha
# 创建列表
水果 = ["苹果", "香蕉", "橙子"]

# 映射
大写水果 = map(lambda x: upper(x), 水果)

# 过滤
长水果 = filter(lambda x: len(x) > 2, 水果)

# 归约
总长度 = reduce(lambda acc, x: acc + len(x), 水果, 0)
```

## 教程 5：字典和 JSON

```matha
# JSON 序列化
用户 = json_dumps({"name": "Alice", "age": 30})

# JSON 反序列化
数据 = json_loads('{"name": "Bob", "age": 25}')
```

## 教程 6：游戏开发

```matha
# 创建游戏引擎
引擎 = create_game_engine()

# 创建场景
场景 = create_scene("main")

# 添加实体
实体 = create_entity("player")
添加碰撞体(实体, 32, 32)
添加刚体(实体, mass=1.0)

# 启动游戏
启动引擎(引擎)
```

## 教程 7：Web 开发

```matha
# 创建 Web 服务器
服务器 = create_web_server(host="127.0.0.1", port=8080)

# 创建 Web 应用
应用 = create_web_app()
```

## 教程 8：数据分析

```matha
# 创建数据科学管理器
ds = create_data_science()

# 创建数据集
数据集 = create_dataset("my_data")
```

## 教程 9：神经网络

```matha
# 创建神经网络
nn = create_neural_network(input_size=784, hidden_size=128, output_size=10)

# 使用神经网络
结果 = nn.predict([0.5, 0.3, 0.8])
```

## 教程 10：区块链

```matha
# 创建区块链
区块链 = create_blockchain()

# 创建交易
交易 = create_transaction(from_addr="Alice", to_addr="Bob", amount=100)

# 挖矿
区块 = mine_block(区块链)
```

---

*Matha v4.5 | 教程*