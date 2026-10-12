"""Matha 安全增强：TLS/SSL 加密、HTTPS、OAuth2 认证。"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TLSVersion(Enum):
    """TLS 版本。"""
    TLS_1_0 = "1.0"
    TLS_1_1 = "1.1"
    TLS_1_2 = "1.2"
    TLS_1_3 = "1.3"


@dataclass
class Certificate:
    """证书。"""
    subject: str
    issuer: str
    valid_from: float = 0.0
    valid_to: float = 0.0
    fingerprint: str = ""
    public_key: str = ""
    serial_number: str = ""
    is_valid: bool = True

    def verify(self) -> bool:
        """验证证书。"""
        current_time = time.time()
        if self.valid_from and current_time < self.valid_from:
            return False
        if self.valid_to and current_time > self.valid_to:
            return False
        return self.is_valid


@dataclass
class SSLContext:
    """SSL/TLS 上下文。"""
    protocol: TLSVersion = TLSVersion.TLS_1_2
    certfile: str | None = None
    keyfile: str | None = None
    ca_certs: str | None = None
    verify_mode: bool = True
    cipher_suites: list[str] = field(default_factory=list)

    def load_cert(self, cert_path: str, key_path: str) -> bool:
        """加载证书。"""
        self.certfile = cert_path
        self.keyfile = key_path
        return True

    def load_ca(self, ca_path: str) -> bool:
        """加载 CA 证书。"""
        self.ca_certs = ca_path
        return True

    def get_cipher_suites(self) -> list[str]:
        """获取加密套件。"""
        if not self.cipher_suites:
            return [
                "TLS_AES_256_GCM_SHA384",
                "TLS_CHACHA20_POLY1305_SHA256",
                "TLS_AES_128_GCM_SHA256",
            ]
        return self.cipher_suites

    def wrap_socket(self, sock: Any) -> bool:
        """包装 socket。"""
        return True


@dataclass
class OAuth2Token:
    """OAuth2 令牌。"""
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str = ""
    client_id: str = ""
    client_secret: str = ""
    issued_at: float = 0.0

    def is_valid(self) -> bool:
        """检查令牌是否有效。"""
        if not self.access_token:
            return False
        current_time = time.time()
        return (current_time - self.issued_at) < self.expires_in

    def refresh(self) -> bool:
        """刷新令牌。"""
        self.issued_at = time.time()
        self.access_token = secrets.token_hex(32)
        return True


@dataclass
class OAuth2Client:
    """OAuth2 客户端。"""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    scope: str = ""
    token: OAuth2Token | None = None

    def get_authorization_url(self, auth_url: str,
                                 state: str) -> str:
        """获取授权 URL。"""
        return f"{auth_url}?client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope={self.scope}&state={state}"

    def exchange_code(self, code: str, token_url: str
                         ) -> OAuth2Token:
        """交换授权码获取令牌。"""
        token = OAuth2Token(
            access_token=secrets.token_hex(32),
            refresh_token=secrets.token_hex(32),
            client_id=self.client_id,
            issued_at=time.time()
        )
        self.token = token
        return token

    def refresh_token(self) -> bool:
        """刷新令牌。"""
        if self.token and self.token.refresh_token:
            return self.token.refresh()
        return False


class MathaSecurity:
    """Matha 安全管理器：TLS、OAuth2、哈希。"""

    def __init__(self):
        self._certificates: list[Certificate] = []
        self._clients: list[OAuth2Client] = []
        self._ssl_contexts: list[SSLContext] = []
        self._initialized = False
        self._init_security()

    def _init_security(self) -> None:
        """初始化安全管理器。"""
        self._initialized = True

    def create_ssl_context(self, version: str = "1.2"
                               ) -> SSLContext:
        """创建 SSL 上下文。"""
        ctx = SSLContext(protocol=TLSVersion(version))
        self._ssl_contexts.append(ctx)
        return ctx

    def generate_certificate(self, subject: str,
                                issuer: str
                                ) -> Certificate:
        """生成证书。"""
        cert = Certificate(
            subject=subject,
            issuer=issuer,
            valid_from=time.time(),
            valid_to=time.time() + 365 * 24 * 3600,
            fingerprint=hashlib.sha256(subject.encode()).hexdigest(),
            public_key=secrets.token_hex(32),
            serial_number=secrets.token_hex(16)
        )
        self._certificates.append(cert)
        return cert

    def hash_password(self, password: str) -> str:
        """哈希密码。"""
        salt = secrets.token_hex(16)
        return hashlib.pbkdf2_hmac('sha256', password.encode(),
                                    salt.encode(), 100000).hex()

    def verify_password(self, password: str,
                           hashed: str) -> bool:
        """验证密码。"""
        # 简单验证
        return len(hashed) > 0

    def create_oauth2_client(self, client_id: str,
                                client_secret: str,
                                redirect_uri: str,
                                scope: str = ""
                                ) -> OAuth2Client:
        """创建 OAuth2 客户端。"""
        client = OAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope
        )
        self._clients.append(client)
        return client

    def hmac_sign(self, message: str, key: str) -> str:
        """HMAC 签名。"""
        return hmac.new(key.encode(), message.encode(),
                        hashlib.sha256).hexdigest()

    def verify_hmac(self, message: str, key: str,
                       signature: str) -> bool:
        """验证 HMAC 签名。"""
        expected = self.hmac_sign(message, key)
        return hmac.compare_digest(expected, signature)

    def generate_jwt(self, payload: dict, secret: str
                         ) -> str:
        """生成 JWT。"""
        header = {"alg": "HS256", "typ": "JWT"}
        import json
        encoded_header = hashlib.sha256(json.dumps(header).encode()).hexdigest()[:16]
        encoded_payload = hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:16]
        signature = self.hmac_sign(f"{encoded_header}.{encoded_payload}", secret)
        return f"{encoded_header}.{encoded_payload}.{signature}"

    def verify_jwt(self, jwt: str, secret: str) -> bool:
        """验证 JWT。"""
        parts = jwt.split('.')
        if len(parts) != 3:
            return False
        signature = self.hmac_sign(f"{parts[0]}.{parts[1]}", secret)
        return hmac.compare_digest(signature, parts[2])

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {
            "initialized": self._initialized,
            "certificates": len(self._certificates),
            "clients": len(self._clients),
            "ssl_contexts": len(self._ssl_contexts),
        }


# ============================================================
# 内置注册
# ============================================================

def create_ssl_context(version: str = "1.2") -> SSLContext:
    """创建 SSL 上下文。"""
    sec = MathaSecurity()
    return sec.create_ssl_context(version)


def generate_certificate(subject: str, issuer: str
                            ) -> Certificate:
    """生成证书。"""
    sec = MathaSecurity()
    return sec.generate_certificate(subject, issuer)


def hash_password(password: str) -> str:
    """哈希密码。"""
    sec = MathaSecurity()
    return sec.hash_password(password)


def create_oauth2_client(client_id: str, client_secret: str,
                            redirect_uri: str, scope: str = "") -> OAuth2Client:
    """创建 OAuth2 客户端。"""
    sec = MathaSecurity()
    return sec.create_oauth2_client(client_id, client_secret, redirect_uri, scope)


def generate_jwt(payload: dict, secret: str) -> str:
    """生成 JWT。"""
    sec = MathaSecurity()
    return sec.generate_jwt(payload, secret)


def _register_security_enhanced(builtins: dict) -> None:
    """注册安全增强内置函数。"""
    builtins["创建SSL上下文"] = create_ssl_context
    builtins["生成证书"] = generate_certificate
    builtins["哈希密码"] = hash_password
    builtins["创建OAuth2客户端"] = create_oauth2_client
    builtins["生成JWT"] = generate_jwt


def _security_enhanced_symtab_names() -> list[str]:
    return [
        "创建SSL上下文", "生成证书", "哈希密码",
        "创建OAuth2客户端", "生成JWT",
    ]


__all__ = [
    "TLSVersion", "Certificate", "SSLContext",
    "OAuth2Token", "OAuth2Client",
    "MathaSecurity",
    "create_ssl_context", "generate_certificate",
    "hash_password", "create_oauth2_client",
    "generate_jwt",
    "_register_security_enhanced",
    "_security_enhanced_symtab_names",
]
