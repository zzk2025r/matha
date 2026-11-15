"""Matha 音视频引擎：数据结构 + 播放器状态机。

能力边界（阶段 22a 假成功清算）：编解码、解复用、滤镜、
媒体加载、RTMP 连接需要真实编解码/网络后端，本模块未实现
——一律抛 NotImplementedError，不再返回截断字节 / 默认帧 /
空列表 / 假 True。纯状态面（参数设置、包缓冲、播放器
位置/音量）保持可用。
"""
from __future__ import annotations

import collections
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CodecType(Enum):
    H264 = "h264"
    H265 = "h265"
    AV1 = "av1"
    VP9 = "vp9"
    VP8 = "vp8"
    OPUS = "opus"
    AAC = "aac"
    MP3 = "mp3"
    VORBIS = "vorbis"
    FLAC = "flac"
    PCM = "pcm"


class MediaType(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    TEXT = "text"
    SUBTITLE = "subtitle"


class PixelFormat(Enum):
    YUV420P = "yuv420p"
    RGB24 = "rgb24"
    RGBA = "rgba"
    NV12 = "nv12"
    NV21 = "nv21"
    BGRA = "bgra"


@dataclass
class Frame:
    width: int = 1920
    height: int = 1080
    data: bytes = b""
    pts: float = 0.0
    duration: float = 0.0
    format: PixelFormat = PixelFormat.RGB24
    key_frame: bool = True
    codec: CodecType = CodecType.H264


@dataclass
class AudioFrame:
    samples: int = 44100
    channels: int = 2
    sample_rate: int = 44100
    data: bytes = b""
    pts: float = 0.0
    duration: float = 0.0
    codec: CodecType = CodecType.OPUS


@dataclass
class MediaPacket:
    data: bytes = b""
    pts: float = 0.0
    dts: float = 0.0
    duration: float = 0.0
    stream_index: int = 0
    is_key: bool = True
    type: MediaType = MediaType.VIDEO


@dataclass
class Stream:
    index: int = 0
    codec: CodecType = CodecType.H264
    width: int = 1920
    height: int = 1080
    duration: float = 0.0
    bitrate: int = 5000000
    fps: float = 30.0


class VideoEncoder:
    """视频编码器。"""

    def __init__(self, codec: CodecType = CodecType.H264,
                 width: int = 1920, height: int = 1080,
                 fps: float = 30.0, bitrate: int = 5000000):
        self.codec = codec
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self._frames_encoded = 0

    def encode(self, frame: Frame) -> bytes:
        raise NotImplementedError(
            f"视频编码 {self.codec.value} 需要编解码后端，未实现")

    def flush(self) -> bytes:
        return b""


class AudioEncoder:
    """音频编码器。"""

    def __init__(self, codec: CodecType = CodecType.OPUS,
                 sample_rate: int = 44100, channels: int = 2):
        self.codec = codec
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames_encoded = 0

    def encode(self, frame: AudioFrame) -> bytes:
        raise NotImplementedError(
            f"音频编码 {self.codec.value} 需要编解码后端，未实现")

    def flush(self) -> bytes:
        return b""


class VideoDecoder:
    """视频解码器。"""

    def __init__(self, codec: CodecType = CodecType.H264):
        self.codec = codec
        self._frames_decoded = 0

    def decode(self, packet: bytes) -> Frame:
        raise NotImplementedError(
            f"视频解码 {self.codec.value} 需要编解码后端，未实现")


class AudioDecoder:
    """音频解码器。"""

    def __init__(self, codec: CodecType = CodecType.OPUS):
        self.codec = codec
        self._frames_decoded = 0

    def decode(self, packet: bytes) -> AudioFrame:
        raise NotImplementedError(
            f"音频解码 {self.codec.value} 需要编解码后端，未实现")


class StreamMuxer:
    """复用器。"""

    def __init__(self, container: str = "mp4"):
        self.container = container
        self._streams: list[Stream] = []
        self._packets: list[MediaPacket] = []

    def add_stream(self, stream: Stream) -> None:
        self._streams.append(stream)

    def write(self, packet: MediaPacket) -> None:
        self._packets.append(packet)

    def finalize(self) -> bytes:
        raise NotImplementedError(
            f"容器 {self.container} 封装需要编解码后端，未实现")


class StreamDemuxer:
    """解复用器。"""

    def __init__(self, container: str = "mp4"):
        self.container = container
        self._streams: list[Stream] = []
        self._packets: list[MediaPacket] = []

    def read(self, data: bytes) -> list[MediaPacket]:
        raise NotImplementedError(
            f"容器 {self.container} 解封装需要编解码后端，未实现")


class Filter:
    """视频滤镜。"""

    def __init__(self, name: str = "scale"):
        self.name = name
        self._params: dict[str, Any] = {}

    def apply(self, frame: Frame) -> Frame:
        raise NotImplementedError(
            f"滤镜 {self.name} 需要渲染管线，未实现")

    def set_param(self, key: str, value: Any) -> None:
        self._params[key] = value


class FilterGraph:
    """滤镜图。"""

    def __init__(self):
        self._filters: list[Filter] = []

    def add_filter(self, filter: Filter) -> None:
        self._filters.append(filter)

    def apply(self, frame: Frame) -> Frame:
        if not self._filters:
            return frame
        raise NotImplementedError("滤镜图应用需要渲染管线，未实现")


class MediaPlayer:
    """媒体播放器。"""

    def __init__(self):
        self._playing = False
        self._paused = False
        self._position = 0.0
        self._duration = 0.0
        self._volume = 1.0
        self._muted = False
        self._video_stream: Stream | None = None
        self._audio_stream: Stream | None = None

    def load(self, path: str) -> bool:
        raise NotImplementedError("媒体文件加载需要解复用后端，未实现")

    def play(self) -> None:
        self._playing = True
        self._paused = False

    def pause(self) -> None:
        self._paused = True

    def stop(self) -> None:
        self._playing = False
        self._paused = False
        self._position = 0.0

    def seek(self, position: float) -> None:
        self._position = position

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))

    def get_position(self) -> float:
        return self._position

    def get_duration(self) -> float:
        return self._duration


class RTMPStreamer:
    """RTMP 流媒体推送。"""

    def __init__(self, url: str = "rtmp://localhost/live"):
        self.url = url
        self._connected = False
        self._stream_key: str | None = None
        self._backend: Any = None
        self._buffer: collections.deque = collections.deque(maxlen=120)
        self._frame_count = 0
        self._bytes_out = 0
        self._lock = threading.Lock()

    def connect(self) -> bool:
        raise NotImplementedError(
            "RTMP 连接需要网络后端，未实现（push_frame 的未连接守卫保持诚实拒绝）")

    def publish(self, stream_key: str) -> None:
        self._stream_key = stream_key

    def push_frame(self, frame: bytes) -> None:
        if not self._connected:
            raise RuntimeError("RTMP 流未连接，请先调用 connect()")
        with self._lock:
            self._buffer.append(frame)
            if self._backend is not None:
                self._backend.sendall(frame)
            self._frame_count += 1
            self._bytes_out += len(frame)

    def flush(self) -> None:
        with self._lock:
            while self._buffer:
                item = self._buffer.popleft()
                if self._backend is not None:
                    self._backend.sendall(item)

    def buffer_size(self) -> int:
        return len(self._buffer)

    def disconnect(self) -> None:
        self._connected = False
        self._backend = None
        self._buffer.clear()


def create_video_encoder(codec: CodecType = CodecType.H264,
                            width: int = 1920, height: int = 1080
                            ) -> VideoEncoder:
    return VideoEncoder(codec=codec, width=width, height=height)


def create_audio_encoder(codec: CodecType = CodecType.OPUS,
                            sample_rate: int = 44100
                            ) -> AudioEncoder:
    return AudioEncoder(codec=codec, sample_rate=sample_rate)


def create_video_decoder(codec: CodecType = CodecType.H264
                            ) -> VideoDecoder:
    return VideoDecoder(codec=codec)


def create_audio_decoder(codec: CodecType = CodecType.OPUS
                            ) -> AudioDecoder:
    return AudioDecoder(codec=codec)


def create_filter_graph() -> FilterGraph:
    return FilterGraph()


def create_media_player() -> MediaPlayer:
    return MediaPlayer()


def create_rtmp_streamer(url: str = "rtmp://localhost/live"
                              ) -> RTMPStreamer:
    return RTMPStreamer(url=url)


# ============================================================
# 内置注册
# ============================================================

def _register_audio_video(builtins: dict) -> None:
    builtins["创建视频编码器"] = create_video_encoder
    builtins["创建音频编码器"] = create_audio_encoder
    builtins["创建视频解码器"] = create_video_decoder
    builtins["创建音频解码器"] = create_audio_decoder
    builtins["创建滤镜图"] = create_filter_graph
    builtins["创建媒体播放器"] = create_media_player
    builtins["创建RTMP流媒体"] = create_rtmp_streamer


def _audio_video_names() -> list[str]:
    return ["创建视频编码器", "创建音频编码器",
            "创建视频解码器", "创建音频解码器",
            "创建滤镜图", "创建媒体播放器",
            "创建RTMP流媒体"]


__all__ = [
    "CodecType", "MediaType", "PixelFormat",
    "Frame", "AudioFrame", "MediaPacket", "Stream",
    "VideoEncoder", "AudioEncoder", "VideoDecoder",
    "AudioDecoder", "StreamMuxer", "StreamDemuxer",
    "Filter", "FilterGraph", "MediaPlayer", "RTMPStreamer",
    "create_video_encoder", "create_audio_encoder",
    "create_video_decoder", "create_audio_decoder",
    "create_filter_graph", "create_media_player",
    "create_rtmp_streamer",
    "_register_audio_video", "_audio_video_names",
]
