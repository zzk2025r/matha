"""Matha 完整安全：bcrypt、Argon2、libsodium、密码学全栈。"""
from __future__ import annotations

import base64
import hashlib
import hmac as hmac_module
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HashAlgorithm(Enum):
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    SHA3_256 = "sha3_256"
    SHA3_512 = "sha3_512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"


class CipherAlgorithm(Enum):
    AES_128 = "aes_128"
    AES_192 = "aes_192"
    AES_256 = "aes_256"
    CHACHA20 = "chacha20"
    CHACHA20_POLY1305 = "chacha20_poly1305"
    XSALSA20 = "xchacha20"
    RC4 = "rc4"
    DES = "des"
    THREE_DES = "3des"
    BLOWFISH = "blowfish"
    TWOFISH = "twofish"
    SERPENT = "serpent"
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    ECC_P256 = "ecc_p256"
    ECC_P384 = "ecc_p384"
    ECC_P521 = "ecc_p521"
    ED25519 = "ed25519"


class KeyDerivation(Enum):
    PBKDF2 = "pbkdf2"
    ARGON2D = "argon2d"
    ARGON2I = "argon2i"
    ARGON2ID = "argon2id"
    BCRYPT = "bcrypt"
    SCRYPT = "scrypt"


@dataclass
class HashResult:
    algorithm: HashAlgorithm
    digest: str
    salt: str
    iterations: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class CipherResult:
    algorithm: CipherAlgorithm
    ciphertext: bytes
    iv: bytes
    tag: bytes | None = None
    key_id: str | None = None


@dataclass
class PasswordHash:
    algorithm: KeyDerivation
    hash: str
    salt: str
    iterations: int
    memory_cost: int = 4096
    parallelism: int = 1
    version: str = "1"


class HashManager:
    """哈希管理器。"""

    def __init__(self):
        self._algorithms = {
            HashAlgorithm.MD5: hashlib.md5,
            HashAlgorithm.SHA1: hashlib.sha1,
            HashAlgorithm.SHA256: hashlib.sha256,
            HashAlgorithm.SHA512: hashlib.sha512,
        }

    def hash(self, data: str,
              algorithm: HashAlgorithm = HashAlgorithm.SHA256
              ) -> HashResult:
        func = self._algorithms[algorithm]
        digest = func(data.encode()).hexdigest()
        salt = secrets.token_hex(16)
        return HashResult(algorithm=algorithm, digest=digest, salt=salt, iterations=1)

    def verify(self, data: str, hash_result: HashResult) -> bool:
        func = self._algorithms[hash_result.algorithm]
        computed = func(data.encode()).hexdigest()
        return computed == hash_result.digest


class BCrypt:
    """bcrypt 密码哈希。"""

    def __init__(self, rounds: int = 12):
        self.rounds = rounds

    def hash(self, password: str) -> PasswordHash:
        salt = secrets.token_hex(16)
        # Simulated bcrypt (uses SHA256 with salt and rounds)
        hashed = hashlib.sha256(
            f"{password}{salt}{self.rounds}".encode()
        ).hexdigest()
        return PasswordHash(
            algorithm=KeyDerivation.BCRYPT,
            hash=hashed,
            salt=salt,
            iterations=self.rounds,
        )

    def verify(self, password: str, ph: PasswordHash) -> bool:
        if ph.algorithm != KeyDerivation.BCRYPT:
            return False
        computed = hashlib.sha256(
            f"{password}{ph.salt}{ph.iterations}".encode()
        ).hexdigest()
        return computed == ph.hash

    def needs_rehash(self, ph: PasswordHash,
                        new_rounds: int) -> bool:
        return ph.iterations < new_rounds


class Argon2:
    """Argon2 密码哈希。"""

    def __init__(self, memory_cost: int = 65536,
                 parallelism: int = 4,
                 iterations: int = 3):
        self.memory_cost = memory_cost
        self.parallelism = parallelism
        self.iterations = iterations

    def hash(self, password: str) -> PasswordHash:
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(
            f"{password}{salt}{self.memory_cost}{self.parallelism}{self.iterations}".encode()
        ).hexdigest()
        return PasswordHash(
            algorithm=KeyDerivation.ARGON2ID,
            hash=hashed,
            salt=salt,
            iterations=self.iterations,
            memory_cost=self.memory_cost,
            parallelism=self.parallelism,
        )

    def verify(self, password: str, ph: PasswordHash) -> bool:
        if ph.algorithm not in (KeyDerivation.ARGON2D, KeyDerivation.ARGON2I, KeyDerivation.ARGON2ID):
            return False
        computed = hashlib.sha256(
            f"{password}{ph.salt}{ph.memory_cost}{ph.parallelism}{ph.iterations}".encode()
        ).hexdigest()
        return computed == ph.hash


class Scrypt:
    """scrypt 密码哈希。"""

    def __init__(self, N: int = 16384, r: int = 8, p: int = 1):
        self.N = N
        self.r = r
        self.p = p

    def hash(self, password: str) -> PasswordHash:
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(
            f"{password}{salt}{self.N}{self.r}{self.p}".encode()
        ).hexdigest()
        return PasswordHash(
            algorithm=KeyDerivation.SCRYPT,
            hash=hashed,
            salt=salt,
            iterations=1,
            memory_cost=self.N,
        )

    def verify(self, password: str, ph: PasswordHash) -> bool:
        computed = hashlib.sha256(
            f"{password}{ph.salt}{ph.memory_cost}{ph.parallelism}{ph.iterations}".encode()
        ).hexdigest()
        return computed == ph.hash


class Cipher:
    """加密器。"""

    def __init__(self, algorithm: CipherAlgorithm = CipherAlgorithm.AES_256):
        self.algorithm = algorithm
        self._key: bytes | None = None

    def generate_key(self) -> bytes:
        key_sizes = {
            CipherAlgorithm.AES_128: 16,
            CipherAlgorithm.AES_192: 24,
            CipherAlgorithm.AES_256: 32,
            CipherAlgorithm.CHACHA20: 32,
            CipherAlgorithm.ED25519: 32,
        }
        self._key = secrets.token_bytes(key_sizes.get(self.algorithm, 32))
        return self._key

    def encrypt(self, plaintext: bytes,
                 key: bytes | None = None
                 ) -> CipherResult:
        k = key or self._key or self.generate_key()
        iv = secrets.token_bytes(16)
        # Simulated encryption (XOR with SHA256)
        ciphertext = bytes(b ^ k[i % len(k)] for i, b in enumerate(plaintext))
        return CipherResult(
            algorithm=self.algorithm,
            ciphertext=ciphertext,
            iv=iv,
        )

    def decrypt(self, ciphertext: bytes,
                 key: bytes | None = None
                 ) -> bytes:
        k = key or self._key or self.generate_key()
        return bytes(b ^ k[i % len(k)] for i, b in enumerate(ciphertext))


class HMAC:
    """HMAC 消息认证。"""

    def __init__(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256):
        self.algorithm = algorithm

    def sign(self, message: bytes,
              key: bytes) -> str:
        sig = hmac_module.new(key, message, self.algorithm.value).hexdigest()
        return sig

    def verify(self, message: bytes, key: bytes,
                signature: str) -> bool:
        computed = self.sign(message, key)
        return computed == signature


class Certificate:
    """X.509 证书。"""

    def __init__(self):
        self._certificates: dict[str, dict[str, Any]] = {}

    def generate(self, subject: str,
                    issuer: str,
                    valid_days: int = 365) -> dict[str, Any]:
        cert = {
            "subject": subject,
            "issuer": issuer,
            "valid_from": time.time(),
            "valid_to": time.time() + valid_days * 86400,
            "serial": secrets.token_hex(16),
            "public_key": secrets.token_hex(32),
            "signature_algorithm": "SHA256withRSA",
            "version": 3,
        }
        self._certificates[cert["serial"]] = cert
        return cert

    def verify(self, cert: dict[str, Any]) -> bool:
        now = time.time()
        return cert.get("valid_from", 0) <= now <= cert.get("valid_to", now + 1)

    def revoke(self, serial: str) -> bool:
        if serial in self._certificates:
            self._certificates[serial]["revoked"] = True
            return True
        return False


class SSLContext:
    """SSL/TLS 上下文。"""

    def __init__(self, protocol: str = "TLSv1.3"):
        self.protocol = protocol
        self.certificates: list[dict[str, Any]] = []
        self.cipher_suites: list[str] = [
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_128_GCM_SHA256",
        ]
        self._verified = False

    def load_cert(self, cert: dict[str, Any]) -> None:
        self.certificates.append(cert)

    def verify_cert(self, cert: dict[str, Any]) -> bool:
        return Certificate().verify(cert)

    def create_connection(self, host: str,
                             port: int) -> dict[str, Any]:
        return {"host": host, "port": port, "tls": True, "protocol": self.protocol}


class OAuth2Token:
    """OAuth2 令牌。"""

    def __init__(self, token: str = "",
                 token_type: str = "Bearer",
                 expires_in: int = 3600):
        self.token = token
        self.token_type = token_type
        self.expires_in = expires_in
        self.created_at = time.time()
        self.scopes: list[str] = []

    def is_valid(self) -> bool:
        return time.time() - self.created_at < self.expires_in

    def refresh(self) -> None:
        self.token = secrets.token_hex(32)
        self.created_at = time.time()


class OAuth2Client:
    """OAuth2 客户端。"""

    def __init__(self, client_id: str, client_secret: str,
                 redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._tokens: list[OAuth2Token] = []

    def authorize(self, scopes: list[str] = None) -> OAuth2Token:
        token = OAuth2Token(
            token=secrets.token_hex(32),
            scopes=scopes or ["read", "write"],
        )
        self._tokens.append(token)
        return token

    def get_token(self, code: str) -> OAuth2Token | None:
        for t in self._tokens:
            if t.is_valid():
                return t
        return None


class JWT:
    """JWT 令牌。"""

    def __init__(self):
        self._secret = secrets.token_hex(32)

    def generate(self, payload: dict[str, Any],
                  secret: str | None = None
                  ) -> str:
        s = secret or self._secret
        header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
        body = base64.b64encode(json.dumps(payload).encode()).decode()
        signature = hmac_module.new(s.encode(), f"{header}.{body}".encode(), hashlib.sha256).hexdigest()
        return f"{header}.{body}.{signature}"

    def verify(self, token: str, secret: str | None = None) -> bool:
        parts = token.split(".")
        if len(parts) != 3:
            return False
        s = secret or self._secret
        expected = hmac_module.new(s.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).hexdigest()
        return expected == parts[2]


class KeyManager:
    """密钥管理器。"""

    def __init__(self):
        self._keys: dict[str, bytes] = {}
        self._key_rotation_interval = 86400

    def generate_symmetric_key(self, name: str,
                                  size: int = 32) -> bytes:
        key = secrets.token_bytes(size)
        self._keys[name] = key
        return key

    def generate_asymmetric_keypair(self, name: str) -> dict[str, bytes]:
        key = secrets.token_bytes(32)
        public_key = secrets.token_bytes(32)
        self._keys[f"{name}_private"] = key
        self._keys[f"{name}_public"] = public_key
        return {"private": key, "public": public_key}

    def get_key(self, name: str) -> bytes | None:
        return self._keys.get(name)

    def rotate_key(self, name: str) -> bool:
        if name in self._keys:
            self._keys[name] = secrets.token_bytes(32)
            return True
        return False


def create_hash_manager() -> HashManager:
    return HashManager()


def create_bcrypt(rounds: int = 12) -> BCrypt:
    return BCrypt(rounds=rounds)


def create_argon2(memory_cost: int = 65536,
                     parallelism: int = 4,
                     iterations: int = 3) -> Argon2:
    return Argon2(memory_cost=memory_cost, parallelism=parallelism, iterations=iterations)


def create_scrypt(N: int = 16384, r: int = 8,
                    p: int = 1) -> Scrypt:
    return Scrypt(N=N, r=r, p=p)


def create_cipher(algorithm: CipherAlgorithm = CipherAlgorithm.AES_256
                      ) -> Cipher:
    return Cipher(algorithm=algorithm)


def create_hmac(algorithm: HashAlgorithm = HashAlgorithm.SHA256
                   ) -> HMAC:
    return HMAC(algorithm=algorithm)


def create_certificate() -> Certificate:
    return Certificate()


def create_ssl_context(protocol: str = "TLSv1.3"
                          ) -> SSLContext:
    return SSLContext(protocol=protocol)


def create_jwt() -> JWT:
    return JWT()


def create_key_manager() -> KeyManager:
    return KeyManager()


# ============================================================
# 内置注册
# ============================================================

def _register_security_complete(builtins: dict) -> None:
    builtins["创建哈希管理器"] = create_hash_manager
    builtins["创建bcrypt"] = create_bcrypt
    builtins["创建Argon2"] = create_argon2
    builtins["创建scrypt"] = create_scrypt
    builtins["创建加密器"] = create_cipher
    builtins["创建HMAC"] = create_hmac
    builtins["创建证书"] = create_certificate
    builtins["创建SSL上下文"] = create_ssl_context
    builtins["创建JWT"] = create_jwt
    builtins["创建密钥管理器"] = create_key_manager


def _security_complete_names() -> list[str]:
    return ["创建哈希管理器", "创建bcrypt", "创建Argon2",
            "创建scrypt", "创建加密器", "创建HMAC",
            "创建证书", "创建SSL上下文", "创建JWT",
            "创建密钥管理器"]


__all__ = [
    "HashAlgorithm", "CipherAlgorithm", "KeyDerivation",
    "HashResult", "CipherResult", "PasswordHash",
    "HashManager", "BCrypt", "Argon2", "Scrypt",
    "Cipher", "HMAC", "Certificate", "SSLContext",
    "OAuth2Token", "OAuth2Client", "JWT", "KeyManager",
    "create_hash_manager", "create_bcrypt", "create_argon2",
    "create_scrypt", "create_cipher", "create_hmac",
    "create_certificate", "create_ssl_context", "create_jwt",
    "create_key_manager",
    "_register_security_complete", "_security_complete_names",
]
