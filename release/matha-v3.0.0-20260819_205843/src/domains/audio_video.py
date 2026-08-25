# -*- coding: utf-8 -*-
"""Matha 音视频处理领域模块：音频采样、视频编码、流媒体、编解码。

覆盖：
  1) 音频采样率转换
  2) 视频码率估算
  3) 流媒体延迟
  4) 编解码压缩比
  5) 音频信噪比
  6) 视频帧率
"""

from __future__ import annotations
import math


def _curry1(func):
    def with_first(a): return func(a)
    return with_first

def _curry2(func):
    def with_first(a): return lambda b: func(a, b)
    return with_first

def _curry3(func):
    def w1(a):
        def w2(b): return lambda c: func(a, b, c)
        return w2
    return w1

def _curry4(func):
    def w1(a):
        def w2(b):
            def w3(c): return lambda d: func(a, b, c, d)
            return w3
        return w2
    return w1


def _音频采样率转换(源采样率, 目标采样率, 声道数):
    """采样率转换后数据量（字节/秒）。"""
    if 源采样率 <= 0 or 目标采样率 <= 0:
        return 0.0
    return 目标采样率 * 2 * 声道数  # 16bit


def _视频码率估算(分辨率_w, 分辨率_h, 帧率, 压缩率):
    """视频码率估算（Mbps）。"""
    if 帧率 <= 0 or 压缩率 <= 0:
        return 0.0
    像素 = 分辨率_w * 分辨率_h * 帧率 * 24 / 8  # 24bit/pixel
    return 像素 * 压缩率 / 1e6


def _流媒体延迟(缓冲秒数, 网络延迟_ms, 编码延迟_ms):
    """流媒体总延迟。"""
    return 缓冲秒数 * 1000 + 网络延迟_ms + 编码延迟_ms


def _编解码压缩比(原始大小_MB, 压缩后大小_MB):
    """压缩比。"""
    if 压缩后大小_MB <= 0:
        return 0.0
    return 原始大小_MB / 压缩后大小_MB


def _音频信噪比(信号功率, 噪声功率):
    """音频信噪比（dB）。"""
    if 噪声功率 <= 0:
        return float('inf')
    return 10 * math.log10(信号功率 / 噪声功率)


def _视频帧率稳定性(目标帧率, 实际帧率_list):
    """帧率稳定性指数。"""
    if not 实际帧率_list or 目标帧率 <= 0:
        return 0.0
    偏差 = sum(abs(f - 目标帧率) for f in 实际帧率_list) / len(实际帧率_list)
    return max(0.0, 1 - 偏差 / 目标帧率) * 100


# ============================================================
# 注册
# ============================================================

def _register_audio_video(builtins: dict) -> None:
    builtins["音频采样率转换"] = _curry3(_音频采样率转换)
    builtins["视频码率估算"] = _curry4(_视频码率估算)
    builtins["流媒体延迟"] = _curry3(_流媒体延迟)
    builtins["编解码压缩比"] = _curry2(_编解码压缩比)
    builtins["音频信噪比"] = _curry2(_音频信噪比)
    builtins["视频帧率稳定性"] = _curry2(_视频帧率稳定性)


def _audio_video_symtab_names() -> list[str]:
    return ["音频采样率转换", "视频码率估算", "流媒体延迟",
            "编解码压缩比", "音频信噪比", "视频帧率稳定性"]


__all__ = [
    "音频采样率转换", "视频码率估算", "流媒体延迟",
    "编解码压缩比", "音频信噪比", "视频帧率稳定性",
    "_register_audio_video", "_audio_video_symtab_names",
]
