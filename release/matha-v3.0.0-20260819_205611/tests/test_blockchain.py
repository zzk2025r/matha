# -*- coding: utf-8 -*-
"""区块链领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.blockchain import (
    block_create, block_verify, chain_validate,
    merkle_root, sign_transaction, verify_signature,
    token_transfer, token_balance,
)


class TestBlockchain(unittest.TestCase):
    def test_block_create(self):
        block = block_create("0", [{"from": "A", "to": "B", "amount": 10}])
        self.assertIn("hash", block)
        self.assertIn("prev_hash", block)

    def test_block_verify(self):
        block = block_create("0", [])
        self.assertTrue(block_verify(block))

    def test_chain_validate(self):
        b1 = block_create("0", [])
        b2 = block_create(b1["hash"], [])
        chain = [b1, b2]
        self.assertTrue(chain_validate(chain))

    def test_merkle_root(self):
        root = merkle_root(["a", "b", "c", "d"])
        self.assertIsInstance(root, str)
        self.assertEqual(len(root), 64)

    def test_sign_and_verify(self):
        tx = {"from": "A", "to": "B", "amount": 100}
        sig = sign_transaction(tx, "secret_key")
        self.assertTrue(verify_signature(tx, sig, "secret_key"))
        self.assertFalse(verify_signature(tx, sig, "wrong_key"))

    def test_token_transfer(self):
        from src.domains.blockchain import token_mint, _token_balances
        _token_balances.clear()
        token_mint("Alice", 1000.0)
        token_mint("Bob", 0.0)
        self.assertTrue(token_transfer("Alice", "Bob", 100.0))
        self.assertAlmostEqual(token_balance("Alice"), 900.0)
        self.assertAlmostEqual(token_balance("Bob"), 100.0)

    def test_token_insufficient(self):
        from src.domains.blockchain import token_mint, _token_balances
        _token_balances.clear()
        token_mint("Alice", 50.0)
        self.assertFalse(token_transfer("Alice", "Bob", 100.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
