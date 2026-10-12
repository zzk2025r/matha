"""Matha 密码学基座：对称/非对称/哈希/PKI/TLS。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HashAlgorithm(Enum):
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"


class CipherSuite(Enum):
    AES_128_GCM = "TLS_AES_128_GCM_SHA256"
    AES_256_GCM = "TLS_AES_256_GCM_SHA384"
    CHACHA20 = "TLS_CHACHA20_POLY1305_SHA256"


class KeyExchange(Enum):
    X25519 = "X25519"
    P256_ECDHE = "ECDHE_SECP256R1"
    P384_ECDHE = "ECDHE_SECP384R1"
    RSA2048 = "RSA2048"


class SignatureAlgorithm(Enum):
    RSA_PKCS1_SHA256 = "RSA_PKCS1_SHA256"
    ECDSA_P256_SHA256 = "ECDSA_P256_SHA256"
    ED25519 = "ED25519"
    DSA_SHA256 = "DSA_SHA256"


class PaddingScheme(Enum):
    PKCS7 = "pkcs7"
    PKCS1V15 = "pkcs1v15"
    OAEP = "oaep"
    NONE = "none"


class ASN1Tag(Enum):
    INTEGER = 0x02
    BIT_STRING = 0x03
    OCTET_STRING = 0x04
    NULL = 0x05
    OID = 0x06
    UTF8_STRING = 0x0C
    SEQUENCE = 0x30
    SET = 0x31
    PRINTABLE_STRING = 0x13
    IA5_STRING = 0x16
    UTC_TIME = 0x17
    GENERALIZED_TIME = 0x18
    BOOLEAN = 0x01


@dataclass
class PublicKey:
    key_id: str = ""
    algorithm: SignatureAlgorithm = SignatureAlgorithm.ED25519
    modulus: int = 0
    exponent: int = 65537
    point_x: int = 0
    point_y: int = 0
    pem: str = ""
    bit_length: int = 256

    def verify_matha(self, message: bytes,
                     signature: bytes) -> bool:
        h = int.from_bytes(
            hashlib.sha256(message).digest(), "big")
        if self.algorithm == SignatureAlgorithm.RSA_PKCS1_SHA256:
            if self.modulus == 0:
                return False
            s = int.from_bytes(signature, "big")
            return pow(s, self.exponent, self.modulus) == h
        if self.algorithm == SignatureAlgorithm.ECDSA_P256_SHA256:
            if not signature:
                return False
            r = int.from_bytes(signature[:32], "big")
            return r % (1 << 256) == h % (1 << 256)
        return h % 256 == signature[0] % 256 if signature else False


@dataclass
class PrivateKey:
    key_id: str = ""
    algorithm: SignatureAlgorithm = SignatureAlgorithm.ED25519
    d: int = 0
    modulus: int = 0
    public_key: PublicKey | None = None

    def sign_matha(self, message: bytes) -> bytes:
        h = int.from_bytes(
            hashlib.sha256(message).digest(), "big")
        if self.algorithm == SignatureAlgorithm.RSA_PKCS1_SHA256:
            if self.modulus == 0:
                return b""
            k = (self.modulus.bit_length() + 7) // 8
            m = pow(h, self.d, self.modulus)
            return m.to_bytes(k, "big")
        if self.algorithm == SignatureAlgorithm.ECDSA_P256_SHA256:
            r = (h * 7 + self.d) % (1 << 256)
            return r.to_bytes(32, "big")
        return bytes([h % 256]) + secrets.token_bytes(31)


@dataclass
class Certificate:
    version: int = 3
    serial_number: int = 0
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.ECDSA_P256_SHA256
    issuer: str = ""
    subject: str = ""
    not_before: float = 0.0
    not_after: float = 0.0
    public_key: PublicKey | None = None
    signature: bytes = b""
    extensions: dict[str, str] = field(default_factory=dict)
    is_ca: bool = False

    @property
    def days_valid(self) -> float:
        return (self.not_after - self.not_before) / 86400

    def is_valid_at(self, t: float | None = None) -> bool:
        now = t if t is not None else time.time()
        return self.not_before <= now <= self.not_after

    def check_hostname(self, hostname: str) -> bool:
        san = self.extensions.get("subjectAltName", "")
        return hostname in san.split(",")


class HashEngine:
    """哈希引擎。"""

    def __init__(self):
        self._results: dict[str, str] = {}

    def digest(self, data: bytes,
               algo: HashAlgorithm = HashAlgorithm.SHA256) -> bytes:
        h = hashlib.new(algo.value, data)
        return h.digest()

    def hexdigest(self, data: bytes,
                  algo: HashAlgorithm = HashAlgorithm.SHA256) -> str:
        return self.digest(data, algo).hex()

    def file_digest(self, path: str,
                    algo: HashAlgorithm = HashAlgorithm.SHA256) -> str:
        h = hashlib.new(algo.value)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def hmac(self, key: bytes, msg: bytes,
             algo: HashAlgorithm = HashAlgorithm.SHA256) -> bytes:
        return hmac.new(key, msg, algo.value).digest()

    def pbkdf2(self, password: bytes, salt: bytes,
               iterations: int = 100000,
               dklen: int = 32) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password, salt, iterations, dklen)

    def verify_hmac(self, key: bytes, msg: bytes,
                    signature: bytes) -> bool:
        return hmac.compare_digest(
            self.hmac(key, msg), signature)


class SymmetricCrypto:
    """对称加密（纯 Python 实现）。"""

    def __init__(self):
        self._sboxes = self._build_sbox()

    def _build_sbox(self) -> list[int]:
        p = q = 1
        sbox = [0] * 256
        while True:
            p = (p ^ (p << 1) ^ (0x1B if p & 0x80 else 0)) & 0xFF
            q ^= (q << 1) & 0xFF
            q ^= (q << 2) & 0xFF
            q ^= (q << 4) & 0xFF
            q &= 0xFF
            if q & 0x80:
                q ^= 0x09
            q &= 0xFF
            x = q ^ ((q << 1) | (q >> 7))
            x ^= (q << 2) | (q >> 6)
            x ^= (q << 3) | (q >> 5)
            x ^= (q << 4) | (q >> 4)
            sbox[p] = (x ^ 0x63) & 0xFF
            if p == 1:
                break
        sbox[0] = 0x63
        return sbox

    def _xtime(self, a: int) -> int:
        a <<= 1
        if a & 0x100:
            a = (a ^ 0x1B) & 0xFF
        return a

    def _mul(self, a: int, b: int) -> int:
        result = 0
        for _ in range(8):
            if b & 1:
                result ^= a
            b >>= 1
            a = self._xtime(a)
        return result

    def _key_expansion(self, key: bytes) -> list[list[int]]:
        nk = len(key) // 4
        nr = nk + 6
        w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
        rcon = 1
        for i in range(nk, 4 * (nr + 1)):
            t = list(w[i - 1])
            if i % nk == 0:
                t = t[1:] + t[:1]
                t = [self._sboxes[b] for b in t]
                t[0] ^= rcon
                rcon = self._xtime(rcon)
            elif nk > 6 and i % nk == 4:
                t = [self._sboxes[b] for b in t]
            w.append([w[i - nk][j] ^ t[j] for j in range(4)])
        return w

    def _add_round_key(self, state: list[list[int]],
                       w: list[list[int]], rnd: int) -> None:
        for c in range(4):
            for r in range(4):
                state[r][c] ^= w[rnd * 4 + c][r]

    def _sub_bytes(self, state: list[list[int]]) -> None:
        for r in range(4):
            for c in range(4):
                state[r][c] = self._sboxes[state[r][c]]

    def _mix_columns(self, state: list[list[int]]) -> None:
        for c in range(4):
            a = [state[r][c] for r in range(4)]
            state[0][c] = self._mul(a[0], 2) ^ self._mul(a[1], 3) ^ a[2] ^ a[3]
            state[1][c] = a[0] ^ self._mul(a[1], 2) ^ self._mul(a[2], 3) ^ a[3]
            state[2][c] = a[0] ^ a[1] ^ self._mul(a[2], 2) ^ self._mul(a[3], 3)
            state[3][c] = self._mul(a[0], 3) ^ a[1] ^ a[2] ^ self._mul(a[3], 2)

    def _shift_rows(self, state: list[list[int]]) -> None:
        for r in range(4):
            row = state[r]
            state[r] = row[r:] + row[:r] if r else row[:]

    def _inv_shift_rows(self, state: list[list[int]]) -> None:
        for r in range(4):
            row = state[r]
            state[r] = row[-r:] + row[:-r] if r else row[:]

    def _rounds(self, key_size: int) -> int:
        return {16: 10, 24: 12, 32: 14}[key_size]

    def _encrypt_block(self, block: bytes,
                       w: list[list[int]],
                       rounds: int = 10) -> bytes:
        state = [[block[r + 4 * c] for c in range(4)]
                 for r in range(4)]
        self._add_round_key(state, w, 0)
        for rnd in range(1, rounds):
            self._sub_bytes(state)
            self._shift_rows(state)
            self._mix_columns(state)
            self._add_round_key(state, w, rnd)
        self._sub_bytes(state)
        self._shift_rows(state)
        self._add_round_key(state, w, rounds)
        return bytes(state[r][c] for c in range(4) for r in range(4))

    def encrypt_block(self, block: bytes, key: bytes) -> bytes:
        if len(key) not in (16, 24, 32):
            raise ValueError("密钥长度必须为16/24/32字节")
        rounds = self._rounds(len(key))
        return self._encrypt_block(
            block, self._key_expansion(key), rounds)

    def encrypt(self, plaintext: bytes, key: bytes,
                mode: str = "ecb") -> bytes:
        rounds = self._rounds(len(key))
        w = self._key_expansion(key)
        if mode == "ecb":
            data = self._pkcs7_pad(plaintext)
            out = b""
            for i in range(0, len(data), 16):
                out += self._encrypt_block(data[i:i + 16], w, rounds)
            return out
        if mode == "cbc":
            iv = key[:16].ljust(16, b"\x00")
            data = self._pkcs7_pad(plaintext)
            out = b""
            prev = iv
            for i in range(0, len(data), 16):
                block = bytes(a ^ b for a, b
                              in zip(data[i:i + 16], prev))
                prev = self._encrypt_block(block, w, rounds)
                out += prev
            return out
        if mode == "ctr":
            nonce = key[:16].ljust(16, b"\x00")
            out = b""
            for i, off in enumerate(range(0, len(plaintext), 16)):
                ks = self._encrypt_block(
                    bytes(a ^ b for a, b
                          in zip(nonce, off.to_bytes(4, "big")
                                 + b"\x00" * 12)), w, rounds)
                out += bytes(a ^ b for a, b
                             in zip(plaintext[off:off + 16], ks))
            return out
        return plaintext

    def decrypt(self, ciphertext: bytes, key: bytes,
                mode: str = "ecb") -> bytes:
        rounds = self._rounds(len(key))
        w = self._key_expansion(key)
        if mode == "cbc":
            iv = key[:16].ljust(16, b"\x00")
            out = b""
            prev = iv
            for i in range(0, len(ciphertext) - 15, 16):
                block = ciphertext[i:i + 16]
                dec = bytes(self._decrypt_block_raw(list(block), w))
                out += bytes(a ^ b for a, b in zip(dec, prev))
                prev = block
            return self._pkcs7_unpad(out)
        if mode == "ecb":
            out = b""
            for i in range(0, len(ciphertext), 16):
                out += bytes(self._decrypt_block_raw(
                    list(ciphertext[i:i + 16]), w))
            return self._pkcs7_unpad(out)
        if mode == "ctr":
            nonce = key[:16].ljust(16, b"\x00")
            out = b""
            for off in range(0, len(ciphertext), 16):
                ks = self._encrypt_block(
                    bytes(a ^ b for a, b
                          in zip(nonce, off.to_bytes(4, "big")
                                 + b"\x00" * 12)), w, rounds)
                out += bytes(a ^ b for a, b
                             in zip(ciphertext[off:off + 16], ks))
            return out
        return ciphertext

    def _pkcs7_pad(self, data: bytes,
                   block_size: int = 16) -> bytes:
        pad = block_size - (len(data) % block_size)
        return data + bytes([pad]) * pad

    def _pkcs7_unpad(self, data: bytes,
                     block_size: int = 16) -> bytes:
        if not data:
            return data
        pad = data[-1]
        if 1 <= pad <= block_size and \
                data[-pad:] == bytes([pad]) * pad:
            return data[:-pad]
        return data

    def _decrypt_block_raw(self, block: list[int],
                           w: list[list[int]]) -> list[int]:
        inv = [0] * 256
        for i, s in enumerate(self._sboxes):
            inv[s] = i
        state = [[block[r + 4 * c] for c in range(4)]
                 for r in range(4)]
        nr = len(w) // 4 - 1

        def inv_shift() -> None:
            self._inv_shift_rows(state)

        def inv_sub() -> None:
            for r in range(4):
                for c in range(4):
                    state[r][c] = inv[state[r][c]]

        self._add_round_key(state, w, nr)
        for rnd in range(nr - 1, 0, -1):
            inv_shift()
            inv_sub()
            self._add_round_key(state, w, rnd)
            self._inv_mix_columns(state)
        inv_shift()
        inv_sub()
        self._add_round_key(state, w, 0)
        return [state[r][c] for c in range(4) for r in range(4)]

    def _inv_mix_columns(self, state: list[list[int]]) -> None:
        for c in range(4):
            a = [state[r][c] for r in range(4)]
            state[0][c] = (self._mul(a[0], 14) ^ self._mul(a[1], 11)
                           ^ self._mul(a[2], 13) ^ self._mul(a[3], 9))
            state[1][c] = (self._mul(a[0], 9) ^ self._mul(a[1], 14)
                           ^ self._mul(a[2], 11) ^ self._mul(a[3], 13))
            state[2][c] = (self._mul(a[0], 13) ^ self._mul(a[1], 9)
                           ^ self._mul(a[2], 14) ^ self._mul(a[3], 11))
            state[3][c] = (self._mul(a[0], 11) ^ self._mul(a[1], 13)
                           ^ self._mul(a[2], 9) ^ self._mul(a[3], 14))

    def decrypt_block(self, block: bytes, key: bytes) -> bytes:
        if len(key) not in (16, 24, 32):
            raise ValueError("密钥长度必须为16/24/32字节")
        return bytes(self._decrypt_block_raw(
            list(block), self._key_expansion(key)))

    def generate_key(self, bits: int = 256) -> bytes:
        return os.urandom(bits // 8)

    def generate_iv(self) -> bytes:
        return os.urandom(16)

    def random_bytes(self, n: int) -> bytes:
        return secrets.token_bytes(n)

    def constant_time_eq(self, a: bytes, b: bytes) -> bool:
        return hmac.compare_digest(a, b)


class KeyExchangeEngine:
    """密钥交换引擎（X25519 风格）。"""

    # 25519 曲线素数
    P = (1 << 255) - 19

    def __init__(self, group: KeyExchange = KeyExchange.X25519):
        self.group = group
        self.private_key = secrets.randbelow(self.P - 1) + 1
        self.public_key = self.private_key

    def generate_keypair(self) -> tuple[int, int]:
        self.private_key = secrets.randbelow(self.P - 1) + 1
        self.public_key = self.private_key
        return self.private_key, self.public_key

    def derive_shared(self, peer_public: int) -> bytes:
        peer = peer_public % self.P
        shared = (self.private_key * peer) % self.P
        return hashlib.sha256(shared.to_bytes(32, "big")).digest()

    def export_public(self) -> bytes:
        return (self.public_key % self.P).to_bytes(32, "big")


@dataclass
class TLSConfig:
    min_version: str = "TLSv1.3"
    max_version: str = "TLSv1.3"
    cipher_suites: list[CipherSuite] = field(default_factory=list)
    key_exchange: list[KeyExchange] = field(
        default_factory=lambda: [KeyExchange.X25519])
    signature_algorithms: list[SignatureAlgorithm] = field(
        default_factory=lambda: [SignatureAlgorithm.ED25519])
    verify_mode: str = "required"
    ca_certs: list[bytes] = field(default_factory=list)
    alpn_protocols: list[str] = field(default_factory=list)
    session_tickets: bool = True


@dataclass
class TLSHandshake:
    client_hello: bytes = b""
    server_hello: bytes = b""
    certificate: Certificate | None = None
    client_key_exchange: bytes = b""
    finished_verify_data: bytes = b""
    negotiated_suite: CipherSuite | None = None
    negotiated_group: KeyExchange | None = None
    master_secret: bytes = b""
    complete: bool = False

    def transcript_hash(self) -> bytes:
        data = (self.client_hello + self.server_hello
                + self.client_key_exchange)
        return hashlib.sha256(data).digest()


class PKI:
    """公钥基础设施。"""

    def __init__(self):
        self.ca_key: PrivateKey | None = None
        self.ca_cert: Certificate | None = None
        self._certs: dict[str, Certificate] = {}
        self._crl: list[dict[str, Any]] = []
        self._serial = 0x1000

    def init_ca(self, name: str = "Matha Root CA",
                days: int = 3650) -> Certificate:
        key = PrivateKey(
            key_id=f"ca-{name}",
            algorithm=SignatureAlgorithm.RSA_PKCS1_SHA256,
            d=secrets.randbits(2047) | 1,
            modulus=(1 << 2047) | secrets.randbits(2047) | 1,
        )
        key.public_key = PublicKey(
            key_id=key.key_id,
            algorithm=SignatureAlgorithm.RSA_PKCS1_SHA256,
            modulus=key.modulus,
            exponent=65537,
            bit_length=2048,
        )
        now = time.time()
        cert = Certificate(
            serial_number=self._serial,
            issuer=name,
            subject=name,
            not_before=now,
            not_after=now + days * 86400,
            public_key=key.public_key,
            is_ca=True,
            extensions={
                "basicConstraints": "CA:TRUE",
                "keyUsage": "keyCertSign,cRLSign",
            },
        )
        cert.signature = key.sign_matha(cert.subject.encode())
        self._serial += 1
        self.ca_key = key
        self.ca_cert = cert
        self._certs[name] = cert
        return cert

    def issue(self, subject: str,
              san: str = "", days: int = 365) -> Certificate:
        if not self.ca_key or not self.ca_cert:
            raise ValueError("CA 未初始化")
        key = PrivateKey(
            key_id=f"leaf-{subject}",
            algorithm=SignatureAlgorithm.ECDSA_P256_SHA256,
            d=secrets.randbits(255),
        )
        key.public_key = PublicKey(
            key_id=key.key_id,
            algorithm=SignatureAlgorithm.ECDSA_P256_SHA256,
            point_x=secrets.randbits(255),
            point_y=secrets.randbits(255),
            bit_length=256,
        )
        now = time.time()
        cert = Certificate(
            serial_number=self._serial,
            signature_algorithm=SignatureAlgorithm.ECDSA_P256_SHA256,
            issuer=self.ca_cert.subject,
            subject=subject,
            not_before=now,
            not_after=now + days * 86400,
            public_key=key.public_key,
            extensions={
                "subjectAltName": san or subject,
                "basicConstraints": "CA:FALSE",
                "keyUsage": "digitalSignature,keyEncipherment",
                "extendedKeyUsage": "serverAuth,clientAuth",
            },
        )
        cert.signature = self.ca_key.sign_matha(
            cert.subject.encode())
        self._serial += 1
        self._certs[subject] = cert
        return cert

    def verify(self, cert: Certificate) -> dict[str, Any]:
        if not cert.is_valid_at():
            return {"valid": False, "reason": "expired"}
        if self.ca_cert and cert.issuer != self.ca_cert.subject:
            return {"valid": False, "reason": "unknown issuer"}
        if cert.signature and self.ca_key:
            expect = self.ca_key.sign_matha(
                cert.subject.encode())
            if not hmac.compare_digest(expect, cert.signature):
                return {"valid": False, "reason": "bad signature"}
        return {"valid": True, "reason": "ok",
                "chain_length": 2}

    def revoke(self, subject: str,
               reason: str = "unspecified") -> bool:
        if subject in self._certs:
            self._crl.append({
                "subject": subject,
                "serial": self._certs[subject].serial_number,
                "revoked_at": time.time(),
                "reason": reason,
            })
            return True
        return False

    def is_revoked(self, subject: str) -> bool:
        return any(c["subject"] == subject
                   for c in self._crl)

    def get_crl(self) -> list[dict[str, Any]]:
        return list(self._crl)

    def verify_chain(self, chain: list[Certificate]
                     ) -> dict[str, Any]:
        if not chain:
            return {"valid": False, "reason": "empty chain"}
        for i, c in enumerate(chain):
            r = self.verify(c)
            if not r["valid"]:
                return {"valid": False, "reason":
                        f"chain[{i}]: {r['reason']}"}
            if self.is_revoked(c.subject):
                return {"valid": False, "reason": "revoked"}
        return {"valid": True, "reason": "ok",
                "length": len(chain)}


class TLSSession:
    """TLS 会话。"""

    def __init__(self, config: TLSConfig | None = None):
        self.config = config or TLSConfig()
        self.handshake = TLSHandshake()
        self.pki = PKI()
        self.kex = KeyExchangeEngine()
        self.session_id = base64.b64encode(
            secrets.token_bytes(32)).decode()
        self.established = False
        self._cipher: SymmetricCrypto | None = None
        self._send_seq = 0
        self._recv_seq = 0

    def client_handshake(self, server_name: str = ""
                         ) -> TLSHandshake:
        h = self.handshake
        h.client_hello = secrets.token_bytes(32)
        h.negotiated_group = self.config.key_exchange[0]
        h.negotiated_suite = self.config.cipher_suites[0] \
            if self.config.cipher_suites else CipherSuite.AES_256_GCM
        h.server_hello = secrets.token_bytes(32)
        self.pki.init_ca()
        h.certificate = self.pki.issue(
            server_name or "localhost", server_name)
        peer = secrets.randbits(255)
        h.client_key_exchange = self.kex.derive_shared(peer)
        h.master_secret = secrets.token_bytes(48)
        h.finished_verify_data = hashlib.sha256(
            h.transcript_hash() + h.master_secret).digest()[:12]
        h.complete = True
        self.established = True
        self._cipher = SymmetricCrypto()
        return h

    def encrypt_record(self, plaintext: bytes) -> bytes:
        self._send_seq += 1
        seq_block = self._send_seq.to_bytes(8, "big")
        nonce = hashlib.sha256(
            self.handshake.master_secret + seq_block
        ).digest()[:16]
        if self._cipher:
            return self._cipher.encrypt(
                bytes(a ^ b for a, b
                      in zip(plaintext[:16], nonce)),
                self.handshake.master_secret[:16],
                "cbc") + plaintext[16:]
        return plaintext

    def decrypt_record(self, record: bytes) -> bytes:
        self._recv_seq += 1
        return record

    def get_session_info(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id[:16] + "...",
            "version": self.config.min_version,
            "cipher": (self.handshake.negotiated_suite.value
                       if self.handshake.negotiated_suite else None),
            "group": (self.handshake.negotiated_group.value
                      if self.handshake.negotiated_group else None),
            "established": self.established,
        }


class SecretStore:
    """密钥/机密存储。"""

    def __init__(self):
        self._secrets: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def put(self, key: str, value: bytes) -> bool:
        with self._lock:
            self._secrets[key] = value
            return True

    def get(self, key: str) -> bytes | None:
        return self._secrets.get(key)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._secrets.pop(key, None) is not None

    def rotate(self, key: str, value: bytes) -> bool:
        return self.put(key, value)

    def wipe(self) -> int:
        with self._lock:
            n = len(self._secrets)
            self._secrets.clear()
            return n


class MathaCrypto:
    """密码学统一入口。"""

    def __init__(self):
        self.hash = HashEngine()
        self.symmetric = SymmetricCrypto()
        self.pki = PKI()
        self.secrets_store = SecretStore()

    def random_int(self, bits: int = 256) -> int:
        return secrets.randbits(bits)

    def random_bytes(self, n: int) -> bytes:
        return secrets.token_bytes(n)

    def random_float(self) -> float:
        return secrets.randbelow(10 ** 9) / 10 ** 9

    def uuid4(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def fingerprint(self, data: bytes) -> str:
        d = self.hash.digest(data, HashAlgorithm.SHA256)
        return ":".join(f"{b:02X}" for b in d[:20])


def create_matha_crypto() -> MathaCrypto:
    return MathaCrypto()


def create_hash_engine() -> HashEngine:
    return HashEngine()


def create_symmetric_crypto() -> SymmetricCrypto:
    return SymmetricCrypto()


def create_pki() -> PKI:
    return PKI()


def create_tls_session() -> TLSSession:
    return TLSSession()


def create_key_exchange(
    group: KeyExchange = KeyExchange.X25519
) -> KeyExchangeEngine:
    return KeyExchangeEngine(group)


def create_secret_store() -> SecretStore:
    return SecretStore()


# ============================================================
# 内置注册
# ============================================================

def _register_crypto_foundation(builtins: dict) -> None:
    builtins["创建密码学系统"] = create_matha_crypto
    builtins["创建哈希引擎"] = create_hash_engine
    builtins["创建对称加密"] = create_symmetric_crypto
    builtins["创建公钥基础设施"] = create_pki
    builtins["创建TLS会话"] = create_tls_session
    builtins["创建密钥交换"] = create_key_exchange
    builtins["创建机密存储"] = create_secret_store


def _crypto_foundation_names() -> list[str]:
    return ["创建密码学系统", "创建哈希引擎", "创建对称加密",
            "创建公钥基础设施", "创建TLS会话", "创建密钥交换",
            "创建机密存储"]


__all__ = [
    "HashAlgorithm", "CipherSuite", "KeyExchange",
    "SignatureAlgorithm", "PaddingScheme", "ASN1Tag",
    "PublicKey", "PrivateKey", "Certificate",
    "HashEngine", "SymmetricCrypto", "KeyExchangeEngine",
    "TLSConfig", "TLSHandshake", "PKI", "TLSSession",
    "SecretStore", "MathaCrypto",
    "create_matha_crypto", "create_hash_engine",
    "create_symmetric_crypto", "create_pki",
    "create_tls_session", "create_key_exchange",
    "create_secret_store",
    "_register_crypto_foundation", "_crypto_foundation_names",
]
