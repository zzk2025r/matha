# -*- coding: utf-8 -*-
"""toolchain_signature —— 可选包签名工具链插件（``cosign`` / sigstore）。

包签名与来源认证依赖外部 ``cosign`` 进程，属工具链而非语言内核，故从
``src/pkg_manager_v2.py`` 中拆出（该模块现在只在真正需要签名时惰性 import 本
插件）。

行为变更（消除静默假成功）：
  * ``verify_signed_package`` 旧实现把**同一个包文件字节**同时当数据、签名、
    公钥传给 ``cosign verify-blob``，结果永远不可信；现按正确三元组调用。
  * 工具缺失时不再静默返回 ``False``：抛出 :class:`SignatureError`，由调用方
    决定是「跳过验签」还是「失败退出」，跳过与否必须显式写出来。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

__all__ = ["SignatureError", "SignatureVerifier", "cosign_available"]

_VERSION_TIMEOUT = 5.0
_SIGN_TIMEOUT = 30.0
_INSTALL_HINT = "请安装 cosign：https://docs.sigstore.dev/cosign/installation/"


class SignatureError(Exception):
    """签名/验签错误（含工具缺失，显式失败而非返回伪结果）。"""


def cosign_available(cosign_path: str = "cosign") -> bool:
    return shutil.which(cosign_path) is not None


class SignatureVerifier:
    """使用外部 ``cosign`` 对包做签名/验签。"""

    def __init__(self, cosign_path: str = "cosign", sigstore_root: str = "",
                 offline: bool = False, require: bool = True):
        self._cosign = cosign_path
        self._sigstore_root = sigstore_root
        self._offline = offline
        if require and not self.is_available:
            raise SignatureError(f"cosign 未安装或不可用（{_INSTALL_HINT}）")

    @property
    def is_available(self) -> bool:
        """探测 cosign 是否可执行（这是本类唯一的进程调用，且只读版本信息）。"""
        if not cosign_available(self._cosign):
            return False
        try:
            return subprocess.run([self._cosign, "version"],
                                  capture_output=True,
                                  timeout=_VERSION_TIMEOUT).returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _require_cosign(self) -> None:
        if not self.is_available:
            raise SignatureError(f"cosign 未安装或不可用（{_INSTALL_HINT}）")

    def _run(self, cmd: list[str], timeout: float = _SIGN_TIMEOUT
             ) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(cmd, capture_output=True, timeout=timeout)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise SignatureError(f"cosign 调用失败：{exc}") from exc

    def sign_blob(self, data: bytes, key_path: str,
                  password: str | None = None) -> bytes:
        """对数据签名，返回 cosign 输出的签名字节。"""
        self._require_cosign()
        with tempfile.NamedTemporaryFile(delete=False) as tmp_data:
            tmp_data.write(data)
            data_path = tmp_data.name
        try:
            cmd = [self._cosign, "sign-blob", "--key", key_path]
            if password:
                cmd.extend(["--passphrase", password])
            cmd.append(data_path)
            result = self._run(cmd)
            if result.returncode != 0:
                raise SignatureError(
                    f"签名失败: {result.stderr.decode(errors='replace')}")
            return result.stdout
        finally:
            os.unlink(data_path)

    def verify_blob(self, data: bytes, signature: bytes, public_key_path: str,
                    certificate_path: str | None = None) -> bool:
        """验证 blob 签名（工具缺失按上面的说明显式报错）。"""
        self._require_cosign()
        with tempfile.NamedTemporaryFile(delete=False) as tmp_data:
            tmp_data.write(data)
            data_path = tmp_data.name
        with tempfile.NamedTemporaryFile(delete=False) as tmp_sig:
            tmp_sig.write(signature)
            sig_path = tmp_sig.name
        try:
            cmd = [self._cosign, "verify-blob", "--key", public_key_path,
                   "--signature", sig_path]
            if certificate_path:
                cmd.extend(["--certificate", certificate_path])
            if self._offline:
                cmd.append("--offline")
            cmd.append(data_path)
            return self._run(cmd).returncode == 0
        finally:
            os.unlink(data_path)
            os.unlink(sig_path)

    @staticmethod
    def _find_sig(pkg_path) -> "os.PathLike | None":
        """约定签名文件为 ``<pkg>.sig``，退化查找同名 ``.sig`` 后缀。"""
        cand = pkg_path.with_suffix(pkg_path.suffix + ".sig")
        if cand.exists():
            return cand
        alt = pkg_path.with_suffix(".sig")
        return alt if alt.exists() else None

    def verify_signed_package(self, pkg_path, public_key_path: str,
                              certificate_path: str | None = None) -> bool:
        """验证已签名包：数据 = 包字节，签名 = .sig 文件内容，公钥 = 传入者。"""
        if not os.path.exists(pkg_path):
            raise SignatureError(f"包文件不存在：{pkg_path}")
        sig_path = self._find_sig(pkg_path)
        if sig_path is None:
            raise SignatureError(f"未找到签名文件（{pkg_path} 缺少 .sig），无法验签")
        return self.verify_blob(pkg_path.read_bytes(),
                                sig_path.read_bytes(),
                                public_key_path, certificate_path)

    def verify_slsa_provenance(self, pkg_path, provenance_path,
                               builder_id: str) -> bool:
        """验证 SLSA 来源认证（attestation）。"""
        self._require_cosign()
        cmd = [self._cosign, "verify-attestation", "--type", "slsaprovenance",
               "--predicate", str(provenance_path),
               "--certificate-identity-regexp", builder_id, str(pkg_path)]
        return self._run(cmd).returncode == 0
