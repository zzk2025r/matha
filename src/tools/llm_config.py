"""Matha LLM API 密钥配置管理

提供：
  - API 密钥加密存储（cryptography.Fernet）
  - 多密钥切换（按模型维护密钥列表）
  - 密钥轮换（rotate）
  - 环境变量回退（MATHA_LLM_API_KEY / MATHA_LLM_MODEL）
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from cryptography.fernet import Fernet

DEFAULT_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".matha")


def _config_dir() -> str:
    return os.environ.get("MATHA_CONFIG_DIR", DEFAULT_CONFIG_DIR)


def _key_path() -> str:
    return os.path.join(_config_dir(), "llm_master.key")


def _load_or_create_master_key() -> bytes:
    """加载或创建主密钥"""
    path = _key_path()
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    os.makedirs(_config_dir(), exist_ok=True)
    key = Fernet.generate_key()
    with open(path, "wb") as f:
        f.write(key)
    return key


def _fernet() -> Fernet:
    return Fernet(_load_or_create_master_key())


class LLMKeyConfig:
    """LLM 密钥配置管理器（单例可用）"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or os.path.join(_config_dir(), "llm_config.json")
        self._data: dict[str, Any] = {
            "version": 1,
            "models": {},  # model_name -> {"entries": [{id,label,cipher}], "active": entry_id}
        }
        self._load()

    # ── 存储 ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict) and "models" in loaded:
                    self._data = loaded
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ── 密钥管理 ──────────────────────────────────────────────────────────

    def add_key(self, model: str, api_key: str, label: str | None = None, make_active: bool = False) -> str:
        """添加（加密）一个新密钥，返回 entry_id"""
        if not api_key.strip():
            raise ValueError("API 密钥不能为空")
        entry_id = uuid.uuid4().hex[:12]
        cipher = _fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")
        model_cfg = self._data["models"].setdefault(model, {"entries": [], "active": None})
        model_cfg["entries"].append({
            "id": entry_id,
            "label": label or f"{model}-{len(model_cfg['entries']) + 1}",
            "cipher": cipher,
        })
        if make_active or model_cfg["active"] is None:
            model_cfg["active"] = entry_id
        self._save()
        return entry_id

    def remove_key(self, model: str, entry_id: str) -> bool:
        """移除指定密钥"""
        model_cfg = self._data["models"].get(model)
        if not model_cfg:
            return False
        before = len(model_cfg["entries"])
        model_cfg["entries"] = [e for e in model_cfg["entries"] if e["id"] != entry_id]
        if len(model_cfg["entries"]) == before:
            return False
        if model_cfg["active"] == entry_id:
            model_cfg["active"] = model_cfg["entries"][-1]["id"] if model_cfg["entries"] else None
        self._save()
        return True

    def update_key(self, model: str, entry_id: str, new_api_key: str) -> bool:
        """更新（重新加密）指定密钥"""
        model_cfg = self._data["models"].get(model)
        if not model_cfg:
            return False
        for entry in model_cfg["entries"]:
            if entry["id"] == entry_id:
                entry["cipher"] = _fernet().encrypt(new_api_key.encode("utf-8")).decode("utf-8")
                self._save()
                return True
        return False

    def set_active(self, model: str, entry_id: str) -> bool:
        """切换到指定密钥"""
        model_cfg = self._data["models"].get(model)
        if not model_cfg or not any(e["id"] == entry_id for e in model_cfg["entries"]):
            return False
        model_cfg["active"] = entry_id
        self._save()
        return True

    def rotate(self, model: str) -> str | None:
        """轮换密钥：切到列表中的下一个密钥，返回新 entry_id"""
        entries = self.list_keys(model)
        if not entries:
            return None
        active = self.active_entry_id(model)
        idx = next((i for i, e in enumerate(entries) if e["id"] == active), -1)
        next_id = entries[(idx + 1) % len(entries)]["id"]
        self.set_active(model, next_id)
        return next_id

    def get_api_key(self, model: str | None = None) -> str | None:
        """获取当前生效的密钥（环境变量优先）"""
        env_key = os.environ.get("MATHA_LLM_API_KEY")
        if env_key and model in (None, os.environ.get("MATHA_LLM_MODEL")):
            return env_key
        if model is None:
            model = os.environ.get("MATHA_LLM_MODEL", "")
        entry_id = self.active_entry_id(model)
        for entry in self._data["models"].get(model, {}).get("entries", []):
            if entry["id"] == entry_id:
                return _fernet().decrypt(entry["cipher"].encode("utf-8")).decode("utf-8")
        return None

    # ── 查询 ──────────────────────────────────────────────────────────────

    def list_keys(self, model: str) -> list[dict[str, str]]:
        """列出某模型的密钥信息（不含明文）"""
        return [
            {"id": e["id"], "label": e["label"], "active": e["id"] == self.active_entry_id(model)}
            for e in self._data["models"].get(model, {}).get("entries", [])
        ]

    def active_entry_id(self, model: str) -> str | None:
        return self._data["models"].get(model, {}).get("active")

    @property
    def models(self) -> list[str]:
        return list(self._data["models"].keys())

    @property
    def total_keys(self) -> int:
        return sum(len(m.get("entries", [])) for m in self._data["models"].values())

    @property
    def config_file(self) -> str:
        return self.config_path


def get_llm_config() -> LLMKeyConfig:
    """获取全局 LLM 密钥配置实例"""
    global _LLM_CONFIG
    if _LLM_CONFIG is None:
        _LLM_CONFIG = LLMKeyConfig()
    return _LLM_CONFIG


_LLM_CONFIG: LLMKeyConfig | None = None
