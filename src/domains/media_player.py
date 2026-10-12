"""Matha 视频/音频播放器模块：媒体播放、播放控制、播放列表、均衡器。

覆盖：
  1) 视频播放
  2) 音频播放
  3) 播放控制（播放/暂停/停止/快进/快退）
  4) 播放列表
  5) 均衡器
  6) 字幕
  7) 播放器统计
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class PlayerState(Enum):
    """播放器状态。"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"
    ENDED = "ended"
    ERROR = "error"


class PlaybackSpeed(Enum):
    """播放速度。"""
    SPEED_025 = 0.25
    SPEED_050 = 0.50
    SPEED_075 = 0.75
    SPEED_100 = 1.00
    SPEED_125 = 1.25
    SPEED_150 = 1.50
    SPEED_200 = 2.00


class EqualizerBand(Enum):
    """均衡器频段。"""
    LOW = "low"
    MID_LOW = "mid_low"
    MID = "mid"
    MID_HIGH = "mid_high"
    HIGH = "high"


@dataclass
class PlaybackPosition:
    """播放位置。"""
    current_time: float = 0.0
    total_duration: float = 0.0
    percentage: float = 0.0
    buffered: float = 0.0

    @property
    def is_complete(self) -> bool:
        """是否播放完毕。"""
        return self.current_time >= self.total_duration


@dataclass
class TrackInfo:
    """音轨信息。"""
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    format: str = "mp3"
    bitrate: int = 320
    sample_rate: int = 44100
    channels: int = 2


@dataclass
class Subtitle:
    """字幕。"""
    text: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    language: str = "zh"


@dataclass
class PlayerStats:
    """播放器统计。"""
    state: str = "stopped"
    current_track: str = ""
    position: float = 0.0
    duration: float = 0.0
    volume: float = 1.0
    playback_speed: float = 1.0
    equalizer: dict[str, float] = field(default_factory=lambda: {
        "low": 0.0, "mid_low": 0.0, "mid": 0.0, "mid_high": 0.0, "high": 0.0
    })
    playlists_loaded: int = 0
    tracks_played: int = 0


class MediaPlayer:
    """媒体播放器：视频/音频播放。"""

    def __init__(self, volume: float = 1.0):
        self._state: PlayerState = PlayerState.STOPPED
        self._tracks: list[TrackInfo] = []
        self._current_track: TrackInfo | None = None
        self._position = PlaybackPosition()
        self._stats = PlayerStats()
        self._volume = max(0.0, min(1.0, volume))
        self._speed: float = 1.0
        self._playlists: list[list[TrackInfo]] = []
        self._equalizer: dict[str, float] = {
            "low": 0.0, "mid_low": 0.0, "mid": 0.0, "mid_high": 0.0, "high": 0.0
        }
        self._subtitles: list[Subtitle] = []
        self._start_time: float = 0.0
        self._paused_time: float = 0.0
        self._initialized: bool = False
        self._init_player()

    def _init_player(self) -> None:
        """初始化播放器。"""
        self._initialized = True

    def load_track(self, track: TrackInfo) -> bool:
        """加载音轨。"""
        self._current_track = track
        self._position.total_duration = track.duration
        self._position.current_time = 0.0
        self._state = PlayerState.STOPPED
        self._stats.current_track = track.title
        return True

    def play(self) -> bool:
        """播放。"""
        if self._current_track and self._state != PlayerState.PLAYING:
            self._state = PlayerState.PLAYING
            self._start_time = time.time() - self._paused_time
            return True
        return False

    def pause(self) -> bool:
        """暂停。"""
        if self._state == PlayerState.PLAYING:
            self._state = PlayerState.PAUSED
            self._paused_time = time.time() - self._start_time
            return True
        return False

    def stop(self) -> bool:
        """停止。"""
        if self._state != PlayerState.STOPPED:
            self._state = PlayerState.STOPPED
            self._position.current_time = 0.0
            self._paused_time = 0.0
            return True
        return False

    def seek(self, time_seconds: float) -> bool:
        """跳转。"""
        if self._current_track:
            self._position.current_time = max(0.0, min(time_seconds, self._current_track.duration))
            return True
        return False

    def set_volume(self, volume: float) -> bool:
        """设置音量。"""
        self._volume = max(0.0, min(1.0, volume))
        self._stats.volume = self._volume
        return True

    def set_speed(self, speed: float) -> bool:
        """设置播放速度。"""
        self._speed = max(0.25, min(2.0, speed))
        self._stats.playback_speed = self._speed
        return True

    def set_equalizer(self, band: str, gain: float) -> bool:
        """设置均衡器。"""
        if band in self._equalizer:
            self._equalizer[band] = gain
            self._stats.equalizer[band] = gain
            return True
        return False

    def add_subtitle(self, text: str, start: float, end: float,
                     language: str = "zh") -> bool:
        """添加字幕。"""
        sub = Subtitle(text=text, start_time=start, end_time=end, language=language)
        self._subtitles.append(sub)
        return True

    def get_stats(self) -> PlayerStats:
        """获取播放器统计。"""
        if self._state == PlayerState.PLAYING:
            elapsed = time.time() - self._start_time
            self._position.current_time = min(
                self._paused_time + elapsed, self._position.total_duration
            )
            self._stats.position = self._position.current_time
            self._stats.duration = self._position.total_duration
        self._stats.state = self._state.value
        self._stats.tracks_played += 1
        return self._stats

    def get_position(self) -> PlaybackPosition:
        """获取播放位置。"""
        self._position.percentage = (
            self._position.current_time / self._position.total_duration * 100
            if self._position.total_duration > 0 else 0.0
        )
        return self._position

    def create_playlist(self, name: str, tracks: list[TrackInfo] | None = None) -> list[TrackInfo]:
        """创建播放列表。"""
        playlist = tracks or []
        self._playlists.append(playlist)
        self._stats.playlists_loaded += 1
        return playlist

    def next_track(self) -> TrackInfo | None:
        """下一曲。"""
        return self._current_track

    def previous_track(self) -> TrackInfo | None:
        """上一曲。"""
        return self._current_track


def create_media_player() -> MediaPlayer:
    """创建媒体播放器。"""
    return MediaPlayer()


def create_track(title: str, duration: float = 180.0,
                  artist: str = "", format: str = "mp3") -> TrackInfo:
    """创建音轨。"""
    return TrackInfo(title=title, duration=duration, artist=artist, format=format)


def _register_player(builtins: dict) -> None:
    """注册播放器内置函数。"""
    builtins["创建媒体播放器"] = create_media_player
    builtins["创建音轨"] = lambda t, d=180.0, a="", f="mp3": create_track(t, d, a, f)
    builtins["加载音轨"] = lambda p, t: p.load_track(t)
    builtins["播放"] = lambda p: p.play()
    builtins["暂停"] = lambda p: p.pause()
    builtins["停止"] = lambda p: p.stop()
    builtins["跳转"] = lambda p, t: p.seek(t)
    builtins["设置音量"] = lambda p, v: p.set_volume(v)
    builtins["设置速度"] = lambda p, s: p.set_speed(s)
    builtins["设置均衡器"] = lambda p, b, g: p.set_equalizer(b, g)
    builtins["添加字幕"] = lambda p, t, s, e: p.add_subtitle(t, s, e)
    builtins["获取统计"] = lambda p: p.get_stats()
    builtins["获取位置"] = lambda p: p.get_position()
    builtins["创建播放列表"] = lambda p, n, tr=None: p.create_playlist(n, tr)
    builtins["下一曲"] = lambda p: p.next_track()
    builtins["上一曲"] = lambda p: p.previous_track()


def _player_symtab_names() -> list[str]:
    return [
        "创建媒体播放器", "创建音轨", "加载音轨",
        "播放", "暂停", "停止", "跳转",
        "设置音量", "设置速度", "设置均衡器",
        "添加字幕", "获取统计", "获取位置",
        "创建播放列表", "下一曲", "上一曲",
    ]


__all__ = [
    "PlayerState", "PlaybackSpeed", "EqualizerBand",
    "PlaybackPosition", "TrackInfo", "Subtitle", "PlayerStats",
    "MediaPlayer", "create_media_player", "create_track",
    "_register_player", "_player_symtab_names",
]
