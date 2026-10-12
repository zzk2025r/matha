"""极客文化与灰产边缘：CTF、漏洞研究、安全审计、渗透测试。

本模块仅用于授权的防御性安全研究：二进制安全检查、CTF 解题、
渗透测试辅助与安全审计。所有载荷生成均为受控的模板化输出。
"""
from __future__ import annotations

import base64
import binascii
import collections
import hashlib
import re
import string
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

MAX_PAYLOAD_SIZE = 4096
STACK_CANARY_LEN = 8
ASLR_BITS = 28

BANNER = "defense-research only"


class Severity(Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ArchType(Enum):
    X86_32 = "x86_32"
    X86_64 = "x86_64"
    ARM_32 = "arm_32"
    ARM_64 = "arm_64"
    MIPS = "mips"
    RISC_V = "risc_v"


class FindType(Enum):
    BUFFER_OVERFLOW = "buffer_overflow"
    FORMAT_STRING = "format_string"
    USE_AFTER_FREE = "use_after_free"
    INT_OVERFLOW = "int_overflow"
    RACE = "race"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    XXE = "xxe"
    SSTI = "ssti"
    HARDCODED_SECRET = "hardcoded_secret"
    WEAK_CRYPTO = "weak_crypto"


@dataclass
class Finding:
    find_type: FindType = FindType.BUFFER_OVERFLOW
    severity: Severity = Severity.MEDIUM
    line: int = 0
    column: int = 0
    snippet: str = ""
    description: str = ""
    cwe: str = ""
    remediation: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.find_type.value,
            "severity": self.severity.value,
            "line": self.line, "column": self.column,
            "description": self.description, "cwe": self.cwe,
            "remediation": self.remediation,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class BinaryInfo:
    name: str = ""
    arch: ArchType = ArchType.X86_64
    endian: str = "little"
    bits: int = 64
    pie: bool = False
    nx: bool = True
    canary: bool = False
    relro: str = "none"
    stripped: bool = False
    sections: dict[str, int] = field(default_factory=dict)
    symbols: dict[str, int] = field(default_factory=dict)
    entry: int = 0x400000
    strings: list[str] = field(default_factory=list)

    def hardening_score(self) -> float:
        score = 0.0
        score += 0.25 if self.pie else 0.0
        score += 0.25 if self.nx else 0.0
        score += 0.25 if self.canary else 0.0
        score += {"full": 0.25, "partial": 0.125}.get(self.relro, 0.0)
        return score


# ---------------------------------------------------------------- CTF 编解码

B64_ALPHABET = string.ascii_uppercase + string.ascii_lowercase + \
    string.digits + "+/"
ROT_ALPHABET = string.ascii_lowercase + string.ascii_uppercase + \
    string.digits + "!@#$%^&*"


def base64_decode(data: str) -> bytes:
    data = "".join(data.split())
    data += "=" * (-len(data) % 4)
    return base64.b64decode(data, validate=False)


def base64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hex_decode(data: str) -> bytes:
    return binascii.unhexlify("".join(data.split()))


def hex_encode(data: bytes) -> str:
    return binascii.hexlify(data).decode()


def url_decode(data: str) -> str:
    import urllib.parse
    return urllib.parse.unquote_plus(data)


LETTERS = string.ascii_lowercase + string.ascii_uppercase


def rot_n(data: str, n: int = 13, symbols: bool = False) -> str:
    """凯撒位移。默认只旋转 ASCII 字母；symbols=True 时扩展到符号表。"""
    alpha = ROT_ALPHABET if symbols else LETTERS
    n %= len(alpha)
    out = []
    for ch in data:
        if ch in alpha:
            out.append(alpha[(alpha.index(ch) + n) % len(alpha)])
        else:
            out.append(ch)
    return "".join(out)


def xor_decode(data: str | bytes, key: str | bytes) -> bytes:
    if isinstance(data, str):
        data = data.encode()
    if isinstance(key, str):
        key = key.encode()
    if not key:
        return data
    return bytes(b ^ key[i % len(key)]
                 for i, b in enumerate(data))


def xor_encode(data: bytes, key: str) -> str:
    return base64.b64encode(xor_decode(data, key)).decode()


def reverse_engineer(data: str | bytes) -> dict[str, Any]:
    """识别常见编码类型并尝试多路解码。"""
    text = data if isinstance(data, str) else data.decode(
        "latin-1", "replace")
    results: list[dict[str, str]] = []
    stripped = "".join(text.split())
    try:
        raw = base64_decode(stripped)
        results.append({
            "encoding": "base64",
            "decoded": raw.decode("utf-8", "replace"),
            "size": len(raw),
        })
    except Exception:
        pass
    try:
        raw = hex_decode(stripped)
        results.append({
            "encoding": "hex",
            "decoded": raw.decode("utf-8", "replace"),
            "size": len(raw),
        })
    except Exception:
        pass
    if all(c in ROT_ALPHABET for c in text) and text:
        for n in (13, 47, 5, 3):
            results.append({
                "encoding": f"rot{n}",
                "decoded": rot_n(text, n),
                "size": len(text),
            })
    for b64 in (13, 47):
        if text and all(c in ROT_ALPHABET for c in text):
            dec = rot_n(text, b64)
            try:
                raw = base64_decode("".join(dec.split()))
                results.append({
                    "encoding": f"rot{b64}+base64",
                    "decoded": raw.decode("utf-8", "replace"),
                    "size": len(raw),
                })
            except Exception:
                pass
    return {
        "input_len": len(text),
        "input_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
        "candidates": results,
        "best": results[0] if results else None,
    }


def exploit_simplify(payload: str) -> str:
    """去除冗余与注释，提取核心利用序列。"""
    payload = re.sub(r"(?m)#.*$", "", payload)
    payload = re.sub(r"/\*.*?\*/", "", payload, flags=re.S)
    payload = payload.replace("\n\n", "\n")
    return re.sub(r"[ \t]{2,}", " ", payload).strip()


# -------------------------------------------------------------- 二进制安全

def buffer_overflow_check(code: str) -> list[dict[str, Any]]:
    findings = []
    unsafe_patterns = [
        (r"\bstrcpy\s*\(", "strcpy 无边界检查", "CWE-120"),
        (r"\bstrcat\s*\(", "strcat 可能溢出", "CWE-120"),
        (r"\bgets\s*\(", "gets 已被移除，禁止使用", "CWE-242"),
        (r"\bsprintf\s*\(", "sprintf 可能越界", "CWE-120"),
        (r"\bvsprintf\s*\(", "vsprintf 可能越界", "CWE-120"),
        (r"\bmemcpy\s*\([^,]+,[^,]+,\s*[a-z_]+\s*\)",
         "memcpy 长度来自变量", "CWE-120"),
    ]
    for i, line in enumerate(code.splitlines(), 1):
        for pattern, desc, cwe in unsafe_patterns:
            if re.search(pattern, line):
                findings.append({
                    "pattern": desc, "line": i, "cwe": cwe,
                    "severity": "high",
                    "snippet": line.strip()[:120],
                    "remediation": "改用 strncpy/strlcpy/snprintf "
                                   "并校验长度",
                })
    return findings


def format_string_detect(code: str) -> list[dict[str, Any]]:
    findings = []
    patterns = [
        (r"\bprintf\s*\(\s*[a-z_][a-z0-9_]*\s*\)",
         "printf 直接使用变量，缺少 %s", "CWE-134"),
        (r"\b(printf|fprintf|syslog|log)\s*\([^,)]*%n",
         "存在 %n 格式符，可写任意内存", "CWE-134"),
        (r"\bscanf\s*\(\s*\"[^\"]*%s[^\"]*\"\s*,\s*[a-z_]+\s*\)",
         "scanf %s 无宽度限制", "CWE-120"),
        (r"\bputs\s*\([a-z_]", "puts 使用变量可能泄露栈内容",
         "CWE-134"),
    ]
    for i, line in enumerate(code.splitlines(), 1):
        for pattern, desc, cwe in patterns:
            if re.search(pattern, line):
                sev = "critical" if "%n" in line else "high"
                findings.append({
                    "pattern": desc, "line": i, "cwe": cwe,
                    "severity": sev,
                    "snippet": line.strip()[:120],
                    "remediation": "使用固定格式串，"
                                   "printf(\"%s\", buf)",
                })
    return findings


def use_after_free_check(code: str) -> list[dict[str, Any]]:
    findings = []
    lines = code.splitlines()
    freed: list[tuple[str, int]] = []
    reported = set()
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r"\bfree\s*\(\s*&?(\w+)\s*\)", line):
            var = m.group(1)
            freed.append((var, i))
            tail = line[m.end():]
            if re.search(rf"\b{re.escape(var)}\b\s*(?:->|\[|\.)", tail):
                key = (var, i)
                if key not in reported:
                    reported.add(key)
                    findings.append({
                        "pattern": f"free 后同一语句继续使用 {var}",
                        "line": i, "cwe": "CWE-416",
                        "severity": "critical",
                        "snippet": line.strip()[:120],
                        "remediation": "置空指针或改用智能指针",
                    })
    for i, line in enumerate(lines, 1):
        if re.search(r"\bfree\s*\(", line):
            continue
        for var, free_line in freed:
            if free_line >= i or (var, i) in reported:
                continue
            if re.search(rf"\b{re.escape(var)}\b\s*(?:->|\[|\.)", line):
                reported.add((var, i))
                findings.append({
                    "pattern": f"free 后继续使用 {var}",
                    "line": i, "cwe": "CWE-416",
                    "severity": "critical",
                    "snippet": line.strip()[:120],
                    "remediation": "置空指针或改用智能指针",
                })
    return findings


def integer_overflow_check(code: str) -> list[dict[str, Any]]:
    findings = []
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(r"\b(malloc|realloc|calloc)\s*\(", line) and \
                re.search(r"\*\s*\d+|\+", line):
            findings.append({
                "pattern": "分配大小存在乘法/加法溢出风险",
                "line": i, "cwe": "CWE-190", "severity": "high",
                "snippet": line.strip()[:120],
                "remediation": "使用 __builtin_mul_overflow "
                               "或显式溢出检查",
            })
        if re.search(r"\b(size_t|int|uint32_t)\b.*=.*<<", line):
            findings.append({
                "pattern": "移位未检查宽度",
                "line": i, "cwe": "CWE-190", "severity": "medium",
                "snippet": line.strip()[:120],
                "remediation": "移位前校验 < sizeof(T)*8",
            })
    return findings


def race_condition_check(code: str) -> list[dict[str, Any]]:
    findings = []
    if re.search(r"\b(pthread_create|Thread|threading)\b", code) \
            and not re.search(r"\b(mutex|lock|semaphore|critical)\b",
                              code, re.I):
        findings.append({
            "pattern": "多线程但未发现同步原语",
            "line": 0, "cwe": "CWE-362", "severity": "high",
            "snippet": "", "remediation": "使用互斥锁或原子操作",
        })
    if re.search(r"\b(system|popen)\s*\(", code) and \
            re.search(r"\bthread|async|concurrent", code, re.I):
        findings.append({
            "pattern": "并发环境调用 system 存在注入与竞态风险",
            "line": 0, "cwe": "CWE-78", "severity": "critical",
            "snippet": "", "remediation": "使用 execve 并严格校验参数",
        })
    return findings


def sql_injection_check(code: str) -> list[dict[str, Any]]:
    findings = []
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(r"(execute|query|raw)\s*\(\s*[\"']?[^\"']*"
                     r"\+|%s" % "%", line) or \
                re.search(r"(execute|query|raw)\s*\(\s*f?[\"']"
                          r"[^\"']*(\+|%s)" % "%", line):
            findings.append({
                "pattern": "SQL 语句字符串拼接",
                "line": i, "cwe": "CWE-89", "severity": "critical",
                "snippet": line.strip()[:120],
                "remediation": "使用参数化查询",
            })
    return findings


def command_injection_check(code: str) -> list[dict[str, Any]]:
    findings = []
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(r"\b(system|popen|exec[lv]p?e?|Runtime)"
                     r"\s*\(", line) and \
                re.search(r"(\+|%s|\"\s*\+)" % "%", line):
            findings.append({
                "pattern": "命令执行参数拼接",
                "line": i, "cwe": "CWE-78", "severity": "critical",
                "snippet": line.strip()[:120],
                "remediation": "使用参数数组，禁止 shell 解析",
            })
    return findings


def path_traversal_check(code: str) -> list[dict[str, Any]]:
    findings = []
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(r"\bopen\s*\(", line) and \
                re.search(r"(request|params|argv|input|user)", line):
            findings.append({
                "pattern": "文件路径来自外部输入",
                "line": i, "cwe": "CWE-22", "severity": "high",
                "snippet": line.strip()[:120],
                "remediation": "规范化路径并校验前缀",
            })
    return findings


def hardcoded_secret_check(code: str) -> list[dict[str, Any]]:
    findings = []
    cred = (r"(?:password|passwd|pwd|pw|secret|api[_-]?key|"
            r"access[_-]?key|token|auth|private[_-]?key|credential)s?")
    pat = re.compile(rf"\b{cred}\b\s*[:=]\s*[\"'][^\"']{{5,}}[\"']", re.I)
    inline = re.compile(
        rf"[\"'][^\"']*\b{cred}\s*=\s*[^\"';]{{5,}}[^\"']*[\"']", re.I)
    for i, line in enumerate(code.splitlines(), 1):
        hit = pat.search(line) or inline.search(line)
        if hit:
            key = hit.group(0)[:20]
            findings.append({
                "pattern": f"硬编码凭据（{key}）",
                "line": i, "cwe": "CWE-798", "severity": "critical",
                "snippet": re.sub(r"[\"'][^\"']{5,}[\"']",
                                  "'***'", line.strip())[:120],
                "remediation": "迁移至环境变量或密钥管理服务",
            })
    return findings


def weak_crypto_check(code: str) -> list[dict[str, Any]]:
    findings = []
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(r"\b(MD5|SHA1)\b", line, re.I):
            findings.append({
                "pattern": "使用已弃用的 MD5/SHA1",
                "line": i, "cwe": "CWE-327", "severity": "medium",
                "snippet": line.strip()[:120],
                "remediation": "改用 SHA-256 以上或 HMAC",
            })
        if re.search(r"\bAES\s*\(\s*ECB", line, re.I) or \
                re.search(r"[\"']AES/ECB", line):
            findings.append({
                "pattern": "ECB 模式不提供语义安全",
                "line": i, "cwe": "CWE-327", "severity": "high",
                "snippet": line.strip()[:120],
                "remediation": "改用 GCM 或 CBC+HMAC",
            })
        if re.search(r"random\s*\(\s*\)", line) and \
                not re.search(r"random_|urandom", line):
            findings.append({
                "pattern": "使用非密码学安全随机源",
                "line": i, "cwe": "CWE-338", "severity": "high",
                "snippet": line.strip()[:120],
                "remediation": "使用 secrets / os.urandom",
            })
    return findings


def xxe_check(code: str) -> list[dict[str, Any]]:
    findings = []
    if re.search(r"(libxml|xml\.etree|lxml|XMLParser|SAXParser)", code) \
            and not re.search(r"(noent\s*=\s*False|"
                              r"resolve_entities\s*=\s*False|"
                              r"disable_entities)", code):
        findings.append({
            "pattern": "XML 解析器可能允许外部实体",
            "line": 0, "cwe": "CWE-611", "severity": "high",
            "snippet": "", "remediation": "显式关闭外部实体",
        })
    return findings


def ssti_check(code: str) -> list[dict[str, Any]]:
    findings = []
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(r"(render_template_string|Template)\s*\(", line) and \
                re.search(r"(request|input|user|params)", line):
            findings.append({
                "pattern": "模板渲染外部输入",
                "line": i, "cwe": "CWE-1336", "severity": "critical",
                "snippet": line.strip()[:120],
                "remediation": "使用自动转义或沙箱模板",
            })
    return findings


CHECKERS = {
    FindType.BUFFER_OVERFLOW: buffer_overflow_check,
    FindType.FORMAT_STRING: format_string_detect,
    FindType.COMMAND_INJECTION: command_injection_check,
    FindType.PATH_TRAVERSAL: path_traversal_check,
    FindType.HARDCODED_SECRET: hardcoded_secret_check,
    FindType.WEAK_CRYPTO: weak_crypto_check,
}


class SecurityAuditor:
    """静态安全审计器。"""

    def __init__(self):
        self._findings: list[Finding] = []
        self._loc = 0

    def scan(self, code: str) -> dict[str, Any]:
        self._findings = []
        self._loc = 0
        for find_type, checker in CHECKERS.items():
            for raw in checker(code):
                self._findings.append(self._to_finding(find_type, raw))
        for extra, checker in (
            (FindType.USE_AFTER_FREE, use_after_free_check),
            (FindType.INT_OVERFLOW, integer_overflow_check),
            (FindType.RACE, race_condition_check),
            (FindType.XXE, xxe_check),
            (FindType.SSTI, ssti_check),
        ):
            for raw in checker(code):
                self._findings.append(self._to_finding(extra, raw))
        return self.report()

    def _to_finding(self, ft: FindType, raw: dict[str, Any]
                    ) -> Finding:
        self._loc += 1
        return Finding(
            find_type=ft,
            severity=Severity(raw.get("severity", "medium")),
            line=raw.get("line", 0),
            snippet=raw.get("snippet", ""),
            description=raw.get("pattern", ""),
            cwe=raw.get("cwe", ""),
            remediation=raw.get("remediation", ""),
            confidence=0.9 if raw.get("line") else 0.6,
        )

    def report(self) -> dict[str, Any]:
        counts = collections.Counter(
            f.severity.value for f in self._findings)
        by_cwe: dict[str, int] = collections.Counter(
            f.cwe for f in self._findings if f.cwe)
        return {
            "total": len(self._findings),
            "by_severity": dict(counts),
            "by_cwe": dict(by_cwe),
            "risk_score": self._risk_score(),
            "findings": [f.to_dict() for f in self._findings],
        }

    def _risk_score(self) -> float:
        weights = {"critical": 20.0, "high": 10.0,
                   "medium": 4.0, "low": 1.0, "info": 0.5}
        raw = sum(weights.get(f.severity.value, 1.0)
                  * f.confidence for f in self._findings)
        return round(min(100.0, raw), 2)

    def findings(self) -> list[Finding]:
        return list(self._findings)


class PenetrationTester:
    """受控渗透测试模拟器。"""

    COMMON_PORTS = {
        22: "ssh", 21: "ftp", 23: "telnet", 25: "smtp", 53: "dns",
        80: "http", 110: "pop3", 139: "netbios", 143: "imap",
        443: "https", 445: "smb", 3306: "mysql", 3389: "rdp",
        5432: "postgres", 6379: "redis", 8080: "http-alt",
        9200: "elasticsearch", 27017: "mongodb",
    }

    def __init__(self):
        self._hosts: dict[str, dict[str, Any]] = {}

    def add_host(self, host: str, open_ports: list[int],
                 os_hint: str = "linux") -> dict[str, Any]:
        services = [self.COMMON_PORTS.get(p, f"unknown-{p}")
                    for p in open_ports]
        info = {
            "host": host, "open_ports": sorted(open_ports),
            "services": services, "os_hint": os_hint,
            "exposed_count": len(open_ports),
        }
        self._hosts[host] = info
        return info

    def enumerate_services(self, host: str) -> list[dict[str, Any]]:
        info = self._hosts.get(host)
        if not info:
            return []
        out = []
        risky = {"telnet": "明文远程管理",
                 "ftp": "明文文件传输",
                 "redis": "常无认证",
                 "mongodb": "常无认证",
                 "elasticsearch": "常无认证",
                 "rdp": "暴力破解面大",
                 "smb": "永恒之蓝等历史漏洞"}
        for port in info["open_ports"]:
            svc = self.COMMON_PORTS.get(port, f"unknown-{port}")
            out.append({
                "port": port, "service": svc,
                "risk": risky.get(svc, ""),
                "version_guess": self._guess_version(svc),
            })
        return out

    def _guess_version(self, service: str) -> str:
        table = {"ssh": "OpenSSH 8.x", "http": "nginx 1.20+",
                 "https": "nginx 1.20+", "redis": "Redis 6/7",
                 "mysql": "MySQL 8.0", "smb": "Samba 4.x",
                 "elasticsearch": "ES 7.x", "mongodb": "Mongo 5/6"}
        return table.get(service, "unknown")

    def risk_matrix(self, host: str) -> dict[str, Any]:
        info = self._hosts.get(host)
        if not info:
            return {"ok": False}
        services = self.enumerate_services(host)
        risky = [s for s in services if s["risk"]]
        score = min(100.0, len(risky) * 18 + info["exposed_count"] * 3)
        return {
            "ok": True, "host": host,
            "exposure": score,
            "grade": ("F" if score >= 80 else "D" if score >= 60
                      else "C" if score >= 40 else
                      "B" if score >= 20 else "A"),
            "risky_services": [s["service"] for s in risky],
            "recommendations": self._recommend(services),
        }

    def _recommend(self, services: list[dict[str, Any]]
                   ) -> list[str]:
        recs = []
        svc_set = {s["service"] for s in services}
        if "telnet" in svc_set:
            recs.append("关闭 telnet，改用 SSH")
        if "ftp" in svc_set:
            recs.append("FTP 改用 SFTP/FTPS")
        if {"redis", "mongodb", "elasticsearch"} & svc_set:
            recs.append("为数据库启用认证与网络白名单")
        if "smb" in svc_set:
            recs.append("禁用 SMBv1，启用签名")
        if "rdp" in svc_set:
            recs.append("限制 RDP 来源 IP，启用 NLA")
        if not recs:
            recs.append("维持现有加固基线并持续监控")
        return recs


class HardeningChecker:
    """二进制加固检查。"""

    def __init__(self, info: BinaryInfo):
        self.info = info

    def stack_canary_check(self) -> dict[str, Any]:
        return {
            "present": self.info.canary,
            "expected_len": STACK_CANARY_LEN,
            "symbols": [s for s in self.info.symbols
                        if "stack_chk" in s],
            "ok": self.info.canary,
            "remediation": "" if self.info.canary
            else "编译时启用 -fstack-protector-strong",
        }

    def aslr_entropy(self) -> dict[str, Any]:
        pie = self.info.pie
        effective = ASLR_BITS if (pie and self.info.bits == 64) else \
            (16 if pie else 0)
        return {
            "pie": pie,
            "aslr_bits": effective,
            "strength": "strong" if effective >= 28
            else "partial" if effective else "none",
            "ok": effective >= 28,
        }

    def nx_check(self) -> dict[str, Any]:
        return {
            "nx": self.info.nx,
            "writable_exec": not self.info.nx,
            "ok": self.info.nx,
            "remediation": "" if self.info.nx else "启用 NX/W^X",
        }

    def relro_check(self) -> dict[str, Any]:
        return {
            "relro": self.info.relro,
            "partial": self.info.relro == "partial",
            "full": self.info.relro == "full",
            "ok": self.info.relro == "full",
            "remediation": "" if self.info.relro == "full"
            else "使用 -Wl,-z,relro,-z,now",
        }

    def check_all(self) -> dict[str, Any]:
        checks = {
            "canary": self.stack_canary_check(),
            "aslr": self.aslr_entropy(),
            "nx": self.nx_check(),
            "relro": self.relro_check(),
        }
        passed = sum(1 for c in checks.values() if c["ok"])
        return {
            "binary": self.info.name,
            "arch": self.info.arch.value,
            "checks": checks,
            "passed": passed, "total": len(checks),
            "score": round(self.info.hardening_score() * 100, 1),
            "verdict": "well-hardened"
            if passed == len(checks) else "weak",
        }


class PayloadLab:
    """受控载荷实验室（仅用于授权测试）。"""

    def __init__(self):
        self._log: list[dict[str, Any]] = []

    def payload_generate(self, kind: str = "marker",
                         size: int = 64) -> dict[str, Any]:
        size = min(size, MAX_PAYLOAD_SIZE)
        if kind == "marker":
            data = b"MATHA_MARKER_" * (size // 13 + 1)
        elif kind == "cyclic":
            data = b"".join(struct.pack("<I", i)
                            for i in range(size // 4))[:size]
        elif kind == "ret2libc":
            data = b"A" * (size - 8) + struct.pack("<Q", 0xDEADBEEF)
        elif kind == "rop":
            data = b"\x90" * size
        else:
            data = b"\x00" * size
        data = data[:size]
        self._log.append({
            "kind": kind, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()[:16],
            "timestamp_note": BANNER,
        })
        return {
            "kind": kind, "size": len(data),
            "hex": hex_encode(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "notice": BANNER,
        }

    def shellcode_search(self, binary: bytes,
                         patterns: list[bytes] | None = None
                         ) -> list[dict[str, Any]]:
        patterns = patterns or [
            b"\x90\x90\x90\x90", b"\xcc\xcc\xcc\xcc",
            b"\xeb\xfe", b"/bin/sh", b"/bin/bash",
        ]
        hits = []
        for pat in patterns:
            start = 0
            while True:
                idx = binary.find(pat, start)
                if idx < 0:
                    break
                hits.append({
                    "pattern": hex_encode(pat),
                    "offset": hex(idx),
                    "context": hex_encode(
                        binary[max(0, idx - 4):idx + len(pat) + 4]),
                })
                start = idx + 1
        return hits

    def stats(self) -> dict[str, int]:
        return {"generations": len(self._log)}


class CTFSolver:
    """CTF 助手。"""

    def __init__(self):
        self.payloads = PayloadLab()
        self.auditor = SecurityAuditor()

    def solve_base64(self, data: str) -> dict[str, Any]:
        raw = base64_decode(data)
        return {"type": "base64", "size": len(raw),
                "decoded": raw.decode("utf-8", "replace"),
                "hex": hex_encode(raw)}

    def solve_xor(self, data: str, key: str) -> dict[str, Any]:
        raw = xor_decode(data, key)
        return {"type": "xor", "size": len(raw),
                "decoded": raw.decode("utf-8", "replace"),
                "hex": hex_encode(raw)}

    def solve_rot(self, data: str, n: int = 13) -> dict[str, Any]:
        dec = rot_n(data, n)
        return {"type": f"rot{n}", "decoded": dec,
                "flag_found": bool(re.search(r"flag\{[^}]+\}", dec,
                                            re.I))}

    def identify(self, data: str) -> dict[str, Any]:
        return reverse_engineer(data)

    def exploit_from_crash(self, offset_map: dict[str, int],
                           gadgets: dict[str, int]
                           ) -> dict[str, Any]:
        ordered = sorted(offset_map.items(), key=lambda kv: kv[1])
        plan = []
        for name, offset in ordered:
            plan.append({
                "gadget": name,
                "offset": hex(offset),
                "available": gadgets.get(name, 0) > 0,
            })
        usable = [p for p in plan if p["available"]]
        return {
            "banner": BANNER,
            "offset_delta": (ordered[-1][1] - ordered[0][1])
            if len(ordered) > 1 else 0,
            "unique_offsets": len({o for _, o in ordered}),
            "monotonic": all(ordered[i][1] <= ordered[i + 1][1]
                             for i in range(len(ordered) - 1)),
            "chain": usable,
            "confidence": round(len(usable) / max(1, len(plan)), 2),
        }


class GeekGrayEngine:
    """极客文化与灰产边缘统一入口。"""

    def __init__(self):
        self.auditor = SecurityAuditor()
        self.tester = PenetrationTester()
        self.solver = CTFSolver()
        self._hardening: dict[str, HardeningChecker] = {}

    def add_binary(self, info: BinaryInfo) -> dict[str, Any]:
        self._hardening[info.name] = HardeningChecker(info)
        return self._hardening[info.name].check_all()

    def hardening(self, name: str) -> dict[str, Any]:
        h = self._hardening.get(name)
        return h.check_all() if h else {"ok": False}

    def scan(self, code: str) -> dict[str, Any]:
        return self.auditor.scan(code)


def create_geek_engine() -> GeekGrayEngine:
    return GeekGrayEngine()


def buffer_overflow_check_wrapper(code: str) -> list[dict[str, Any]]:
    return buffer_overflow_check(code)


def stack_canary_check(info: BinaryInfo) -> dict[str, Any]:
    return HardeningChecker(info).stack_canary_check()


def aslr_entropy(info: BinaryInfo) -> dict[str, Any]:
    return HardeningChecker(info).aslr_entropy()


def shellcode_search(binary: bytes,
                     patterns: list[bytes] | None = None
                     ) -> list[dict[str, Any]]:
    return PayloadLab().shellcode_search(binary, patterns)


def payload_generate(kind: str = "marker",
                     size: int = 64) -> dict[str, Any]:
    return PayloadLab().payload_generate(kind, size)


def security_audit(code: str) -> dict[str, Any]:
    return GeekGrayEngine().scan(code)


def _register_geek_gray(builtins: dict) -> None:
    builtins["buffer_overflow_check"] = buffer_overflow_check
    builtins["format_string_detect"] = format_string_detect
    builtins["xor_decode"] = xor_decode
    builtins["base64_decode"] = base64_decode
    builtins["rot_n"] = rot_n
    builtins["stack_canary_check"] = stack_canary_check
    builtins["aslr_entropy"] = aslr_entropy
    builtins["shellcode_search"] = shellcode_search
    builtins["payload_generate"] = payload_generate
    builtins["exploit_simplify"] = exploit_simplify
    builtins["reverse_engineer"] = reverse_engineer
    builtins["security_audit"] = security_audit
    builtins["use_after_free_check"] = use_after_free_check
    builtins["integer_overflow_check"] = integer_overflow_check
    builtins["race_condition_check"] = race_condition_check
    builtins["sql_injection_check"] = sql_injection_check
    builtins["command_injection_check"] = command_injection_check
    builtins["path_traversal_check"] = path_traversal_check
    builtins["hardcoded_secret_check"] = hardcoded_secret_check
    builtins["weak_crypto_check"] = weak_crypto_check
    builtins["xxe_check"] = xxe_check
    builtins["ssti_check"] = ssti_check
    builtins["创建极客引擎"] = create_geek_engine


__all__ = [
    "Severity", "ArchType", "FindType", "Finding", "BinaryInfo",
    "SecurityAuditor", "PenetrationTester", "HardeningChecker",
    "PayloadLab", "CTFSolver", "GeekGrayEngine",
    "create_geek_engine", "base64_decode", "base64_encode",
    "hex_decode", "hex_encode", "url_decode", "rot_n",
    "xor_decode", "xor_encode", "reverse_engineer",
    "exploit_simplify", "buffer_overflow_check",
    "format_string_detect", "use_after_free_check",
    "integer_overflow_check", "race_condition_check",
    "sql_injection_check", "command_injection_check",
    "path_traversal_check", "hardcoded_secret_check",
    "weak_crypto_check", "xxe_check", "ssti_check",
    "stack_canary_check", "aslr_entropy", "shellcode_search",
    "payload_generate", "security_audit",
    "_register_geek_gray",
]
