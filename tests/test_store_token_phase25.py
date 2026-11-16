# -*- coding: utf-8 -*-
"""阶段 25b 三锁：商店自生凭据（HMAC 令牌自签发/校验/吊销）。

锁四面：
  A. 签名往返 —— 签发→校验载荷字段（sub/iat/exp/jti）；令牌三段式 HS256 形；
  B. 诚实拒绝 —— 篡改（载荷位/签名位）→签名不符 / 过期→已过期 /
     吊销→已吊销 / 形态错 / 主体与过期秒非法 / 密钥文件损坏；
  C. 持久面 —— 密钥与吊销表落盘 .matha/store/（无内存态）；换表重验仍拒绝；
     吊销表过期条目回收；
  D. Matha 面 —— 宿主 Interpreter 签发→校验→吊销闭环 + VM 面同样可达。
所有用例 chdir 到 tmp_path，密钥落 tmp 的 .matha/store/，不污染仓库。
"""
import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from src.domains.store import (  # noqa: E402
    _register_store,
    _store_symtab_names,
    issue_token,
    revoke_token,
    store_dir,
    verify_token,
)
from src.interp import Interpreter  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.parser import parse  # noqa: E402


# ============================================================
# A. 签名往返
# ============================================================

class TestRoundTrip:
    def test_issue_verify_payload_fields(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        t = issue_token("我的应用", 3600)
        parts = t.split(".")
        assert len(parts) == 3 and all(parts)
        p = verify_token(t)
        assert p["sub"] == "我的应用"
        assert p["exp"] - p["iat"] == 3600
        assert isinstance(p["jti"], str) and len(p["jti"]) == 16

    def test_secret_generated_once_reused(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        t1 = issue_token("甲", 60)
        t2 = issue_token("乙", 60)
        secret_file = store_dir() / "secret.key"
        assert secret_file.exists()
        first = secret_file.read_text(encoding="utf-8")
        assert len(first) == 64
        verify_token(t1)
        verify_token(t2)
        assert secret_file.read_text(encoding="utf-8") == first


# ============================================================
# B. 诚实拒绝
# ============================================================

class TestHonestRefusal:
    def test_tampered_payload_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        h, p, s = issue_token("原体", 60).split(".")
        with pytest.raises(ValueError, match="签名不符"):
            verify_token(f"{h}.{'AAAA' + p[4:]}.{s}")

    def test_tampered_signature_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        t = issue_token("原体", 60)
        h, p, s = t.split(".")
        bad = ("b" if s[0] != "b" else "c") + s[1:]
        with pytest.raises(ValueError, match="签名不符"):
            verify_token(f"{h}.{p}.{bad}")

    def test_expired_token_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        t = issue_token("短命", 1)
        assert verify_token(t)["sub"] == "短命"
        time.sleep(1.05)
        with pytest.raises(ValueError, match="已过期"):
            verify_token(t)

    def test_revoked_token_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        t = issue_token("吊销对象", 3600)
        assert verify_token(t)["sub"] == "吊销对象"
        assert revoke_token(t) is True
        with pytest.raises(ValueError, match="已吊销"):
            verify_token(t)

    def test_malformed_shapes_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        for bad in ("", "abc", "a.b", "a.b.c.d", "..x"):
            with pytest.raises(ValueError, match="三段式"):
                verify_token(bad)
        with pytest.raises(ValueError, match="令牌须为字符串"):
            verify_token(42)

    def test_bad_subject_and_ttl_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        for bad_subject in ("", "   ", 42, None):
            with pytest.raises(ValueError, match="主体须为非空字符串"):
                issue_token(bad_subject, 60)
        for bad_ttl in (0, -5, True, "60"):
            with pytest.raises(ValueError, match="过期秒须为正数"):
                issue_token("体", bad_ttl)

    def test_corrupted_secret_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        d = store_dir()
        d.mkdir(parents=True)
        (d / "secret.key").write_text("xyz", encoding="utf-8")
        with pytest.raises(ValueError, match="密钥文件损坏"):
            issue_token("体", 60)
        with pytest.raises(ValueError, match="密钥文件损坏"):
            verify_token("a.b.c")

    def test_wrong_secret_rejected_as_tamper(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        t = issue_token("体", 60)
        (store_dir() / "secret.key").write_text("a" * 64, encoding="utf-8")
        with pytest.raises(ValueError, match="签名不符"):
            verify_token(t)


# ============================================================
# C. 持久面（无内存态）
# ============================================================

class TestPersistence:
    def test_revocation_persists_across_fresh_table(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        t = issue_token("持久吊销", 3600)
        assert revoke_token(t) is True
        fresh = {}
        _register_store(fresh)
        with pytest.raises(ValueError, match="已吊销"):
            fresh["商店_校验令牌"](t)

    def test_revoked_table_prunes_expired_entries(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        d = store_dir()
        d.mkdir(parents=True)
        (d / "revoked.json").write_text(json.dumps(
            {"protocol_version": 1, "revoked": {"死条目": 1}}),
            encoding="utf-8")
        t = issue_token("体", 3600)
        revoke_token(t)
        table = json.loads((d / "revoked.json").read_text(encoding="utf-8"))
        assert "死条目" not in table["revoked"]
        assert len(table["revoked"]) == 1

    def test_symtab_matches_registration(self):
        b = {}
        _register_store(b)
        assert set(_store_symtab_names()) == set(b)


# ============================================================
# D. Matha 面
# ============================================================

class TestMathaFace:
    def test_host_issue_verify_revoke(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ip = Interpreter()
        ip.run(parse(
            'let t = 商店_签发令牌("数学应用")(60)\n'
            'let p = 商店_校验令牌(t)\n'
            '输出(p["sub"])\n'
            '输出(商店_吊销令牌(t))'))
        assert [str(o) for o in ip.outputs] == ["数学应用", "True"]
        with pytest.raises(ValueError, match="已吊销"):
            verify_token(ip.env["t"])

    def test_vm_face_reachable(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        outs, err = exec_api.run_checked(
            'let t = 商店_签发令牌("vm探针")(60)\n'
            '输出(商店_校验令牌(t)["sub"])',
            mode="vm")
        assert err is None
        assert outs == ["vm探针"]
