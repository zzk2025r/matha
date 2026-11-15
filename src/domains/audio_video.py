"""Matha 音视频处理模块（阶段 22a 诚实化）。

能力边界（诚实口径）：
  - 音频面真实现：generate_tone 生成真实正弦 PCM（16bit 单声道 44100Hz）、
    mix 按样本求和（int16 饱和钳位）、export 经标准库 wave 写出真实 WAV 文件；
    非 wav 格式（mp3 等）需要编码器，离线环境显式拒绝，不再假装导出成功。
  - 视频面诚实降格：load 真实读取文件字节；剪辑/合并/特效/渲染需要编解码与
    渲染管线，本模块未实现——一律抛 NotImplementedError，不再返回假 True。
"""
from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

SAMPLE_RATE = 44100


class AudioFormat(Enum):
    """音频格式。"""
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    AAC = "aac"
    OGG = "ogg"


class VideoFormat(Enum):
    """视频格式。"""
    MP4 = "mp4"
    AVI = "avi"
    MKV = "mkv"
    WEBM = "webm"
    MOV = "mov"


@dataclass
class AudioClip:
    """音频片段（data = 16bit 单声道 PCM 小端样本）。"""
    name: str = ""
    duration: float = 0.0
    sample_rate: int = SAMPLE_RATE
    channels: int = 1
    format: str = "wav"
    data: bytes = b""


@dataclass
class VideoClip:
    """视频片段（data = 原始文件字节；时长未知，未解码）。"""
    name: str = ""
    duration: float = 0.0
    width: int = 1920
    height: int = 1080
    fps: int = 30
    format: str = "mp4"
    data: bytes = b""


@dataclass
class Effect:
    """特效登记条目。"""
    name: str = ""
    type: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


def _samples(clip: AudioClip) -> list[int]:
    if not clip.data:
        return []
    n = len(clip.data) // 2
    return list(struct.unpack(f"<{n}h", clip.data[: n * 2]))


def _pack(samples: list[int]) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


class AudioEngine:
    """音频引擎：音调合成、混音、WAV 导出（全部真实样本/真实落盘）。"""

    def __init__(self):
        self._clips: list[AudioClip] = []
        self._effects: list[Effect] = []

    def generate_tone(self, frequency: float, duration: float,
                      volume: float = 1.0) -> AudioClip:
        """生成正弦音调：真实 PCM 样本（44100Hz 16bit 单声道）。"""
        n = int(SAMPLE_RATE * duration)
        amp = max(0.0, min(1.0, volume)) * 32767
        samples = [int(amp * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE))
                   for i in range(n)]
        clip = AudioClip(name=f"tone_{frequency}hz", duration=duration,
                         data=_pack(samples))
        self._clips.append(clip)
        return clip

    def add_effect(self, name: str, effect_type: str,
                   params: dict[str, Any] = None) -> Effect:
        """登记特效条目（仅登记；应用到样本属 DSP 管线，未实现）。"""
        effect = Effect(name=name, type=effect_type, parameters=params or {})
        self._effects.append(effect)
        return effect

    def mix(self, clips: list[AudioClip]) -> AudioClip:
        """混音：按样本求和，int16 饱和钳位（空片段按静音处理）。"""
        if not clips:
            raise ValueError("混音需要至少一个音频片段")
        tracks = [_samples(c) for c in clips]
        length = max((len(t) for t in tracks), default=0)
        mixed: list[int] = []
        for i in range(length):
            s = sum(t[i] for t in tracks if i < len(t))
            mixed.append(max(-32768, min(32767, s)))
        out = AudioClip(name="mixed", duration=length / SAMPLE_RATE,
                        data=_pack(mixed))
        self._clips.append(out)
        return out

    def export(self, clip: AudioClip, format: str = "wav") -> bool:
        """导出为真实 WAV 文件（clip.data 为空时诚实报错）。

        返回值 = 文件是否成功写出。format 仅支持 wav；mp3/flac/aac/ogg
        需要编码器，离线环境未实现，显式抛 NotImplementedError。
        """
        fmt = format.lower()
        if fmt != "wav":
            raise NotImplementedError(
                f"音频导出格式 {format} 需要编码器，离线环境未实现（支持 wav）")
        if not clip.data:
            raise ValueError(f"音频片段 {clip.name!r} 无样本数据，拒绝导出空文件")
        with wave.open(clip.name or "clip.wav", "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(clip.sample_rate)
            w.writeframes(clip.data)
        clip.format = "wav"
        return True


class VideoEditor:
    """视频编辑器（诚实降格）：仅 load 真实读取文件字节。

    剪辑 / 合并 / 特效 / 渲染需要编解码与渲染管线，未实现——显式拒绝，
    不再返回假成功。
    """

    def __init__(self):
        self._clips: list[VideoClip] = []

    def load(self, path: str) -> VideoClip:
        """加载视频文件字节（真实读取；文件不存在自然抛 FileNotFoundError）。"""
        p = Path(path)
        clip = VideoClip(name=str(p), format=p.suffix.lstrip(".").lower() or "mp4",
                         data=p.read_bytes())
        self._clips.append(clip)
        return clip

    def cut(self, clip: VideoClip, start: float, end: float) -> VideoClip:
        raise NotImplementedError("视频剪辑需要编解码支持，未实现")

    def add_effect(self, clip: VideoClip, effect: str,
                   params: dict[str, Any] = None) -> bool:
        raise NotImplementedError("视频特效需要渲染管线支持，未实现")

    def render(self, clip: VideoClip, format: str = "mp4") -> bool:
        raise NotImplementedError("视频渲染需要编解码与渲染管线支持，未实现")

    def merge(self, clips: list[VideoClip]) -> VideoClip:
        raise NotImplementedError("视频合并需要编解码支持，未实现")


def create_audio_engine() -> AudioEngine:
    """创建音频引擎。"""
    return AudioEngine()


def create_video_editor() -> VideoEditor:
    """创建视频编辑器。"""
    return VideoEditor()


def _register_av(builtins: dict) -> None:
    """注册音视频内置函数。"""
    builtins["创建音频引擎"] = create_audio_engine
    builtins["创建视频编辑器"] = create_video_editor
    builtins["生成音调"] = lambda f, d, v=1.0: AudioEngine().generate_tone(f, d, v)
    builtins["添加特效"] = lambda ae, n, t, p=None: ae.add_effect(n, t, p)
    builtins["混音"] = lambda ae, c: ae.mix(c)
    builtins["加载视频"] = lambda ve, p: ve.load(p)
    builtins["剪辑视频"] = lambda ve, c, s, e: ve.cut(c, s, e)
    builtins["渲染视频"] = lambda ve, c, f="mp4": ve.render(c, f)
    builtins["合并视频"] = lambda ve, c: ve.merge(c)
    builtins["导出音频"] = lambda ae, c, f="wav": ae.export(c, f)


def _av_symtab_names() -> list[str]:
    return [
        "创建音频引擎", "创建视频编辑器",
        "生成音调", "添加特效", "混音", "导出音频",
        "加载视频", "剪辑视频", "渲染视频", "合并视频",
    ]


__all__ = [
    "AudioFormat", "VideoFormat", "AudioClip", "VideoClip",
    "Effect", "AudioEngine", "VideoEditor",
    "create_audio_engine", "create_video_editor",
    "_register_av", "_av_symtab_names",
]
