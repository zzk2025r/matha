# -*- coding: utf-8 -*-
"""Audio/Video 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.audio_video import (
    _音频采样率转换, _视频码率估算, _流媒体延迟,
    _编解码压缩比, _音频信噪比, _视频帧率稳定性,
)


class TestAudioVideo(unittest.TestCase):
    def test_audio_sample_rate_convert(self):
        result = _音频采样率转换(44100, 48000, 2)
        self.assertGreater(result, 0)

    def test_video_bitrate_estimate(self):
        br = _视频码率估算(1920, 1080, 30, 0.1)
        self.assertGreater(br, 0)

    def test_streaming_latency(self):
        lat = _流媒体延迟(2, 50, 100)
        self.assertGreater(lat, 0)

    def test_codec_compression_ratio(self):
        ratio = _编解码压缩比(100, 10)
        self.assertGreater(ratio, 0)

    def test_audio_snr(self):
        snr = _音频信噪比(1.0, 0.001)
        self.assertGreater(snr, 0)

    def test_video_frame_stability(self):
        stab = _视频帧率稳定性(30, [29, 30, 31, 30])
        self.assertGreater(stab, 0)


if __name__ == '__main__':
    unittest.main()
