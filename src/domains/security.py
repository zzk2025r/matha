"""Matha 加密安全模块：哈希、加密、签名、认证。

覆盖：
  1) 哈希函数（MD5/SHA-256/BLAKE3）
  2) 对称加密（AES）
  3) 非对称加密（RSA）
  4) 数字签名
  5) 认证/授权
  6) 随机数生成
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum


class HashAlgorithm(Enum):
    """哈希算法。"""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE3 = "blake3"


class EncryptionAlgorithm(Enum):
    """加密算法。"""
    AES_128 = "aes-128"
    AES_256 = "aes-256"
    RSA_2048 = "rsa-2048"
    RSA_4096 = "rsa-4096"


class SignatureScheme(Enum):
    """签名方案。"""
    HMAC_SHA256 = "hmac-sha256"
    RSA_PSS = "rsa-pss"
    ECDSA = "ecdsa"


@dataclass
class HashResult:
    """哈希结果。"""
    algorithm: str
    hash_value: str
    input_size: int
    output_size: int


@dataclass
class EncryptionResult:
    """加密结果。"""
    algorithm: str
    ciphertext: bytes
    key_id: str
    iv: bytes


@dataclass
class SignatureResult:
    """签名结果。"""
    algorithm: str
    signature: bytes
    public_key: str
    verified: bool


@dataclass
class AuthToken:
    """认证令牌。"""
    token: str
    user_id: str
    expires_at: float
    permissions: list[str] = field(default_factory=list)


@dataclass
class SecurityStats:
    """安全统计。"""
    hashes_computed: int = 0
    encryptions: int = 0
    signatures: int = 0
    auth_tokens: int = 0
    failed_attempts: int = 0


class HashEngine:
    """哈希引擎：计算哈希值。"""

    def __init__(self):
        self._stats = SecurityStats()
        self._initialized = False
        self._init_hash()

    def _init_hash(self) -> None:
        """初始化哈希引擎。"""
        self._initialized = True

    def hash(self, data: str, algorithm: str = "sha256") -> HashResult:
        """计算哈希。"""
        h = hashlib.new(algorithm, data.encode())
        self._stats.hashes_computed += 1
        return HashResult(
            algorithm=algorithm,
            hash_value=h.hexdigest(),
            input_size=len(data),
            output_size=h.digest_size,
        )

    def md5(self, data: str) -> HashResult:
        """MD5哈希。"""
        return self.hash(data, "md5")

    def sha256(self, data: str) -> HashResult:
        """SHA-256哈希。"""
        return self.hash(data, "sha256")

    def sha512(self, data: str) -> HashResult:
        """SHA-512哈希。"""
        return self.hash(data, "sha512")

    def blake3_hash(self, data: str) -> HashResult:
        """BLAKE3哈希。"""
        return self.hash(data, "blake3")


class EncryptionEngine:
    """加密引擎：对称/非对称加密。"""

    def __init__(self):
        self._stats = SecurityStats()
        self._keys: dict[str, bytes] = {}
        self._initialized = False
        self._init_encryption()

    def _init_encryption(self) -> None:
        """初始化加密引擎。"""
        self._initialized = True

    def generate_key(self, algorithm: str = "aes-256") -> str:
        """生成密钥。"""
        key_id = secrets.token_hex(16)
        key = secrets.token_bytes(32 if "256" in algorithm else 16)
        self._keys[key_id] = key
        return key_id

    def encrypt(self, data: str, key_id: str) -> EncryptionResult:
        """加密数据 — 显式拒绝：AES 对称加密未实现（标准库无 AES）。

        旧实现把明文字节标注成 AES-256 密文返回（假成功）。
        """
        raise NotImplementedError(
            "对称加密未实现（标准库无 AES；旧实现将明文冒充密文，已显式拒绝）")

    def decrypt(self, ciphertext: bytes, key_id: str) -> str:
        """解密数据 — 显式拒绝（同 encrypt）。"""
        raise NotImplementedError(
            "对称解密未实现（标准库无 AES；旧实现将密文原样解码冒充明文，已显式拒绝）")


class SignatureEngine:
    """签名引擎：数字签名。"""

    def __init__(self):
        self._stats = SecurityStats()
        self._initialized = False
        self._init_signature()

    def _init_signature(self) -> None:
        """初始化签名引擎。"""
        self._initialized = True

    def sign(self, data: str, key_id: str) -> SignatureResult:
        """签名数据 — 真实 HMAC-SHA256（key_id 即密钥材料）。"""
        import hmac
        self._stats.signatures += 1
        digest = hmac.new(key_id.encode(), data.encode(), "sha256").digest()
        return SignatureResult(
            algorithm="HMAC-SHA256",
            signature=digest,
            public_key=key_id,
            verified=True,
        )

    def verify(self, data: str, signature: bytes,
                public_key: str) -> bool:
        """验证签名 — 重算 HMAC 并恒时比较（旧实现恒 True）。"""
        import hmac
        expected = hmac.new(public_key.encode(), data.encode(), "sha256").digest()
        return hmac.compare_digest(expected, signature)


class AuthManager:
    """认证管理器：用户认证和授权。

    令牌存于类级仓库（跨实例共享）：一次性工厂（生成令牌/验证令牌内建各建
    新实例）下签发与验证仍属同一仓库，验证真实可用。
    """

    _TOKEN_STORE: dict[str, "AuthToken"] = {}

    def __init__(self):
        self._tokens: dict[str, AuthToken] = self._TOKEN_STORE
        self._stats = SecurityStats()
        self._initialized = False
        self._init_auth()

    def _init_auth(self) -> None:
        """初始化认证管理器。"""
        self._initialized = True

    def generate_token(self, user_id: str,
                         permissions: list[str] = None
                         ) -> AuthToken:
        """生成认证令牌。"""
        token = secrets.token_hex(32)
        expires_at = time.time() + 3600
        auth_token = AuthToken(
            token=token, user_id=user_id,
            expires_at=expires_at,
            permissions=permissions or [],
        )
        self._tokens[token] = auth_token
        self._stats.auth_tokens += 1
        return auth_token

    def verify_token(self, token: str) -> bool:
        """验证令牌 — 存在且未过期（旧实现只查存在、无视过期）。"""
        t = self._tokens.get(token)
        if t is None:
            return False
        return t.expires_at > time.time()

    def revoke_token(self, token: str) -> bool:
        """撤销令牌。"""
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False

    def get_user_id(self, token: str) -> str | None:
        """获取用户ID。"""
        t = self._tokens.get(token)
        return t.user_id if t else None


class SecureRandom:
    """安全随机数生成器。"""

    def __init__(self):
        self._initialized = False
        self._init_random()

    def _init_random(self) -> None:
        """初始化随机数生成器。"""
        self._initialized = True

    def generate(self, length: int = 32) -> str:
        """生成随机字符串。"""
        return secrets.token_hex(length)

    def generate_bytes(self, length: int = 32) -> bytes:
        """生成随机字节。"""
        return secrets.token_bytes(length)

    def generate_int(self, min_val: int = 0,
                        max_val: int = 1000000) -> int:
        """生成随机整数。"""
        return secrets.randbelow(max_val - min_val) + min_val


def create_hash_engine() -> HashEngine:
    """创建哈希引擎。"""
    return HashEngine()


def create_encryption_engine() -> EncryptionEngine:
    """创建加密引擎。"""
    return EncryptionEngine()


def create_signature_engine() -> SignatureEngine:
    """创建签名引擎。"""
    return SignatureEngine()


def create_auth_manager() -> AuthManager:
    """创建认证管理器。"""
    return AuthManager()


def create_secure_random() -> SecureRandom:
    """创建安全随机数生成器。"""
    return SecureRandom()


def _register_security(builtins: dict) -> None:
    """注册安全内置函数。"""
    builtins["创建哈希引擎"] = create_hash_engine
    builtins["创建加密引擎"] = create_encryption_engine
    builtins["创建签名引擎"] = create_signature_engine
    builtins["创建认证管理器"] = create_auth_manager
    builtins["创建安全随机数"] = create_secure_random
    builtins["MD5哈希"] = lambda d: create_hash_engine().md5(d)
    builtins["SHA256哈希"] = lambda d: create_hash_engine().sha256(d)
    builtins["SHA512哈希"] = lambda d: create_hash_engine().sha512(d)
    builtins["生成密钥"] = lambda a="aes-256": create_encryption_engine().generate_key(a)
    builtins["加密数据"] = lambda d, k: create_encryption_engine().encrypt(d, k)
    builtins["解密数据"] = lambda c, k: create_encryption_engine().decrypt(c, k)
    builtins["签名"] = lambda d, k: create_signature_engine().sign(d, k)
    builtins["验证签名"] = lambda d, s, p: create_signature_engine().verify(d, s, p)
    builtins["生成令牌"] = lambda u, p=None: create_auth_manager().generate_token(u, p)
    builtins["验证令牌"] = lambda t: create_auth_manager().verify_token(t)
    builtins["生成随机数"] = lambda l=32: create_secure_random().generate(l)


def _security_symtab_names() -> list[str]:
    return [
        "创建哈希引擎", "创建加密引擎", "创建签名引擎",
        "创建认证管理器", "创建安全随机数",
        "MD5哈希", "SHA256哈希", "SHA512哈希",
        "生成密钥", "加密数据", "解密数据",
        "签名", "验证签名",
        "生成令牌", "验证令牌", "生成随机数",
    ]


__all__ = [
    "HashAlgorithm", "EncryptionAlgorithm", "SignatureScheme",
    "HashResult", "EncryptionResult", "SignatureResult",
    "AuthToken", "SecurityStats",
    "HashEngine", "EncryptionEngine", "SignatureEngine",
    "AuthManager", "SecureRandom",
    "create_hash_engine", "create_encryption_engine",
    "create_signature_engine", "create_auth_manager",
    "create_secure_random", "_register_security",
    "_security_symtab_names",
]
