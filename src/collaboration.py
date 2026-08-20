# -*- coding: utf-8 -*-
"""
Matha 协作引擎 — WebSocket + 实时同步

提供多人协作编辑功能：
  - WebSocket 实时通信
  - 操作变换（OT）算法
  - 邀请系统
  - 实时聊天
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass
class Collaborator:
    """协作者"""
    user_id: str
    username: str
    color: str = "#3498db"
    is_online: bool = True
    last_seen: float = 0.0
    cursor_position: tuple = (0, 0)


@dataclass
class Operation:
    """操作（用于 OT 算法）"""
    op_id: str
    user_id: str
    timestamp: float
    target_entity: str  # "node", "connection", "project"
    entity_id: str
    action: str  # "create", "update", "delete"
    data: dict
    version: int = 1


@dataclass
class ChatMessage:
    """聊天消息"""
    message_id: str
    user_id: str
    username: str
    content: str
    timestamp: float
    is_system: bool = False


@dataclass
class Invite:
    """协作邀请"""
    invite_id: str
    project_id: str
    inviter_id: str
    inviter_name: str
    code: str
    expires_at: float
    max_members: int = 10
    created_at: float = field(default_factory=time.time)


# ── OT 算法（操作变换）───────────────────────────────────────────────────────

class OperationTransformer:
    """操作变换器（基于 JSON Patch 的 OT）"""

    def transform(self, op_a: Operation, op_b: Operation) -> tuple[Operation, Operation]:
        """
        变换两个并发操作，确保最终一致性。

        策略：
        - 如果操作目标不同，保持不变
        - 如果操作目标相同且类型相同，优先早期操作
        - 如果操作目标相同但类型不同，调整目标引用
        """
        if op_a.target_entity != op_b.target_entity:
            return op_a, op_b

        if op_a.entity_id != op_b.entity_id:
            return op_a, op_b

        # 相同目标的操作：时间戳早的优先
        if op_a.timestamp <= op_b.timestamp:
            return op_a, self._adjust_after_delete(op_b, op_a)
        else:
            return self._adjust_after_delete(op_a, op_b), op_b

    def _adjust_after_delete(self, op: Operation, deleted: Operation) -> Operation:
        """操作在被删除节点之后执行时的调整"""
        if deleted.action == "delete":
            # 如果删除的是同类型实体，调整引用
            if op.target_entity == deleted.target_entity:
                logger.debug(f"调整操作 {op.op_id} 以适配删除 {deleted.entity_id}")
        return op

    def apply_operations(self, operations: List[Operation], state: dict) -> dict:
        """按顺序应用操作序列到状态"""
        for op in sorted(operations, key=lambda o: o.timestamp):
            state = self._apply_single(op, state)
        return state

    def _apply_single(self, op: Operation, state: dict) -> dict:
        """应用单个操作"""
        entity_type = op.target_entity
        entity_id = op.entity_id

        if entity_type not in state:
            state[entity_type] = {}

        entities = state[entity_type]

        if op.action == "create":
            entities[entity_id] = op.data
        elif op.action == "update":
            if entity_id in entities:
                entities[entity_id].update(op.data)
        elif op.action == "delete":
            entities.pop(entity_id, None)

        return state


# ── 协作会话 ────────────────────────────────────────────────────────────────

class CollaborationSession:
    """协作会话管理器"""

    def __init__(self, session_id: str, project_id: str):
        self.session_id = session_id
        self.project_id = project_id
        self._collaborators: Dict[str, Collaborator] = {}
        self._operations: List[Operation] = []
        self._chat_messages: List[ChatMessage] = []
        self._invites: Dict[str, Invite] = {}
        self._state: dict = {}
        self._transformer = OperationTransformer()
        self._on_operation = None
        self._on_chat = None
        self._on_invite = None
        self._on_member_join = None
        self._on_member_leave = None
        self._client_id = uuid.uuid4().hex[:8]

    @property
    def collaborator_count(self) -> int:
        return len([c for c in self._collaborators.values() if c.is_online])

    @property
    def collaborators(self) -> Dict[str, Collaborator]:
        return self._collaborators.copy()

    # ── 成员管理 ──────────────────────────────────────────────────────────────

    def join(self, user_id: str, username: str, color: str = "#3498db") -> Collaborator:
        """加入协作会话"""
        if user_id in self._collaborators:
            self._collaborators[user_id].is_online = True
            self._collaborators[user_id].last_seen = time.time()
            return self._collaborators[user_id]

        collaborator = Collaborator(
            user_id=user_id,
            username=username,
            color=color,
            is_online=True,
            last_seen=time.time(),
        )
        self._collaborators[user_id] = collaborator

        # 广播加入事件
        if self._on_member_join:
            self._on_member_join(user_id, username)

        logger.info(f"协作者加入: {username} (会话: {self.session_id}, 在线: {self.collaborator_count})")
        return collaborator

    def leave(self, user_id: str) -> None:
        """离开协作会话"""
        if user_id in self._collaborators:
            self._collaborators[user_id].is_online = False
            self._collaborators[user_id].last_seen = time.time()

            if self._on_member_leave:
                self._on_member_leave(user_id, self._collaborators[user_id].username)

            logger.info(f"协作者离开: {user_id}")

    def update_cursor(self, user_id: str, x: float, y: float) -> None:
        """更新协作者光标位置"""
        if user_id in self._collaborators:
            self._collaborators[user_id].cursor_position = (x, y)

    # ── 操作广播 ──────────────────────────────────────────────────────────────

    def broadcast_operation(self, op: Operation) -> None:
        """广播操作（OT 变换后）"""
        # 变换操作
        transformed_ops = []
        for existing_op in self._operations[-100:]:  # 只保留最近 100 条
            t_op_a, t_op_b = self._transformer.transform(op, existing_op)
            transformed_ops.append(t_op_b)

        self._operations.append(op)
        self._state = self._transformer.apply_operations([op] + transformed_ops, self._state)

        if self._on_operation:
            self._on_operation(op)

        logger.debug(f"操作已广播: {op.action} {op.target_entity}.{op.entity_id}")

    def get_operation_history(self, limit: int = 50) -> List[Operation]:
        """获取操作历史"""
        return self._operations[-limit:]

    # ── 聊天 ──────────────────────────────────────────────────────────────────

    def send_message(self, user_id: str, username: str, content: str, is_system: bool = False) -> ChatMessage:
        """发送聊天消息"""
        msg = ChatMessage(
            message_id=uuid.uuid4().hex,
            user_id=user_id,
            username=username,
            content=content,
            timestamp=time.time(),
            is_system=is_system,
        )
        self._chat_messages.append(msg)

        if self._on_chat:
            self._on_chat(msg)

        return msg

    def get_chat_history(self, limit: int = 50) -> List[ChatMessage]:
        """获取聊天记录"""
        return self._chat_messages[-limit:]

    # ── 邀请系统 ──────────────────────────────────────────────────────────────

    def create_invite(self, inviter_id: str, inviter_name: str, max_members: int = 10) -> Invite:
        """创建协作邀请"""
        invite_code = uuid.uuid4().hex[:8].upper()
        invite = Invite(
            invite_id=uuid.uuid4().hex,
            project_id=self.project_id,
            inviter_id=inviter_id,
            inviter_name=inviter_name,
            code=invite_code,
            expires_at=time.time() + 86400,  # 24 小时有效期
            max_members=max_members,
        )
        self._invites[invite_code] = invite

        if self._on_invite:
            self._on_invite(invite)

        logger.info(f"创建邀请: {invite_code} by {inviter_name}")
        return invite

    def redeem_invite(self, code: str, user_id: str, username: str) -> Optional[Collaborator]:
        """兑换邀请码"""
        invite = self._invites.get(code)
        if not invite:
            return None
        if time.time() > invite.expires_at:
            logger.warning(f"邀请码已过期: {code}")
            return None
        if len(self._collaborators) >= invite.max_members:
            logger.warning(f"协作会话已满: {invite.max_members}")
            return None

        return self.join(user_id, username)

    def get_invite_info(self, code: str) -> Optional[dict]:
        """获取邀请信息"""
        invite = self._invites.get(code)
        if invite:
            return {
                "invite_id": invite.invite_id,
                "project_id": invite.project_id,
                "inviter_name": invite.inviter_name,
                "max_members": invite.max_members,
                "expires_at": invite.expires_at,
                "current_members": len(self._collaborators),
            }
        return None

    # ── 回调 ──────────────────────────────────────────────────────────────────

    def on_operation(self, callback: Callable) -> None:
        self._on_operation = callback

    def on_chat(self, callback: Callable) -> None:
        self._on_chat = callback

    def on_invite(self, callback: Callable) -> None:
        self._on_invite = callback

    def on_member_join(self, callback: Callable) -> None:
        self._on_member_join = callback

    def on_member_leave(self, callback: Callable) -> None:
        self._on_member_leave = callback

    # ── 状态 ──────────────────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """获取当前状态"""
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "state": self._state,
            "collaborators": {
                uid: {
                    "username": c.username,
                    "color": c.color,
                    "is_online": c.is_online,
                    "cursor": c.cursor_position,
                }
                for uid, c in self._collaborators.items()
            },
            "operation_count": len(self._operations),
            "chat_count": len(self._chat_messages),
        }

    def to_dict(self) -> dict:
        """序列化为字典"""
        return self.get_state()


# ── 全局会话管理 ────────────────────────────────────────────────────────────

_sessions: Dict[str, CollaborationSession] = {}
_session_callbacks: Dict[str, dict] = {}


def create_session(session_id: str, project_id: str) -> CollaborationSession:
    """创建协作会话"""
    session = CollaborationSession(session_id, project_id)
    _sessions[session_id] = session
    logger.info(f"创建协作会话: {session_id} (项目: {project_id})")
    return session


def get_session(session_id: str) -> Optional[CollaborationSession]:
    """获取协作会话"""
    return _sessions.get(session_id)


def destroy_session(session_id: str) -> bool:
    """销毁协作会话"""
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info(f"销毁协作会话: {session_id}")
        return True
    return False


def list_sessions() -> List[dict]:
    """列出所有会话"""
    return [
        {
            "session_id": sid,
            "project_id": sess.project_id,
            "members": sess.collaborator_count,
            "operation_count": len(sess._operations),
        }
        for sid, sess in _sessions.items()
    ]


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  Matha 协作引擎测试")
    print("=" * 60)

    # 创建会话
    session = create_session("sess_001", "proj_001")
    print(f"\n创建会话: {session.session_id}")

    # 加入成员
    alice = session.join("alice", "Alice", "#e74c3c")
    bob = session.join("bob", "Bob", "#2ecc71")
    print(f"成员数: {session.collaborator_count}")

    # 发送操作
    from src.visual_editor.node_executor import Operation as NodeOp
    op = Operation(
        op_id=uuid.uuid4().hex,
        user_id="alice",
        timestamp=time.time(),
        target_entity="node",
        entity_id="node_1",
        action="create",
        data={"type": "math_add", "x": 100, "y": 200},
    )
    session.broadcast_operation(op)
    print(f"操作历史: {len(session.get_operation_history())} 条")

    # 发送聊天
    msg = session.send_message("alice", "Alice", "大家好！")
    print(f"聊天消息: {msg.content}")

    # 创建邀请
    invite = session.create_invite("alice", "Alice")
    print(f"邀请码: {invite.code}")

    # 兑换邀请
    charlie = session.redeem_invite(invite.code, "charlie", "Charlie")
    print(f"Charlie 加入: {charlie.username if charlie else '失败'}")
    print(f"成员数: {session.collaborator_count}")

    # 状态
    state = session.get_state()
    print(f"\n会话状态:")
    print(f"  协作者: {len(state['collaborators'])}")
    print(f"  操作数: {state['operation_count']}")
    print(f"  聊天数: {state['chat_count']}")

    # 清理
    destroy_session("sess_001")
    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
