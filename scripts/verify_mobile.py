# -*- coding: utf-8 -*-
"""
修复移动端 API 的 zeros 调用问题
"""
import sys
sys.path.insert(0, r"D:\trae")

from src.mobile_full import MobileAPI, MobileConfig, FlutterShell, is_mobile, get_mobile_state

print("=== 移动端测试 ===")
print(f"is_mobile: {is_mobile()}")
print(f"state: {get_mobile_state()}")

api = MobileAPI(MobileConfig(memory_limit_mb=128))
# 测试 zeros - 传入 tuple
result = api.zeros((3, 3))
print(f"zeros((3,3)): {type(result).__name__}, shape={result.shape if hasattr(result, 'shape') else 'N/A'}")

result = api.eye(3)
print(f"eye(3): {type(result).__name__}")

# Flutter 协议
init = FlutterShell.create_init_message("Matha", "4.4.0")
print(f"Flutter init: {init['type']}")

print("\n=== 全部通过 ===")
