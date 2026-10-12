# Matha API 文档

## 核心类

### MathaSystem

系统核心类，管理所有领域模块。

```python
from src.matha_system import MathaSystem
ms = MathaSystem(debug=False)
```

### VirtualCodeEngine

虚拟代码引擎，自动注册缺失代码。

```python
from src.virtual_code import VirtualCodeEngine
vc = VirtualCodeEngine()
```

### MathaLSP

LSP 语言服务器。

```python
from src.lsp import MathaLSP
lsp = MathaLSP()
```

### MathaLSPEnhanced

增强版 LSP 服务器。

```python
from src.lsp import MathaLSPEnhanced
lsp = MathaLSPEnhanced()
completions = lsp.complete("fib(", (0, 4))
```

## 领域模块

### 游戏引擎

```python
from src.domains.game_engine import GameEngine, Scene, Entity, Vec2
engine = GameEngine()
```

### 图形引擎

```python
from src.domains.graphics_engine import Canvas, Color
canvas = Canvas(800, 600)
```

### 神经网络

```python
from src.domains.neural_network import NeuralNetwork
nn = NeuralNetwork()
```

### 并发编程

```python
from src.domains.concurrent import Future, Promise, Parallel
f = Future()
```

### 区块链

```python
from src.domains.blockchain import Blockchain
bc = Blockchain()
```

### 量子计算

```python
from src.domains.quantum import QuantumComputer
qc = QuantumComputer()
```

### 音视频处理

```python
from src.domains.audio_video import AudioEngine, VideoEditor
audio = AudioEngine()
```

### 地理空间

```python
from src.domains.geospatial import GeoEngine
geo = GeoEngine()
```

### 化学

```python
from src.domains.chemistry import ChemistryEngine
chem = ChemistryEngine()
```

### 天文学

```python
from src.domains.astronomy import AstroEngine
astro = AstroEngine()
```

### 音乐

```python
from src.domains.music import MusicEngine
music = MusicEngine()
```

### 机器人

```python
from src.domains.robotics import RobotEngine
robot = RobotEngine()
```

### Web框架

```python
from src.domains.web_framework import WebServer
server = WebServer(host="127.0.0.1", port=8080)
```

### 数据库

```python
from src.domains.database import Database
db = Database()
```

### 安全

```python
from src.domains.security import HashEngine, EncryptionEngine
hash_engine = HashEngine()
```

### 数据科学

```python
from src.domains.data_science import DataScienceManager
ds = DataScienceManager()
```

## CLI 命令

```bash
# 计算
matha eval "1+2*3"

# REPL
matha

# 编译
matha-cc compile demo.matha -o c

# 可视化
matha pipeline
matha arch
matha domains

# 领域工具
matha nn
matha blockchain
matha quantum
matha audio
matha game
```

## 内置函数

### 数学

- `sin`, `cos`, `tan`, `asin`, `acos`, `atan`
- `exp`, `log`, `log10`, `log2`, `sqrt`, `pow`
- `abs`, `floor`, `ceil`, `round`, `trunc`
- `max`, `min`, `sum`, `sign`, `hypot`
- `阶乘`, `排列数`, `组合数`, `gcd`
- `pi`, `e`, `tau`, `phi`

### 列表/字符串

- `len`, `reverse`, `sort`, `map`, `filter`, `reduce`
- `join`, `split`, `upper`, `lower`, `strip`, `replace`
- `contains`, `startswith`, `endswith`, `slice`
- `append`, `insert`, `remove`, `pop`
- `chr`, `ord`, `range`, `zip`, `enumerate`
- `any`, `all`, `random_int`, `random_float`
- `random_choice`, `shuffle`
- `json_dumps`, `json_loads`, `time_now`
- `format`, `isinstance`, `type_name`

### 中文逻辑

- `逻辑非`, `逻辑与`, `逻辑或`

---

*Matha v4.5 | API 文档*