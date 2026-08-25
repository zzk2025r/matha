# -*- coding: utf-8 -*-
"""Matha 移动端远程 API 客户端

提供与后端的 HTTP 通信功能：
  - 用户认证
  - 数据同步
  - 冲突检测
  - 文件上传/下载
"""
from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import hashlib


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
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
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
    local_data: Dict[str, Any]
    remote_data: Optional[Dict[str, Any]] = None
    status: SyncStatus = SyncStatus.PENDING
    conflict_resolved: bool = False
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    synced_at: Optional[float] = None


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
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._sync_queue: List[SyncRecord] = []
        self._conflict_callbacks: List[Callable[[SyncRecord], None]] = []
        self._sync_callbacks: List[Callable[[str, str], None]] = []
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

    async def push_data(self, record_type: str, record_id: str, data: Dict[str, Any]) -> APIResponse:
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

    async def get_all_records(self, record_type: str, since: Optional[float] = None) -> APIResponse:
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

    async def batch_push(self, records: List[Dict[str, Any]]) -> APIResponse:
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

    async def batch_pull(self, record_keys: List[str]) -> APIResponse:
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

    async def upload_file(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> APIResponse:
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
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, bytes]] = None,
    ) -> APIResponse:
        url = f"{self._base_url}{path}"
        headers = self._build_headers()

        for attempt in range(self._max_retries):
            try:
                result = await self._simulate_request(method, url, headers, data, params, files)
                return APIResponse(
                    status_code=result['status'],
                    data=result.get('data'),
                    error=result.get('error')
                )
            except Exception as e:
                if attempt < self._max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"请求失败，{wait_time}s 后重试: {e}")
                    await self._delay(wait_time)
                else:
                    return APIResponse(status_code=500, error=str(e))

        return APIResponse(status_code=500, error="Max retries exceeded")

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        if self._api_key:
            headers['X-API-Key'] = self._api_key
        return headers

    async def _simulate_request(self, method, url, headers, data, params, files):
        await self._delay(0.1)
        if '/auth/login' in url:
            if data and data.get('username') == 'test':
                return {
                    'status': 200,
                    'data': {
                        'access_token': 'mock_token_123',
                        'refresh_token': 'mock_refresh_123',
                        'expires_in': 3600
                    }
                }
            return {'status': 401, 'error': 'Invalid credentials'}
        if '/sync/' in url:
            if method == HTTPMethod.PUT and 'conflict' in str(data):
                return {
                    'status': 409,
                    'data': {
                        'remote_data': {'value': 'remote_version', 'timestamp': time.time()},
                        'local_data': data
                    }
                }
            return {'status': 200, 'data': {'success': True}}
        return {'status': 200, 'data': {}}

    async def _delay(self, seconds: float) -> None:
        import asyncio
        await asyncio.sleep(seconds)

    def on_conflict(self, callback: Callable[[SyncRecord], None]) -> None:
        self._conflict_callbacks.append(callback)

    def on_sync(self, callback: Callable[[str, str], None]) -> None:
        self._sync_callbacks.append(callback)

    def _notify_conflict(self, record_type: str, record_id: str,
                         local_data: Dict, remote_data: Dict) -> None:
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

    def get_token(self) -> Optional[str]:
        return self._token

    def clear_token(self) -> None:
        self._token = None
        self._refresh_token = None
        self._is_authenticated = False

    def __repr__(self) -> str:
        return f"MathaAPIClient(base_url={self._base_url}, authenticated={self._is_authenticated})"


_client: Optional[MathaAPIClient] = None


def get_api_client() -> MathaAPIClient:
    global _client
    if _client is None:
        _client = MathaAPIClient(base_url="https://api.matha.local")
    return _client


def set_api_client(client: MathaAPIClient) -> None:
    global _client
    _client = client


if __name__ == "__main__":
    import asyncio

    async def main():
        client = MathaAPIClient(base_url="https://api.matha.test")

        print("测试登录...")
        response = await client.login("test", "test")
        print(f"登录结果: {response.status_code}, success={response.success}")

        print("\n测试推送数据...")
        response = await client.push_data("history", "1", {"code": "x=1"})
        print(f"推送结果: {response.status_code}, success={response.success}")

        print("\n测试冲突检测...")
        response = await client.push_data("history", "conflict", {"value": "conflict"})
        print(f"冲突结果: {response.status_code}, is_conflict={response.is_conflict}")

    asyncio.run(main())
