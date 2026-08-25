# -*- coding: utf-8 -*-
"""
Matha 领域模块单元测试。

测试覆盖：
  1) AI/数据科学领域
  2) 软件/应用开发领域
  3) 游戏开发领域
  4) 区块链领域
  5) 量子计算领域
  6) 混沌/分型领域
  7) 遗传算法领域
  8) 创意编程领域
  9) 领域注册表
"""
import sys
import unittest
sys.path.insert(0, r"D:\trae")


class TestAIScienceDomain(unittest.TestCase):
    """AI 与数据科学领域测试。"""

    def test_sigmoid(self):
        from src.domains.ai_data_science import sigmoid
        self.assertAlmostEqual(sigmoid(0), 0.5)
        self.assertAlmostEqual(sigmoid(10), 0.99995, places=4)
        self.assertAlmostEqual(sigmoid(-10), 0.00005, places=4)

    def test_relu(self):
        from src.domains.ai_data_science import relu
        self.assertEqual(relu(5), 5.0)
        self.assertEqual(relu(-3), 0.0)
        self.assertEqual(relu(0), 0.0)

    def test_softmax(self):
        from src.domains.ai_data_science import softmax
        result = softmax([1.0, 2.0, 3.0])
        self.assertAlmostEqual(sum(result), 1.0)
        self.assertTrue(all(0 < r < 1 for r in result))

    def test_mse(self):
        from src.domains.ai_data_science import mse
        self.assertAlmostEqual(mse([1.0, 2.0], [1.0, 2.0]), 0.0)
        self.assertAlmostEqual(mse([0.0, 0.0], [1.0, 1.0]), 1.0)

    def test_cross_entropy(self):
        from src.domains.ai_data_science import cross_entropy
        result = cross_entropy([1.0, 0.0], [0.9, 0.1])
        self.assertGreater(result, 0)

    def test_accuracy(self):
        from src.domains.ai_data_science import accuracy
        self.assertAlmostEqual(accuracy([0, 1, 1, 0], [0, 1, 0, 1]), 0.5)

    def test_dot_product(self):
        from src.domains.ai_data_science import dot_product
        self.assertAlmostEqual(dot_product([1, 2, 3], [4, 5, 6]), 32.0)

    def test_matrix_mult(self):
        from src.domains.ai_data_science import matrix_mult
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]
        result = matrix_mult(a, b)
        self.assertAlmostEqual(result[0][0], 19.0)
        self.assertAlmostEqual(result[0][1], 22.0)

    def test_gradient_descent(self):
        from src.domains.ai_data_science import gradient_descent
        params = {"w": 1.0, "b": 0.0}
        grads = {"w": 0.5, "b": 0.1}
        result = gradient_descent(params, grads, lr=0.1)
        self.assertAlmostEqual(result["w"], 0.95)
        self.assertAlmostEqual(result["b"], -0.01)

    def test_mean(self):
        from src.domains.ai_data_science import mean
        self.assertAlmostEqual(mean([1, 2, 3, 4, 5]), 3.0)

    def test_std(self):
        from src.domains.ai_data_science import std
        self.assertAlmostEqual(std([2, 4, 4, 4, 5, 5, 7, 9]), 2.0, places=1)

    def test_correlation(self):
        from src.domains.ai_data_science import correlation
        self.assertAlmostEqual(correlation([1, 2, 3], [2, 4, 6]), 1.0)


class TestSoftwareAppDomain(unittest.TestCase):
    """软件与应用开发领域测试。"""

    def test_http_get(self):
        from src.domains.software_app import http_get
        result = http_get("https://api.example.com")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["method"], "GET")

    def test_http_post(self):
        from src.domains.software_app import http_post
        result = http_post("https://api.example.com", {"key": "value"})
        self.assertEqual(result["status"], 201)

    def test_jwt_encode_decode(self):
        from src.domains.software_app import jwt_encode, jwt_decode
        token = jwt_encode({"user": "test", "role": "admin"})
        payload = jwt_decode(token)
        self.assertEqual(payload["user"], "test")

    def test_bcrypt_hash_verify(self):
        from src.domains.software_app import bcrypt_hash, bcrypt_verify
        hashed = bcrypt_hash("password123")
        self.assertTrue(bcrypt_verify("password123", hashed))
        self.assertFalse(bcrypt_verify("wrong", hashed))

    def test_cache_get_set(self):
        from src.domains.software_app import cache_set, cache_get, cache_size
        cache_set("key1", "value1")
        self.assertEqual(cache_get("key1"), "value1")
        self.assertEqual(cache_size(), 1)

    def test_queue(self):
        from src.domains.software_app import queue_enqueue, queue_dequeue, queue_size
        queue_enqueue(1)
        queue_enqueue(2)
        self.assertEqual(queue_size(), 2)
        self.assertEqual(queue_dequeue(), 1)
        self.assertEqual(queue_dequeue(), 2)

    def test_db_insert_query(self):
        from src.domains.software_app import db_insert, db_query
        id_ = db_insert("users", {"name": "Alice", "age": 30})
        rows = db_query("users", {"name": "Alice"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Alice")


class TestGameDevDomain(unittest.TestCase):
    """游戏开发领域测试。"""

    def test_sprite_create(self):
        from src.domains.game_dev import sprite_create
        s = sprite_create(100, 200, 32, 32)
        self.assertEqual(s["x"], 100)
        self.assertEqual(s["w"], 32)

    def test_sprite_collide(self):
        from src.domains.game_dev import sprite_collide, sprite_create
        a = sprite_create(0, 0, 10, 10)
        b = sprite_create(5, 5, 10, 10)
        self.assertTrue(sprite_collide(a, b))
        c = sprite_create(100, 100, 10, 10)
        self.assertFalse(sprite_collide(a, c))

    def test_particle_emitter(self):
        from src.domains.game_dev import particle_emitter
        particles = particle_emitter(400, 300, count=5)
        self.assertEqual(len(particles), 5)

    def test_physics_gravity(self):
        from src.domains.game_dev import physics_gravity
        obj = {"vy": 0.0}
        result = physics_gravity(obj, g=9.81, dt=1/60)
        self.assertAlmostEqual(result["vy"], 0.1635, places=4)

    def test_render_3d(self):
        from src.domains.game_dev import render_3d
        point = (0, 0, 10)
        camera = (0, 0, 0)
        result = render_3d(point, camera, (0, 0, 1))
        self.assertIsInstance(result, tuple)

    def test_camera_look_at(self):
        from src.domains.game_dev import camera_look_at
        result = camera_look_at((0, 0, 5), (0, 0, 0))
        self.assertEqual(len(result), 3)


class TestBlockchainDomain(unittest.TestCase):
    """区块链领域测试。"""

    def test_block_create_verify(self):
        from src.domains.blockchain import block_create, block_verify
        block = block_create("0", [{"tx": "a"}])
        self.assertTrue(block_verify(block))

    def test_chain_validate(self):
        from src.domains.blockchain import block_create, chain_validate
        b1 = block_create("0", [])
        b2 = block_create(b1["hash"], [{"tx": "b"}])
        chain = [b1, b2]
        self.assertTrue(chain_validate(chain))

    def test_merkle_root(self):
        from src.domains.blockchain import merkle_root
        root = merkle_root(["a", "b", "c"])
        self.assertIsInstance(root, str)
        self.assertEqual(len(root), 64)

    def test_sign_verify(self):
        from src.domains.blockchain import sign_transaction, verify_signature
        tx = {"from": "A", "to": "B", "amount": 10}
        sig = sign_transaction(tx, "secret")
        self.assertTrue(verify_signature(tx, sig, "secret"))

    def test_token_transfer(self):
        from src.domains.blockchain import token_mint, token_transfer, token_balance
        token_mint("A", 100)
        token_mint("B", 50)
        self.assertTrue(token_transfer("A", "B", 30))
        self.assertEqual(token_balance("A"), 70)
        self.assertEqual(token_balance("B"), 80)


class TestQuantumComputingDomain(unittest.TestCase):
    """量子计算领域测试。"""

    def test_hadamard(self):
        from src.domains.quantum_compute import hadamard
        h = hadamard()
        self.assertAlmostEqual(h[0][0], 1/math.sqrt(2))

    def test_bell_state(self):
        from src.domains.quantum_compute import bell_state
        state = bell_state()
        self.assertAlmostEqual(abs(state[0]), 1/math.sqrt(2))
        self.assertAlmostEqual(abs(state[3]), 1/math.sqrt(2))

    def test_ghz_state(self):
        from src.domains.quantum_compute import ghz_state
        state = ghz_state(3)
        self.assertEqual(len(state), 8)
        self.assertAlmostEqual(abs(state[0]), 1/math.sqrt(2))
        self.assertAlmostEqual(abs(state[7]), 1/math.sqrt(2))

    def test_qubit_state(self):
        from src.domains.quantum_compute import qubit_state
        state = qubit_state(0, 0)  # |0>
        self.assertAlmostEqual(abs(state[0]), 1.0)
        self.assertAlmostEqual(abs(state[1]), 0.0)

    def test_quantum_fourier_transform(self):
        from src.domains.quantum_compute import quantum_fourier_transform
        state = [1+0j, 0+0j, 0+0j, 0+0j]
        result = quantum_fourier_transform(state)
        self.assertAlmostEqual(abs(result[0]), 0.5)


class TestChaosFractalDomain(unittest.TestCase):
    """混沌理论与分型领域测试。"""

    def test_lorenz_deriv(self):
        from src.domains.chaos_fractal import lorenz_deriv
        dx, dy, dz = lorenz_deriv(1, 1, 1)
        self.assertIsInstance(dx, float)

    def test_lorenz_attractor(self):
        from src.domains.chaos_fractal import lorenz_attractor
        points = lorenz_attractor(steps=100)
        self.assertEqual(len(points), 101)
        self.assertEqual(len(points[0]), 3)

    def test_henon_map(self):
        from src.domains.chaos_fractal import henon_map
        x, y = henon_map(0.1, 0.1)
        self.assertIsInstance(x, float)

    def test_logistic_map(self):
        from src.domains.chaos_fractal import logistic_map
        result = logistic_map(0.5, r=3.5)
        self.assertEqual(result, 3.5 * 0.5 * 0.5)

    def test_mandelbrot_iter(self):
        from src.domains.chaos_fractal import mandelbrot_iter
        result = mandelbrot_iter(0, 0, max_iter=100)
        self.assertEqual(result, 100)  # 在集合内

    def test_julia_iter(self):
        from src.domains.chaos_fractal import julia_iter
        result = julia_iter(-0.8, 0.156, 0, 0)
        self.assertIsInstance(result, int)

    def test_lyapunov_exponent(self):
        from src.domains.chaos_fractal import lyapunov_exponent
        # r=3.5 应为负（周期轨道）
        result = lyapunov_exponent(3.5)
        self.assertIsInstance(result, float)


class TestGeneticAlgorithmDomain(unittest.TestCase):
    """遗传算法领域测试。"""

    def test_ga_evolve(self):
        from src.domains.genetic_algo import ga_evolve
        population = [[random.choice([0,1]) for _ in range(8)] for _ in range(20)]
        fitness_fn = lambda ind: sum(ind)  # 适应度 = 1的个数
        result = ga_evolve(population, fitness_fn, pop_size=20, max_gen=10)
        self.assertIn("best_fitness", result)
        self.assertGreater(result["best_fitness"], 0)

    def test_elitism_preserve(self):
        from src.domains.genetic_algo import elitism_preserve
        population = [[1,1,1,1], [0,0,0,0], [1,0,1,0]]
        result = elitism_preserve(population, lambda x: sum(x), elite_count=2)
        self.assertEqual(len(result), 2)

    def test_code_generation(self):
        from src.domains.genetic_algo import code_generation
        template = "def {name}({params}): return {expr}"
        result = code_generation(template, {"name": "foo", "params": "x", "expr": "x+1"})
        self.assertIn("foo", result)

    def test_hyperparameter_search(self):
        from src.domains.genetic_algo import hyperparameter_search
        space = {"lr": [0.001, 0.01, 0.1], "epochs": [10, 50, 100]}
        fn = lambda p: -abs(p["lr"] - 0.01) - abs(p["epochs"] - 50)
        result = hyperparameter_search(space, fn, n_iterations=5)
        self.assertIn("best_params", result)


class TestCreativeCodingDomain(unittest.TestCase):
    """创意编程领域测试。"""

    def test_perlin_noise(self):
        from src.domains.creative_coding import PerlinNoise
        perlin = PerlinNoise(seed=42)
        n = perlin.noise_2d(0, 0)
        self.assertIsInstance(n, float)
        self.assertGreaterEqual(n, -1.0)
        self.assertLessEqual(n, 1.0)

    def test_simplex_noise(self):
        from src.domains.creative_coding import simplex_noise_2d
        n = simplex_noise_2d(1.0, 2.0)
        self.assertIsInstance(n, float)

    def test_flow_field(self):
        from src.domains.creative_coding import FlowField
        ff = FlowField(10, 10, scale=2.0)
        dir_ = ff.get_direction(5, 5)
        self.assertEqual(len(dir_), 2)

    def test_particle_system(self):
        from src.domains.creative_coding import particle_system
        particles = particle_system(10)
        self.assertEqual(len(particles), 10)

    def test_barnsley_fern(self):
        from src.domains.creative_coding import fractal_barnsley_fern
        points = fractal_barnsley_fern(n=1000)
        self.assertEqual(len(points), 1001)

    def test_color_hsl_to_rgb(self):
        from src.domains.creative_coding import color_hsl_to_rgb
        r, g, b = color_hsl_to_rgb(0, 1, 0.5)
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(g, 0.0)
        self.assertAlmostEqual(b, 0.0)

    def test_color_lerp(self):
        from src.domains.creative_coding import color_lerp
        result = color_lerp((1, 0, 0), (0, 0, 1), 0.5)
        self.assertAlmostEqual(result[0], 0.5)
        self.assertAlmostEqual(result[2], 0.5)


class TestDomainRegistry(unittest.TestCase):
    """领域注册表测试。"""

    def test_register_domain(self):
        from src.domains.registry import DomainRegistry
        registry = DomainRegistry()
        self.assertTrue(registry.register("AI_DataScience"))
        self.assertIsNotNone(registry.get("AI_DataScience"))

    def test_list_domains(self):
        from src.domains.registry import DomainRegistry
        registry = DomainRegistry()
        registry.register("AI_DataScience")
        domains = registry.list_domains()
        self.assertGreater(len(domains), 0)

    def test_get_builtins(self):
        from src.domains.registry import DomainRegistry
        registry = DomainRegistry()
        registry.register("AI_DataScience")
        builtins = registry.get_builtins("AI_DataScience")
        self.assertIn("sigmoid", builtins)
        self.assertIn("relu", builtins)

    def test_unregister(self):
        from src.domains.registry import DomainRegistry
        registry = DomainRegistry()
        registry.register("AI_DataScience")
        self.assertTrue(registry.unregister("AI_DataScience"))
        self.assertIsNone(registry.get("AI_DataScience"))

    def test_get_stats(self):
        from src.domains.registry import DomainRegistry
        registry = DomainRegistry()
        registry.register("AI_DataScience")
        stats = registry.get_stats()
        self.assertIn("total_domains", stats)
        self.assertGreater(stats["total_domains"], 0)


# 需要导入 random 和 math
import random
import math


if __name__ == "__main__":
    unittest.main(verbosity=2)
