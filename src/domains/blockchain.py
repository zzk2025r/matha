# -*- coding: utf-8 -*-
"""
Matha 区块链与Web3开发领域模块。

覆盖：
  1) 区块与链操作
  2) 哈希与 Merkel 树
  3) 交易签名与验证
  4) PoW/PoS 共识
  5) 智能合约模拟
  6) Token 转账
"""
from __future__ import annotations
import hashlib
import hmac
from typing import Optional


# ============================================================
# 区块
# ============================================================

def block_create(prev_hash: str, transactions: list[dict], nonce: int = 0) -> dict:
    """创建区块。"""
    data = f"{prev_hash}:{hashlib.sha256(str(transactions).encode()).hexdigest()}:{nonce}"
    return {
        "index": 0,
        "timestamp": 0.0,
        "prev_hash": prev_hash,
        "transactions": transactions,
        "nonce": nonce,
        "hash": hashlib.sha256(data.encode()).hexdigest(),
    }


def block_verify(block: dict, prev_block: Optional[dict] = None) -> bool:
    """验证区块。"""
    data = f"{block['prev_hash']}:{hashlib.sha256(str(block['transactions']).encode()).hexdigest()}:{block['nonce']}"
    return block["hash"] == hashlib.sha256(data.encode()).hexdigest()


def chain_validate(chain: list[dict]) -> bool:
    """验证区块链。"""
    for i in range(1, len(chain)):
        if chain[i]["prev_hash"] != chain[i-1]["hash"]:
            return False
        if not block_verify(chain[i], chain[i-1]):
            return False
    return True


# ============================================================
# 哈希与 Merkel 树
# ============================================================

def hash_block(data: str) -> str:
    """区块哈希。"""
    return hashlib.sha256(data.encode()).hexdigest()


def merkle_root(leaves: list[str]) -> str:
    """Merkle 根。"""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    current = leaves[:]
    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), 2):
            if i + 1 < len(current):
                combined = current[i] + current[i+1]
            else:
                combined = current[i] + current[i]
            next_level.append(hashlib.sha256(combined.encode()).hexdigest())
        current = next_level
    return current[0]


# ============================================================
# 交易签名
# ============================================================

def sign_transaction(tx: dict, private_key: str) -> str:
    """交易签名。"""
    data = f"{tx['from']}:{tx['to']}:{tx['amount']}"
    return hmac.new(private_key.encode(), data.encode(), hashlib.sha256).hexdigest()


def verify_signature(tx: dict, signature: str, public_key: str) -> bool:
    """验证签名。"""
    expected = sign_transaction(tx, public_key)
    return hmac.compare_digest(expected, signature)


# ============================================================
# 共识算法
# ============================================================

def poW_mine(block: dict, difficulty: int = 4) -> dict:
    """PoW 挖矿。"""
    target = "0" * difficulty
    nonce = 0
    while True:
        data = f"{block['prev_hash']}:{hashlib.sha256(str(block['transactions']).encode()).hexdigest()}:{nonce}"
        h = hashlib.sha256(data.encode()).hexdigest()
        if h.startswith(target):
            block["nonce"] = nonce
            block["hash"] = h
            return block
        nonce += 1
        if nonce > 10_000_000:
            break
    return block


def poS_validate(proposer: str, stake: float, validators: list[dict]) -> bool:
    """PoS 验证（简化）。"""
    total_stake = sum(v["stake"] for v in validators)
    if total_stake == 0:
        return False
    return stake / total_stake > 0.33  # 简单超三分之二规则


# ============================================================
# 智能合约模拟
# ============================================================

_contract_store: dict = {}


def smart_contract_deploy(code: str, owner: str) -> str:
    """部署智能合约。"""
    addr = hashlib.sha256(f"{owner}:{code}".encode()).hexdigest()[:16]
    _contract_store[addr] = {"code": code, "owner": owner, "balance": 0.0}
    return addr


def smart_contract_call(addr: str, func: str, args: list) -> dict:
    """调用智能合约。"""
    if addr not in _contract_store:
        return {"error": "合约不存在"}
    contract = _contract_store[addr]
    # 简化：返回调用结果
    return {"status": "success", "contract": addr, "function": func}


# ============================================================
# Token
# ============================================================

_token_balances: dict = {}


def token_transfer(from_addr: str, to_addr: str, amount: float) -> bool:
    """Token 转账。"""
    if from_addr not in _token_balances:
        _token_balances[from_addr] = 0.0
    if to_addr not in _token_balances:
        _token_balances[to_addr] = 0.0
    if _token_balances[from_addr] < amount:
        return False
    _token_balances[from_addr] -= amount
    _token_balances[to_addr] += amount
    return True


def token_balance(addr: str) -> float:
    """查询 Token 余额。"""
    return _token_balances.get(addr, 0.0)


def token_mint(addr: str, amount: float) -> None:
    """铸造 Token。"""
    _token_balances[addr] = _token_balances.get(addr, 0.0) + amount


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 区块
    "block_create", "block_verify", "chain_validate",
    # 哈希
    "hash_block", "merkle_root",
    # 签名
    "sign_transaction", "verify_signature",
    # 共识
    "poW_mine", "poS_validate",
    # 智能合约
    "smart_contract_deploy", "smart_contract_call",
    # Token
    "token_transfer", "token_balance", "token_mint",
]


# ============================================================
# 注册到解释器
# ============================================================

def _register_blockchain(builtins: dict) -> None:
    """注册区块链内建到解释器。"""
    builtins["创建区块"] = block_create
    builtins["验证区块"] = block_verify
    builtins["验证区块链"] = chain_validate
    builtins["区块哈希"] = hash_block
    builtins["Merkle根"] = merkle_root
    builtins["签名交易"] = sign_transaction
    builtins["验证签名"] = verify_signature
    builtins["PoW挖矿"] = poW_mine
    builtins["PoS验证"] = poS_validate
    builtins["部署合约"] = smart_contract_deploy
    builtins["调用合约"] = smart_contract_call
    builtins["Token转账"] = token_transfer
    builtins["Token余额"] = token_balance
    builtins["Token铸造"] = token_mint


def _blockchain_symtab_names() -> list[str]:
    return ["创建区块", "验证区块", "验证区块链", "区块哈希", "Merkle根",
            "签名交易", "验证签名", "PoW挖矿", "PoS验证",
            "部署合约", "调用合约", "Token转账", "Token余额", "Token铸造"]
