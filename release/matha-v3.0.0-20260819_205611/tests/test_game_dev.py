# -*- coding: utf-8 -*-
"""游戏开发领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.game_dev import (
    sprite_create, sprite_move, sprite_collide, sprite_bounce,
    particle_emitter, physics_gravity, audio_play,
    render_3d, camera_look_at,
)


class TestGameDev(unittest.TestCase):
    def test_sprite_create(self):
        s = sprite_create(10.0, 20.0, 32.0, 32.0)
        self.assertEqual(s["x"], 10.0)
        self.assertEqual(s["active"], True)

    def test_sprite_move(self):
        s = sprite_move({"x": 0.0, "y": 0.0}, 5.0, 3.0)
        self.assertEqual(s["x"], 5.0)
        self.assertEqual(s["y"], 3.0)

    def test_sprite_collide(self):
        a = {"x": 0, "y": 0, "w": 10, "h": 10}
        b = {"x": 5, "y": 5, "w": 10, "h": 10}
        self.assertTrue(sprite_collide(a, b))
        c = {"x": 100, "y": 100, "w": 10, "h": 10}
        self.assertFalse(sprite_collide(a, c))

    def test_particle_emitter(self):
        particles = particle_emitter(100.0, 100.0, count=5)
        self.assertEqual(len(particles), 5)
        self.assertEqual(particles[0]["x"], 100.0)

    def test_physics_gravity(self):
        obj = {"vy": 0.0}
        result = physics_gravity(obj, g=9.81, dt=1/60)
        self.assertAlmostEqual(result["vy"], 9.81 / 60, places=4)

    def test_render_3d(self):
        result = render_3d((0, 0, 10), (0, 0, 0), (0, 0, 1))
        self.assertIsNotNone(result)

    def test_camera_look_at(self):
        result = camera_look_at((0, 0, 5), (0, 0, 0))
        self.assertEqual(len(result), 3)
        self.assertEqual(len(result[0]), 4)

    def test_audio_play(self):
        result = audio_play(440.0, duration=0.5)
        self.assertEqual(result["frequency"], 440.0)
        self.assertTrue(result["playing"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
