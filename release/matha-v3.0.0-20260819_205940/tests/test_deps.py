# -*- coding: utf-8 -*-
"""Matha 自举依赖层测试。

验证：
  1. 无第三方依赖可正常运行
  2. 所有 standalone 功能完整可用
  3. 可选依赖自动检测与降级
  4. 缓存、序列化、日志、IO 工具正确工作
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.deps import (
    get_platform, get_arch, get_python_version, is_portable_env,
    LRUCache, TTLCache,
    to_json, from_json, to_json_pretty,
    to_pickle, from_pickle, to_b64, from_b64, hash_obj,
    fast_json_dumps, fast_json_loads,
    compress_data, decompress_data,
    MathaLogger,
    safe_read_text, safe_write_text, safe_append_text,
    ensure_dir, list_files, file_age_seconds, atomic_write,
    timing, benchmark, get_dependency_status,
    serialize_for_storage, deserialize_from_storage,
)

passed = 0
failed = 0

def check(name, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print(f"  ✓ {name}: {actual}")
    else:
        failed += 1
        print(f"  ✗ {name}: 期望 {expected}, 实际 {actual}")

def check_approx(name, actual, expected, tol=1e-6):
    global passed, failed
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if abs(actual - expected) < tol:
            passed += 1
            print(f"  ✓ {name}: {actual}")
        else:
            failed += 1
            print(f"  ✗ {name}: 期望 {expected}, 实际 {actual}")
    else:
        check(name, actual, expected)

def check_type(name, actual, expected_type):
    global passed, failed
    if isinstance(actual, expected_type):
        passed += 1
        print(f"  ✓ {name}: {type(actual).__name__}")
    else:
        failed += 1
        print(f"  ✗ {name}: 期望 {expected_type.__name__}, 实际 {type(actual).__name__}")

print("=" * 60)
print("Matha 依赖层测试")
print("=" * 60)

# ============================================================
# 1. 平台检测
# ============================================================
print("\n=== 1. 平台检测 ===")
check_type("平台类型", get_platform(), str)
check_type("架构类型", get_arch(), str)
v = get_python_version()
check("Python版本", v[0] >= 3, True)
check("便携模式", isinstance(is_portable_env(), bool), True)

# ============================================================
# 2. LRU 缓存
# ============================================================
print("\n=== 2. LRU 缓存 ===")
cache = LRUCache(maxsize=3)
cache.put("a", 1)
cache.put("b", 2)
cache.put("c", 3)
check("缓存get", cache.get("a"), 1)
check("缓存miss", cache.get("z"), None)
check("缓存大小", cache.size, 3)
cache.put("d", 4)  # 溢出
check("溢出后大小", cache.size, 3)
check("溢出旧值", cache.get("b"), None)  # LRU: 最近使用b, a次之, c最近; d进去后a最先被踢
stats = cache.stats
check("命中率类型", isinstance(stats["hit_rate"], float), True)
cache.clear()
check("清空后大小", cache.size, 0)

# ============================================================
# 3. TTL 缓存
# ============================================================
print("\n=== 3. TTL 缓存 ===")
ttl = TTLCache(default_ttl=0.1, maxsize=10)
ttl.put("key", "value")
check("TTL get", ttl.get("key"), "value")
# 短 TTL 过期测试
ttl.put("exp", "data", ttl=0.01)
import time
time.sleep(0.05)
check("TTL过期", ttl.get("exp"), None)
ttl.clear()
check("TTL清空", ttl.get("key"), None)

# ============================================================
# 4. JSON 序列化
# ============================================================
print("\n=== 4. JSON 序列化 ===")
data = {"name": "Matha", "值": 42, "列表": [1, 2, 3], "嵌套": {"a": True}}
json_str = to_json(data)
check_type("to_json类型", json_str, str)
restored = from_json(json_str)
check("roundtrip", restored["name"], "Matha")
check("roundtrip值", restored["值"], 42)
check("roundtrip列表", restored["列表"], [1, 2, 3])
check("roundtrip嵌套", restored["嵌套"], {"a": True})
pretty = to_json_pretty(data)
check("pretty含缩进", "  " in pretty, True)

# ============================================================
# 5. Pickle 序列化
# ============================================================
print("\n=== 5. Pickle 序列化 ===")
pickled = to_pickle(data)
check_type("to_pickle类型", pickled, bytes)
restored = from_pickle(pickled)
check("pickle roundtrip", restored["name"], "Matha")

# ============================================================
# 6. Base64 序列化
# ============================================================
print("\n=== 6. Base64 序列化 ===")
b64 = to_b64(data)
check_type("to_b64类型", b64, str)
restored = from_b64(b64)
check("b64 roundtrip", restored["值"], 42)

# ============================================================
# 7. 哈希
# ============================================================
print("\n=== 7. 哈希 ===")
h1 = hash_obj(data)
h2 = hash_obj(data)
h3 = hash_obj({"different": True})
check("哈希一致性", h1 == h2, True)
check("哈希不同", h1 != h3, True)
check_type("哈希类型", h1, str)
check("哈希长度", len(h1), 16)

# ============================================================
# 8. 快速 JSON（降级测试）
# ============================================================
print("\n=== 8. 快速 JSON ===")
fast_str = fast_json_dumps(data)
fast_obj = fast_json_loads(fast_str)
check("fast_json roundtrip", fast_obj["name"], "Matha")

# ============================================================
# 9. 压缩
# ============================================================
print("\n=== 9. 压缩 ===")
raw = b"Hello Matha " * 1000
compressed = compress_data(raw)
decompressed = decompress_data(compressed)
check("压缩 roundtrip", decompressed, raw)
check("压缩有效", len(compressed) < len(raw), True)

# ============================================================
# 10. 存储序列化
# ============================================================
print("\n=== 10. 存储序列化 ===")
storage_data = serialize_for_storage({"key": "value", "nums": list(range(100))})
check_type("存储序列化类型", storage_data, bytes)
restored = deserialize_from_storage(storage_data)
check("存储 roundtrip", restored["key"], "value")

# ============================================================
# 11. 日志
# ============================================================
print("\n=== 11. 日志 ===")
log = MathaLogger("test")
check_type("日志器类型", log, MathaLogger)
check("is_debug初始", log.is_debug, False)
log.set_level(10)  # DEBUG
check("is_debug启用", log.is_debug, True)

# ============================================================
# 12. IO 工具
# ============================================================
print("\n=== 12. IO 工具 ===")
with tempfile.TemporaryDirectory() as tmpdir:
    test_file = os.path.join(tmpdir, "sub", "test.txt")
    safe_write_text(test_file, "Hello Matha")
    check("写文件", safe_read_text(test_file), "Hello Matha")
    safe_append_text(test_file, " World")
    check("追加文件", safe_read_text(test_file), "Hello Matha World")

    # 目录创建
    new_dir = os.path.join(tmpdir, "a", "b", "c")
    ensure_dir(new_dir)
    check("目录创建", os.path.isdir(new_dir), True)

    # 列出文件
    safe_write_text(os.path.join(tmpdir, "x.txt"), "1")
    safe_write_text(os.path.join(tmpdir, "y.txt"), "2")
    files = list_files(tmpdir, "*.txt")
    check("列出文件", len(files), 2)  # x.txt + y.txt（test.txt 已验证可读写，不重复计数）

    # 文件年龄
    age = file_age_seconds(test_file)
    check_approx("文件年龄", age, 0, tol=5.0)

    # 原子写入
    atomic_file = os.path.join(tmpdir, "atomic.txt")
    atomic_write(atomic_file, "atomic content")
    check("原子写入", safe_read_text(atomic_file), "atomic content")

# ============================================================
# 13. 性能计时
# ============================================================
print("\n=== 13. 性能计时 ===")
result, elapsed = timing(lambda x: x * 2, 21)
check("timing结果", result, 42)
check("timing耗时", elapsed >= 0, True)

bench = benchmark(lambda: sum(range(100)), iterations=100)
check("benchmark结果", bench["结果"], sum(range(100)))
check_type("benchmark耗时", bench["总耗时_ms"], float)

# ============================================================
# 14. 依赖报告
# ============================================================
print("\n=== 14. 依赖报告 ===")
report = get_dependency_status()
check_type("报告平台", report["平台"], str)
check_type("报告架构", report["架构"], str)
check_type("报告Python", report["Python"], str)
check_type("报告便携", report["便携模式"], bool)
check_type("报告可选", report["可选依赖"], dict)
print(f"  ○ 可选依赖状态: {report['可选依赖']}")

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print(f"测试结果：{passed} 通过, {failed} 失败 (共 {passed + failed})")
print("=" * 60)

if failed > 0:
    sys.exit(1)
