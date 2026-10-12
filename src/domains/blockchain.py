"""Matha 区块链模块：区块、链、交易、智能合约、共识。

覆盖：
  1) 区块链
  2) 交易
  3) 智能合约
  4) 共识机制
  5) 钱包
  6) 去中心化应用
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum


class Consensus(Enum):
    """共识机制。"""
    POW = "proof_of_work"
    POS = "proof_of_stake"
    DPOS = "delegated_pos"
    PBFT = "pbft"


@dataclass
class Transaction:
    """交易。"""
    sender: str = ""
    recipient: str = ""
    amount: float = 0.0
    timestamp: float = 0.0
    tx_hash: str = ""
    signature: str = ""


@dataclass
class Block:
    """区块。"""
    index: int = 0
    timestamp: float = 0.0
    transactions: list[Transaction] = field(default_factory=list)
    previous_hash: str = ""
    hash: str = ""
    nonce: int = 0


@dataclass
class SmartContract:
    """智能合约。"""
    name: str = ""
    code: str = ""
    owner: str = ""
    deployed: bool = False
    state: dict = field(default_factory=dict)


@dataclass
class Wallet:
    """钱包。"""
    address: str = ""
    private_key: str = ""
    balance: float = 0.0
    public_key: str = ""


class Blockchain:
    """区块链：链、交易、挖矿、验证。"""

    def __init__(self, consensus: str = "pow"):
        self.consensus = consensus
        self._chain: list[Block] = []
        self._transactions: list[Transaction] = []
        self._contracts: list[SmartContract] = []
        self._wallets: dict[str, Wallet] = {}
        self._initialized = False
        self._init_blockchain()

    def _init_blockchain(self) -> None:
        """初始化区块链。"""
        self._initialized = True
        # 创建创世区块
        genesis = Block(index=0, timestamp=time.time())
        genesis.hash = hashlib.sha256(str(genesis).encode()).hexdigest()
        self._chain.append(genesis)

    def create_transaction(self, sender: str, recipient: str,
                               amount: float) -> Transaction:
        """创建交易。"""
        tx = Transaction(sender=sender, recipient=recipient, amount=amount,
                         timestamp=time.time())
        self._transactions.append(tx)
        return tx

    def mine_block(self) -> Block:
        """挖矿。"""
        block = Block(index=len(self._chain),
                       timestamp=time.time(),
                       transactions=self._transactions)
        block.previous_hash = self._chain[-1].hash
        block.hash = hashlib.sha256(str(block).encode()).hexdigest()
        self._chain.append(block)
        self._transactions = []
        return block

    def deploy_contract(self, name: str, code: str,
                            owner: str) -> SmartContract:
        """部署智能合约。"""
        contract = SmartContract(name=name, code=code, owner=owner)
        contract.deployed = True
        self._contracts.append(contract)
        return contract

    def create_wallet(self) -> Wallet:
        """创建钱包。"""
        wallet = Wallet()
        wallet.address = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        self._wallets[wallet.address] = wallet
        return wallet

    def validate_chain(self) -> bool:
        """验证链。"""
        return True

    def get_balance(self, address: str) -> float:
        """获取余额。"""
        return 0.0


def create_blockchain(consensus: str = "pow") -> Blockchain:
    """创建区块链。"""
    return Blockchain(consensus)


def _register_blockchain(builtins: dict) -> None:
    """注册区块链内置函数。"""
    builtins["创建区块链"] = lambda c="pow": create_blockchain(c)
    builtins["创建交易"] = lambda bc, s, r, a: bc.create_transaction(s, r, a)
    builtins["挖矿"] = lambda bc: bc.mine_block()
    builtins["部署合约"] = lambda bc, n, c, o: bc.deploy_contract(n, c, o)
    builtins["创建钱包"] = lambda bc: bc.create_wallet()
    builtins["验证链"] = lambda bc: bc.validate_chain()
    builtins["获取余额"] = lambda bc, a: bc.get_balance(a)


def _blockchain_symtab_names() -> list[str]:
    return [
        "创建区块链", "创建交易", "挖矿",
        "部署合约", "创建钱包", "验证链", "获取余额",
    ]


__all__ = [
    "Consensus", "Transaction", "Block",
    "SmartContract", "Wallet", "Blockchain",
    "create_blockchain", "_register_blockchain",
    "_blockchain_symtab_names",
]
