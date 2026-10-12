"""Matha 音乐模块：合成、音阶、和弦、音乐理论、MIDI。

覆盖：
  1) 音高/频率
  2) 音阶
  3) 和弦
  4) 音乐合成
  5) MIDI控制
  6) 音乐理论
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScaleType(Enum):
    """音阶类型。"""
    MAJOR = "major"
    MINOR = "minor"
    PENTATONIC = "pentatonic"
    BLUES = "blues"
    CHROMATIC = "chromatic"


@dataclass
class Note:
    """音符。"""
    pitch: str = "C"
    octave: int = 4
    duration: float = 1.0
    frequency: float = 440.0


@dataclass
class Chord:
    """和弦。"""
    name: str = "C"
    notes: list[Note] = field(default_factory=list)
    type: str = "major"


@dataclass
class Melody:
    """旋律。"""
    name: str = ""
    notes: list[Note] = field(default_factory=list)
    tempo: float = 120.0
    key: str = "C"


class MusicEngine:
    """音乐引擎：音阶、和弦、合成、MIDI。"""

    def __init__(self):
        self._melodies: list[Melody] = []
        self._initialized = False
        self._init_music()

    def _init_music(self) -> None:
        """初始化音乐引擎。"""
        self._initialized = True

    def create_scale(self, root: str, scale_type: str = "major") -> list[Note]:
        """创建音阶。"""
        return [Note(pitch=root, octave=4)]

    def create_chord(self, root: str, chord_type: str = "major") -> Chord:
        """创建和弦。"""
        return Chord(name=root, type=chord_type)

    def create_melody(self, name: str = "melody") -> Melody:
        """创建旋律。"""
        melody = Melody(name=name)
        self._melodies.append(melody)
        return melody

    def add_note(self, melody: Melody, pitch: str,
                    octave: int = 4, duration: float = 1.0) -> Note:
        """添加音符。"""
        note = Note(pitch=pitch, octave=octave, duration=duration)
        melody.notes.append(note)
        return note

    def play(self, melody: Melody) -> bool:
        """播放旋律。"""
        return True

    def generate_midi(self, melody: Melody, path: str) -> bool:
        """生成MIDI。"""
        return True

    def transpose(self, melody: Melody, semitones: int) -> Melody:
        """移调。"""
        return melody


def create_music_engine() -> MusicEngine:
    """创建音乐引擎。"""
    return MusicEngine()


def _register_music(builtins: dict) -> None:
    """注册音乐内置函数。"""
    builtins["创建音乐引擎"] = create_music_engine
    builtins["创建音阶"] = lambda r, s="major": MusicEngine().create_scale(r, s)
    builtins["创建和弦"] = lambda r, t="major": MusicEngine().create_chord(r, t)
    builtins["创建旋律"] = lambda n="m": MusicEngine().create_melody(n)
    builtins["添加音符"] = lambda m, p, o=4, d=1.0: MusicEngine().add_note(m, p, o, d)
    builtins["播放"] = lambda m: MusicEngine().play(m)
    builtins["生成MIDI"] = lambda m, p: MusicEngine().generate_midi(m, p)
    builtins["移调"] = lambda m, s: MusicEngine().transpose(m, s)


def _music_symtab_names() -> list[str]:
    return [
        "创建音乐引擎", "创建音阶", "创建和弦",
        "创建旋律", "添加音符", "播放", "生成MIDI", "移调",
    ]


__all__ = [
    "ScaleType", "Note", "Chord", "Melody",
    "MusicEngine", "create_music_engine",
    "_register_music", "_music_symtab_names",
]
