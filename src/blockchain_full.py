"""Matha 区块链：EVM、智能合约、共识机制。"""
from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConsensusType(Enum):
    POW = "pow"
    POS = "pos"
    DPOS = "dpos"
    PBFT = "pbft"
    RANDOM = "random"
    POA = "poa"


class TransactionType(Enum):
    TRANSFER = "transfer"
    CONTRACT = "contract"
    DEPLOY = "deploy"
    CALL = "call"


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: list[dict[str, Any]] = field(default_factory=list)
    prev_hash: str = "0"
    hash: str = ""
    nonce: int = 0
    validator: str | None = None
    merkle_root: str = ""
    size: int = 0


@dataclass
class Transaction:
    from_addr: str = ""
    to_addr: str = ""
    value: float = 0.0
    data: bytes = b""
    nonce: int = 0
    gas_limit: int = 21000
    gas_price: float = 0.0
    type: TransactionType = TransactionType.TRANSFER
    signature: str | None = None
    tx_hash: str = ""


@dataclass
class SmartContract:
    address: str = ""
    bytecode: str = ""
    abi: list[dict[str, Any]] = field(default_factory=list)
    storage: dict[str, Any] = field(default_factory=dict)
    creator: str = ""
    balance: float = 0.0
    deployed_at: float = field(default_factory=time.time)


@dataclass
class Account:
    address: str = ""
    balance: float = 0.0
    nonce: int = 0
    code_hash: str = ""
    storage_root: str = ""


class EVM:
    """以太坊虚拟机。"""

    def __init__(self):
        self._state: dict[str, Account] = {}
        self._blockchain: list[Block] = []
        self._pending_txs: list[Transaction] = []
        self._gas_price = 1.0
        self._block_gas_limit = 30000000
        self._consensus = ConsensusType.POW
        self._difficulty = 1000

    def create_account(self, address: str,
                          balance: float = 0.0) -> Account:
        account = Account(address=address, balance=balance)
        self._state[address] = account
        return account

    def get_account(self, address: str) -> Account | None:
        return self._state.get(address)

    def deploy_contract(self, bytecode: str,
                           creator: str) -> SmartContract:
        addr = hashlib.sha256(
            f"{creator}{time.time()}".encode()
        ).hexdigest()[:40]
        contract = SmartContract(
            address=addr, bytecode=bytecode, creator=creator,
        )
        self._state[addr] = Account(
            address=addr, code_hash=hashlib.sha256(bytecode.encode()).hexdigest()
        )
        return contract

    def call_contract(self, addr: str,
                         method: str,
                         args: list[Any] = None) -> Any:
        contract = self._state.get(addr)
        if contract:
            return {"result": "executed", "method": method}
        return None

    def execute_tx(self, tx: Transaction) -> bool:
        from_acc = self._state.get(tx.from_addr)
        to_acc = self._state.get(tx.to_addr)
        if from_acc and from_acc.balance >= tx.value:
            from_acc.balance -= tx.value
            if to_acc:
                to_acc.balance += tx.value
            tx.tx_hash = hashlib.sha256(
                str(tx).encode()
            ).hexdigest()
            return True
        return False


class Blockchain:
    """区块链。"""

    def __init__(self, consensus: ConsensusType = ConsensusType.POW,
                 difficulty: int = 1000):
        self.consensus = consensus
        self.difficulty = difficulty
        self._blocks: list[Block] = []
        self._evm = EVM()
        self._genesis_block = self._create_genesis()
        self._chain_id = random.randint(1, 2**32)
        self._pending_txs: list[Transaction] = []

    def _create_genesis(self) -> Block:
        genesis = Block(index=0, timestamp=time.time())
        genesis.hash = hashlib.sha256(
            str(genesis).encode()
        ).hexdigest()
        self._blocks.append(genesis)
        return genesis

    def add_transaction(self, tx: Transaction) -> bool:
        self._pending_txs.append(tx)
        return True

    def mine_block(self) -> Block:
        prev_block = self._blocks[-1]
        txs = self._pending_txs[:]
        self._pending_txs = []
        block = Block(
            index=len(self._blocks),
            timestamp=time.time(),
            transactions=txs,
            prev_hash=prev_block.hash,
        )
        block.hash = self._mine(block)
        self._blocks.append(block)
        return block

    def _mine(self, block: Block) -> str:
        nonce = 0
        while True:
            data = f"{block.index}{block.prev_hash}{nonce}"
            hash_val = hashlib.sha256(data.encode()).hexdigest()
            if hash_val.startswith("0" * (self.difficulty // 4)):
                block.nonce = nonce
                return hash_val
            nonce += 1

    def get_block(self, index: int) -> Block | None:
        return self._blocks[index] if index < len(self._blocks) else None

    def get_chain(self) -> list[Block]:
        return self._blocks

    def is_valid(self) -> bool:
        for i in range(1, len(self._blocks)):
            prev = self._blocks[i-1]
            curr = self._blocks[i]
            if curr.prev_hash != prev.hash:
                return False
        return True


class SmartContractEngine:
    """智能合约引擎。"""

    def __init__(self):
        self._contracts: dict[str, SmartContract] = {}
        self._evm = EVM()
        self._gas_used = 0
        self._gas_limit = 30000000

    def deploy(self, bytecode: str,
                  creator: str) -> SmartContract:
        contract = self._evm.deploy_contract(bytecode, creator)
        self._contracts[contract.address] = contract
        return contract

    def call(self, addr: str, method: str,
                args: list[Any] = None) -> Any:
        return self._evm.call_contract(addr, method, args)

    def get_contract(self, addr: str) -> SmartContract | None:
        return self._contracts.get(addr)

    def estimate_gas(self, bytecode: str) -> int:
        return len(bytecode) // 2


class Token:
    """代币。"""

    def __init__(self, name: str, symbol: str,
                 total_supply: float, decimals: int = 18):
        self.name = name
        self.symbol = symbol
        self.total_supply = total_supply
        self.decimals = decimals
        self.balances: dict[str, float] = {}

    def transfer(self, from_addr: str, to_addr: str,
                    amount: float) -> bool:
        if self.balances.get(from_addr, 0) >= amount:
            self.balances[from_addr] = self.balances.get(from_addr, 0) - amount
            self.balances[to_addr] = self.balances.get(to_addr, 0) + amount
            return True
        return False

    def balance_of(self, addr: str) -> float:
        return self.balances.get(addr, 0.0)


def create_blockchain(consensus: ConsensusType = ConsensusType.POW
                           ) -> Blockchain:
    return Blockchain(consensus=consensus)


def create_smart_contract_engine() -> SmartContractEngine:
    return SmartContractEngine()


def create_token(name: str, symbol: str,
                    total_supply: float) -> Token:
    return Token(name=name, symbol=symbol, total_supply=total_supply)


# ============================================================
# 内置注册
# ============================================================

def _register_blockchain(builtins: dict) -> None:
    builtins["创建区块链"] = create_blockchain
    builtins["创建智能合约引擎"] = create_smart_contract_engine
    builtins["创建代币"] = create_token


def _blockchain_names() -> list[str]:
    return ["创建区块链", "创建智能合约引擎", "创建代币"]


__all__ = [
    "ConsensusType", "TransactionType",
    "Block", "Transaction", "SmartContract", "Account",
    "EVM", "Blockchain", "SmartContractEngine", "Token",
    "create_blockchain", "create_smart_contract_engine",
    "create_token",
    "_register_blockchain", "_blockchain_names",
]
