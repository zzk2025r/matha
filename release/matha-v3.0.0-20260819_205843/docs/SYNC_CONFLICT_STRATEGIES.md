# Matha 离线同步冲突解决策略

> 生成时间：2025-07-26
> 版本：4.4.7

---

## 一、冲突解决策略详解

### 1. LAST_WRITE_WINS（最后写入优先）⭐ 推荐

**原理**：比较时间戳，保留最新的数据

**适用场景**：
- 大多数文本编辑场景
- 用户频繁修改的记录
- 实时协作编辑

**实现逻辑**：
```python
def last_write_wins(local, remote):
    if remote.timestamp > local.timestamp:
        return remote  # 远程更新
    else:
        return local   # 本地更新
```

**优点**：
- 简单直观
- 不会出现数据丢失
- 符合用户直觉

**缺点**：
- 可能覆盖重要的早期修改
- 需要精确的时间戳

---

### 2. FIRST_WRITE_WINS（最先写入优先）

**原理**：保留最先写入的数据，忽略后续更新

**适用场景**：
- 不可变的记录（如历史归档）
- 审计日志
- 法律合规数据

**实现逻辑**：
```python
def first_write_wins(local, remote):
    if local.timestamp < remote.timestamp:
        return local   # 本地先写入
    else:
        return remote  # 远程先写入
```

**优点**：
- 保证数据的完整性
- 防止数据被意外覆盖

**缺点**：
- 可能丢失重要的更新
- 不适合频繁修改的场景

---

### 3. MERGE（智能合并）⭐ 推荐

**原理**：深度合并两个版本的数据，保留双方的变更

**适用场景**：
- 结构化数据（字典、列表）
- 多人协作编辑
- 配置文件同步

**合并规则**：
| 数据类型 | 合并策略 |
|---------|---------|
| 字典 | 递归合并，本地优先 |
| 列表 | 按 ID 合并去重 |
| 标量 | 本地优先 |
| 嵌套结构 | 递归应用上述规则 |

**实现逻辑**：
```python
def merge(local, remote):
    result = local.copy()
    for key, remote_value in remote.items():
        if key in result:
            local_value = result[key]
            if isinstance(local_value, dict) and isinstance(remote_value, dict):
                result[key] = merge(local_value, remote_value)
            elif isinstance(local_value, list) and isinstance(remote_value, list):
                result[key] = merge_lists(local_value, remote_value)
            # 其他：本地优先
        else:
            result[key] = remote_value
    return result
```

**优点**：
- 最大程度保留双方数据
- 适合结构化数据

**缺点**：
- 实现复杂
- 可能产生意外结果

---

### 4. MANUAL（手动解决）

**原理**：标记冲突，等待用户手动选择

**适用场景**：
- 重要数据（财务记录）
- 敏感操作（权限变更）
- 无法自动决定的场景

**实现流程**：
```
1. 检测到冲突
   ↓
2. 显示双方数据对比
   ↓
3. 用户选择：本地 / 远程 / 手动合并
   ↓
4. 记录解决结果
   ↓
5. 继续同步
```

**优点**：
- 完全可控
- 适合重要数据

**缺点**：
- 用户体验差
- 需要人工介入

---

## 二、实现步骤

### 步骤 1：冲突检测

```python
def detect_conflict(local_data, remote_data):
    """检测是否有冲突"""
    # 时间戳相同但内容不同
    if local_data['timestamp'] == remote_data['timestamp'] and local_data != remote_data:
        return True
    
    # 内容不同
    if local_data != remote_data:
        return True
    
    return False
```

### 步骤 2：冲突解决

```python
def resolve_conflict(conflict: SyncConflict) -> Optional[Dict]:
    """根据策略解决冲突"""
    strategy = conflict.strategy or ConflictStrategy.LAST_WRITE_WINS
    
    if strategy == ConflictStrategy.LAST_WRITE_WINS:
        return last_write_wins(conflict)
    elif strategy == ConflictStrategy.FIRST_WRITE_WINS:
        return first_write_wins(conflict)
    elif strategy == ConflictStrategy.MERGE:
        return merge(conflict)
    elif strategy == ConflictStrategy.MANUAL:
        return None  # 需要手动处理
```

### 步骤 3：应用解决结果

```python
def apply_resolution(conflict: SyncConflict, resolution: Dict):
    """应用解决结果到本地和远程"""
    # 保存到远程
    remote_storage.save(conflict.record_type, conflict.id, resolution)
    
    # 更新本地
    local_storage.save(conflict.record_type, conflict.id, resolution)
    
    # 记录日志
    logger.info(f"冲突已解决: {conflict.id}")
```

### 步骤 4：处理特殊情况

```python
def handle_special_cases(conflict: SyncConflict):
    """处理特殊情况"""
    # 1. 一方删除，另一方修改 → 保留修改
    if conflict.local_data is None and conflict.remote_data is not None:
        return conflict.remote_data
    
    if conflict.remote_data is None and conflict.local_data is not None:
        return conflict.local_data
    
    # 2. 双方都删除 → 删除
    if conflict.local_data is None and conflict.remote_data is None:
        return None
    
    # 3. 时间戳相同 → 使用 MERGE
    if conflict.local_timestamp == conflict.remote_timestamp:
        return merge(conflict)
    
    return None
```

---

## 三、完整实现代码

**文件**：[src/offline/sync.py](file:///d:/trae/src/offline/sync.py)

```python
class SyncConflictResolver:
    """冲突解决器"""
    
    def resolve(self, conflict: SyncConflict) -> Optional[Dict]:
        """解决冲突"""
        # 检查预解决的冲突
        if conflict.id in self._resolved_conflicts:
            return self._apply_resolution(conflict, self._resolved_conflicts[conflict.id])
        
        # 根据策略解决
        strategy = conflict.strategy or self._default_strategy
        
        if strategy == ConflictStrategy.LAST_WRITE_WINS:
            return self._last_write_wins(conflict)
        elif strategy == ConflictStrategy.FIRST_WRITE_WINS:
            return self._first_write_wins(conflict)
        elif strategy == ConflictStrategy.MERGE:
            return self._merge(conflict)
        elif strategy == ConflictStrategy.MANUAL:
            return None
        
        return None
    
    def _last_write_wins(self, conflict: SyncConflict) -> Dict:
        """最后写入优先"""
        if conflict.remote_timestamp > conflict.local_timestamp:
            return conflict.remote_data
        return conflict.local_data
    
    def _merge(self, conflict: SyncConflict) -> Dict:
        """智能合并"""
        return self._deep_merge(conflict.local_data, conflict.remote_data)
    
    def _deep_merge(self, local: Dict, remote: Dict) -> Dict:
        """深层合并"""
        result = local.copy()
        for key, remote_value in remote.items():
            if key in result:
                local_value = result[key]
                if isinstance(local_value, dict) and isinstance(remote_value, dict):
                    result[key] = self._deep_merge(local_value, remote_value)
                elif isinstance(local_value, list) and isinstance(remote_value, list):
                    result[key] = self._merge_lists(local_value, remote_value)
                # 其他：本地优先
            else:
                result[key] = remote_value
        return result
```

---

## 四、测试覆盖

**测试文件**：[tests/test_offline_sync.py](file:///d:/trae/tests/test_offline_sync.py)

| 测试用例 | 策略 | 预期结果 |
|---------|------|---------|
| LWW 远程更新 | LAST_WRITE_WINS | 返回远程数据 |
| LWW 本地更新 | LAST_WRITE_WINS | 返回本地数据 |
| 合并字典 | MERGE | 深度合并 |
| 合并列表 | MERGE | 按 ID 去重 |
| FFW 本地先写 | FIRST_WRITE_WINS | 保留本地 |
| FFW 远程先写 | FIRST_WRITE_WINS | 保留远程 |

---

## 五、推荐配置

```python
# 默认策略：最后写入优先
resolver = SyncConflictResolver(
    default_strategy=ConflictStrategy.LAST_WRITE_WINS
)

# 历史记录：合并策略
resolver.register_strategy("history", ConflictStrategy.MERGE)

# 财务数据：手动解决
resolver.register_strategy("finance", ConflictStrategy.MANUAL)
```

---

**状态：✅ 已实现**
