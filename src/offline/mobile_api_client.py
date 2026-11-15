"""Matha 移动端远程 API 客户端（真实 HTTP）。

提供与后端的 HTTP 通信功能（阶段 22a 起为真实 stdlib HTTP，
不再走内置 mock 假响应）：
  - 用户认证（JWT Token）
  - 数据同步（push/pull）
  - 冲突检测（HTTP 409）
  - 文件上传/下载

网络不可达时如实返回 status_code=0 与错误信息（不再伪造
500 服务器响应或 mock 令牌）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class HTTPMethod(Enum):
    """HTTP 方法"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class SyncStatus(Enum):
    """同步状态"""
    PENDING = "pending"
    SYNCING = "syncing"
    SUCCESS = "success"
    CONFLICT = "conflict"
    FAILED = "failed"
    NETWORK_ERROR = "network_error"


@dataclass
class APIResponse:
    """API 响应"""
    status_code: int
    data: dict[str, Any] | None = None
    error: str | None = None
    timestamp: float = field(default_factory=time.time)

    @property
    def success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_conflict(self) -> bool:
        return self.status_code == 409


@dataclass
class SyncRecord:
    """同步记录"""
    id: str
    record_type: str
    action: str  # push, pull
    local_data: dict[str, Any]
    remote_data: dict[str, Any] | None = None
    status: SyncStatus = SyncStatus.PENDING
    conflict_resolved: bool = False
    error_message: str | None = None
    created_at: float = field(default_factory=time.time)
    synced_at: float | None = None


class MathaAPIClient:
    """
    Matha 远程 API 客户端

    提供与后端的 HTTP 通信：
    - 用户认证（JWT Token）
    - 数据同步（push/pull）
    - 冲突检测
    - 文件上传/下载
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._sync_queue: list[SyncRecord] = []
        self._conflict_callbacks: list[Callable[[SyncRecord], None]] = []
        self._sync_callbacks: list[Callable[[str, str], None]] = []
        self._is_authenticated = False

    async def login(self, username: str, password: str) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.POST,
                '/auth/login',
                data={'username': username, 'password': password}
            )
            if response.success and response.data:
                self._token = response.data.get('access_token')
                self._refresh_token = response.data.get('refresh_token')
                self._is_authenticated = True
                logger.info(f"用户登录成功: {username}")
            return response
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def refresh_token(self) -> APIResponse:
        if not self._refresh_token:
            return APIResponse(status_code=401, error="No refresh token")
        try:
            response = await self._request(
                HTTPMethod.POST,
                '/auth/refresh',
                data={'refresh_token': self._refresh_token}
            )
            if response.success and response.data:
                self._token = response.data.get('access_token')
                self._refresh_token = response.data.get('refresh_token')
            return response
        except Exception as e:
            logger.error(f"刷新令牌失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def logout(self) -> None:
        self._token = None
        self._refresh_token = None
        self._is_authenticated = False
        logger.info("用户已登出")

    def is_authenticated(self) -> bool:
        return self._is_authenticated and self._token is not None

    async def push_data(self, record_type: str, record_id: str, data: dict[str, Any]) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.PUT,
                f'/sync/{record_type}/{record_id}',
                data=data
            )
            if response.is_conflict:
                logger.warning(f"检测到冲突: {record_type}:{record_id}")
                self._notify_conflict(record_type, record_id, data, response.data)
            return response
        except Exception as e:
            logger.error(f"推送数据失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def pull_data(self, record_type: str, record_id: str) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.GET,
                f'/sync/{record_type}/{record_id}'
            )
            return response
        except Exception as e:
            logger.error(f"拉取数据失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def get_all_records(self, record_type: str, since: float | None = None) -> APIResponse:
        try:
            params = {}
            if since:
                params['since'] = str(since)
            response = await self._request(
                HTTPMethod.GET,
                f'/sync/{record_type}',
                params=params
            )
            return response
        except Exception as e:
            logger.error(f"获取记录失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def delete_record(self, record_type: str, record_id: str) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.DELETE,
                f'/sync/{record_type}/{record_id}'
            )
            return response
        except Exception as e:
            logger.error(f"删除记录失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def batch_push(self, records: list[dict[str, Any]]) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.POST,
                '/sync/batch',
                data={'records': records}
            )
            return response
        except Exception as e:
            logger.error(f"批量推送失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def batch_pull(self, record_keys: list[str]) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.POST,
                '/sync/batch/pull',
                data={'keys': record_keys}
            )
            return response
        except Exception as e:
            logger.error(f"批量拉取失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def upload_file(self, file_path: str, metadata: dict[str, Any] | None = None) -> APIResponse:
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            file_hash = hashlib.md5(file_data).hexdigest()
            response = await self._request(
                HTTPMethod.POST,
                '/files/upload',
                data={'file_hash': file_hash, 'metadata': metadata or {}}
            )
            return response
        except Exception as e:
            logger.error(f"上传文件失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def download_file(self, file_id: str, save_path: str) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.GET,
                f'/files/{file_id}'
            )
            if response.success and response.data:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(response.data.get('content', b''))
            return response
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def get_sync_status(self) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.GET,
                '/sync/status'
            )
            return response
        except Exception as e:
            logger.error(f"获取同步状态失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def get_conflicts(self) -> APIResponse:
        try:
            response = await self._request(
                HTTPMethod.GET,
                '/sync/conflicts'
            )
            return response
        except Exception as e:
            logger.error(f"获取冲突列表失败: {e}")
            return APIResponse(status_code=500, error=str(e))

    async def _request(
        self,
        method: HTTPMethod,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> APIResponse:
        url = f"{self._base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = self._build_headers()
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")

        last_error = ""
        for attempt in range(self._max_retries):
            try:
                req = urllib.request.Request(
                    url, data=body, headers=headers,
                    method=method.value,
                )
                with urllib.request.urlopen(
                        req, timeout=self._timeout) as resp:
                    raw = resp.read()
                    status = resp.status
                return APIResponse(
                    status_code=status, data=self._parse_body(raw))
            except urllib.error.HTTPError as e:
                raw = e.read()
                return APIResponse(
                    status_code=e.code, data=self._parse_body(raw),
                    error=str(e.reason))
            except Exception as e:
                last_error = str(e)
                if attempt < self._max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"请求失败，{wait_time}s 后重试: {e}")
                    await self._delay(wait_time)
        return APIResponse(
            status_code=0,
            error=f"网络错误（已重试 {self._max_retries} 次）: {last_error}")

    @staticmethod
    def _parse_body(raw: bytes) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {"text": raw.decode("utf-8", errors="replace")}

    def _build_headers(self) -> dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        if self._api_key:
            headers['X-API-Key'] = self._api_key
        return headers

    async def _delay(self, seconds: float) -> None:
        import asyncio
        await asyncio.sleep(seconds)

    def on_conflict(self, callback: Callable[[SyncRecord], None]) -> None:
        self._conflict_callbacks.append(callback)

    def on_sync(self, callback: Callable[[str, str], None]) -> None:
        self._sync_callbacks.append(callback)

    def _notify_conflict(self, record_type: str, record_id: str,
                         local_data: dict, remote_data: dict) -> None:
        record = SyncRecord(
            id=record_id,
            record_type=record_type,
            action='push',
            local_data=local_data,
            remote_data=remote_data,
            status=SyncStatus.CONFLICT
        )
        for callback in self._conflict_callbacks:
            try:
                callback(record)
            except Exception as e:
                logger.error(f"冲突回调执行失败: {e}")

    def _notify_sync(self, action: str, record_id: str) -> None:
        for callback in self._sync_callbacks:
            try:
                callback(action, record_id)
            except Exception as e:
                logger.error(f"同步回调执行失败: {e}")

    def get_base_url(self) -> str:
        return self._base_url

    def set_base_url(self, url: str) -> None:
        self._base_url = url.rstrip('/')

    def get_token(self) -> str | None:
        return self._token

    def clear_token(self) -> None:
        self._token = None
        self._refresh_token = None
        self._is_authenticated = False

    def __repr__(self) -> str:
        return f"MathaAPIClient(base_url={self._base_url}, authenticated={self._is_authenticated})"


_client: MathaAPIClient | None = None


def get_api_client() -> MathaAPIClient:
    global _client
    if _client is None:
        _client = MathaAPIClient(base_url="https://api.matha.local")
    return _client


def set_api_client(client: MathaAPIClient) -> None:
    global _client
    _client = client
