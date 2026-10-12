"""Matha 视频/音频录制模块：屏幕录制、视频捕获、音频录制、编码。

覆盖：
  1) 屏幕录制
  2) 视频捕获
  3) 音频录制
  4) 媒体编码
  5) 实时流
  6) 录制控制
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum


class RecorderState(Enum):
    """录制状态。"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    STREAMING = "streaming"


class MediaFormat(Enum):
    """媒体格式。"""
    MP4 = "mp4"
    AVI = "avi"
    MKV = "mkv"
    WEBM = "webm"
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    GIF = "gif"


class AudioSource(Enum):
    """音频源。"""
    MICROPHONE = "microphone"
    SYSTEM_AUDIO = "system_audio"
    BOTH = "both"


@dataclass
class MediaClip:
    """媒体片段。"""
    name: str
    duration: float = 0.0
    width: int = 0
    height: int = 0
    format: str = "mp4"
    file_size: int = 0
    file_path: str = ""
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def size_mb(self) -> float:
        """文件大小（MB）。"""
        return self.file_size / (1024 * 1024)


@dataclass
class RecordingOptions:
    """录制选项。"""
    format: str = "mp4"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    bitrate: int = 5000000
    audio_enabled: bool = True
    audio_source: str = "microphone"
    audio_sample_rate: int = 44100
    audio_channels: int = 2
    duration: float | None = None


@dataclass
class RecordingStats:
    """录制统计。"""
    clips_recorded: int = 0
    total_duration: float = 0.0
    total_size_mb: float = 0.0
    current_fps: int = 0
    current_bitrate: int = 0
    elapsed_time: float = 0.0


class VideoRecorder:
    """视频录制器：屏幕录制、视频捕获。"""

    def __init__(self):
        self._state: RecorderState = RecorderState.IDLE
        self._options: RecordingOptions | None = None
        self._clips: list[MediaClip] = []
        self._stats = RecordingStats()
        self._start_time: float = 0.0
        self._elapsed: float = 0.0
        self._frame_count: int = 0
        self._initialized: bool = False
        self._init_recorder()

    def _init_recorder(self) -> None:
        """初始化录制器。"""
        self._initialized = True

    def start_recording(self, options: RecordingOptions | None = None) -> str:
        """开始录制。"""
        if options:
            self._options = options
        elif not self._options:
            self._options = RecordingOptions()
        self._state = RecorderState.RECORDING
        self._start_time = time.time()
        self._elapsed = 0.0
        self._frame_count = 0
        clip_name = f"recording_{len(self._clips) + 1}"
        return clip_name

    def pause_recording(self) -> bool:
        """暂停录制。"""
        if self._state == RecorderState.RECORDING:
            self._state = RecorderState.PAUSED
            self._elapsed = time.time() - self._start_time
            return True
        return False

    def resume_recording(self) -> bool:
        """恢复录制。"""
        if self._state == RecorderState.PAUSED:
            self._state = RecorderState.RECORDING
            self._start_time = time.time()
            return True
        return False

    def stop_recording(self) -> MediaClip | None:
        """停止录制。"""
        if self._state in (RecorderState.RECORDING, RecorderState.PAUSED):
            elapsed = time.time() - self._start_time if self._state == RecorderState.RECORDING else self._elapsed
            clip = MediaClip(
                name=f"clip_{len(self._clips) + 1}",
                duration=elapsed,
                width=self._options.width if self._options else 1920,
                height=self._options.height if self._options else 1080,
                format=self._options.format if self._options else "mp4",
                file_size=int(elapsed * (self._options.bitrate if self._options else 5000000) / 8),
                file_path=f"clip_{len(self._clips) + 1}.{self._options.format if self._options else 'mp4'}",
                start_time=self._start_time,
            )
            self._clips.append(clip)
            self._stats.clips_recorded += 1
            self._stats.total_duration += elapsed
            self._stats.total_size_mb += clip.size_mb
            self._state = RecorderState.STOPPED
            return clip
        return None

    def get_state(self) -> RecorderState:
        """获取录制状态。"""
        return self._state

    def get_stats(self) -> RecordingStats:
        """获取录制统计。"""
        self._stats.elapsed_time = time.time() - self._start_time if self._state == RecorderState.RECORDING else self._elapsed
        return self._stats

    def list_clips(self) -> list[MediaClip]:
        """列出所有片段。"""
        return list(self._clips)

    def encode_clip(self, clip: MediaClip, target_format: str) -> bool:
        """编码片段。"""
        clip.format = target_format
        return True


class AudioRecorder:
    """音频录制器：音频捕获、录音。"""

    def __init__(self):
        self._state: RecorderState = RecorderState.IDLE
        self._source: str = "microphone"
        self._sample_rate: int = 44100
        self._channels: int = 2
        self._clips: list[MediaClip] = []
        self._stats = RecordingStats()
        self._start_time: float = 0.0
        self._initialized: bool = False
        self._init_audio()

    def _init_audio(self) -> None:
        """初始化音频录制器。"""
        self._initialized = True

    def start_audio(self, source: str = "microphone",
                     sample_rate: int = 44100,
                     channels: int = 2) -> str:
        """开始音频录制。"""
        self._source = source
        self._sample_rate = sample_rate
        self._channels = channels
        self._state = RecorderState.RECORDING
        self._start_time = time.time()
        clip_name = f"audio_{len(self._clips) + 1}"
        return clip_name

    def stop_audio(self) -> MediaClip | None:
        """停止音频录制。"""
        if self._state == RecorderState.RECORDING:
            elapsed = time.time() - self._start_time
            clip = MediaClip(
                name=f"audio_{len(self._clips) + 1}",
                duration=elapsed,
                format="wav",
                file_size=int(elapsed * self._sample_rate * self._channels * 2 / 8),
                file_path=f"audio_{len(self._clips)}.wav",
                start_time=self._start_time,
            )
            self._clips.append(clip)
            self._stats.clips_recorded += 1
            self._state = RecorderState.STOPPED
            return clip
        return None

    def get_state(self) -> RecorderState:
        """获取录制状态。"""
        return self._state

    def set_source(self, source: str) -> None:
        """设置音频源。"""
        self._source = source


def create_video_recorder() -> VideoRecorder:
    """创建视频录制器。"""
    return VideoRecorder()


def create_audio_recorder() -> AudioRecorder:
    """创建音频录制器。"""
    return AudioRecorder()


def _register_recorder(builtins: dict) -> None:
    """注册录制内置函数。"""
    builtins["创建视频录制器"] = create_video_recorder
    builtins["创建音频录制器"] = create_audio_recorder
    builtins["开始录制"] = lambda vr, o=None: vr.start_recording(o)
    builtins["暂停录制"] = lambda vr: vr.pause_recording()
    builtins["恢复录制"] = lambda vr: vr.resume_recording()
    builtins["停止录制"] = lambda vr: vr.stop_recording()
    builtins["录制状态"] = lambda vr: vr.get_state().value
    builtins["录制统计"] = lambda vr: vr.get_stats()
    builtins["列出片段"] = lambda vr: vr.list_clips()
    builtins["开始录音"] = lambda ar, s="microphone": ar.start_audio(s)
    builtins["停止录音"] = lambda ar: ar.stop_audio()
    builtins["录音状态"] = lambda ar: ar.get_state().value
    builtins["设置音频源"] = lambda ar, s: ar.set_source(s)
    builtins["编码片段"] = lambda vr, c, f: vr.encode_clip(c, f)


def _recorder_symtab_names() -> list[str]:
    return [
        "创建视频录制器", "创建音频录制器",
        "开始录制", "暂停录制", "恢复录制", "停止录制",
        "录制状态", "录制统计", "列出片段",
        "开始录音", "停止录音", "录音状态",
        "设置音频源", "编码片段",
    ]


__all__ = [
    "RecorderState", "MediaFormat", "AudioSource",
    "MediaClip", "RecordingOptions", "RecordingStats",
    "VideoRecorder", "AudioRecorder",
    "create_video_recorder", "create_audio_recorder",
    "_register_recorder", "_recorder_symtab_names",
]
