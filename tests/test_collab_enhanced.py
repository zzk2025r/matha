"""协作引擎增强测试：语音通话/屏幕共享/审计日志/变更历史。"""

import uuid

import pytest

from src.collaboration import (
    AuditEntry,
    Operation,
    ScreenShareSession,
    VoiceMember,
    create_session,
    get_session,
)


@pytest.fixture
def session():
    s = create_session("sess_media", "proj_media")
    s.join("alice", "Alice", "#e74c3c")
    s.join("bob", "Bob", "#2ecc71")
    yield s
    from src import collaboration
    collaboration._sessions.pop("sess_media", None)


def _op(user_id, action="create", entity_id="node_1"):
    return Operation(
        op_id=uuid.uuid4().hex,
        user_id=user_id,
        timestamp=0.0,
        target_entity="node",
        entity_id=entity_id,
        action=action,
        data={},
    )


# ── 审计日志 ────────────────────────────────────────────────────────────────

class TestAuditLog:
    def test_audit_records_membership(self, session):
        entries = session.get_audit_log()
        actions = {e["action"] for e in entries}
        assert "join" in actions
        assert len(entries) == 2

    def test_audit_records_operations(self, session):
        session.broadcast_operation(_op("alice"))
        session.send_message("bob", "Bob", "你好")
        session.create_invite("alice", "Alice")
        summary = session.get_audit_summary()
        assert summary["op"] == 1
        assert summary["chat"] == 1
        assert summary["invite"] == 1
        assert session.audit_count >= 5

    def test_audit_order_newest_first(self, session):
        session.broadcast_operation(_op("alice"))
        log = session.get_audit_log(limit=3)
        assert log[0]["action"] == "op"

    def test_audit_callback(self, session):
        received = []
        session.on_audit(lambda entry: received.append(entry))
        session.send_message("alice", "Alice", "hi")
        assert len(received) == 1
        assert isinstance(received[0], AuditEntry)

    def test_audit_detail_and_leave(self, session):
        session.leave("bob")
        log = session.get_audit_log()
        assert any(e["action"] == "leave" and "Bob" in e["detail"] for e in log)


# ── 语音通话 ────────────────────────────────────────────────────────────────

class TestVoiceCall:
    def test_join_leave(self, session):
        assert session.voice_join("alice") is True
        assert session.voice_join("alice") is False, "重复加入应失败"
        assert session.voice_member_count == 1
        assert session.voice_leave("alice") is True
        assert session.voice_member_count == 0

    def test_join_non_member(self, session):
        assert session.voice_join("stranger") is False

    def test_mute_and_speaking(self, session):
        session.voice_join("alice")
        assert session.voice_set_muted("alice", True) is True
        member = session.voice_members["alice"]
        assert member.muted is True
        assert session.voice_set_speaking("alice", True) is True
        assert member.speaking is True
        assert session.voice_state["active"] is True
        assert session.voice_state["members"]["alice"]["muted"] is True

    def test_voice_member_type(self, session):
        session.voice_join("bob")
        assert isinstance(session.voice_members["bob"], VoiceMember)

    def test_voice_audit(self, session):
        session.voice_join("alice")
        summary = session.get_audit_summary()
        assert summary["voice_join"] == 1


# ── 屏幕共享 ────────────────────────────────────────────────────────────────

class TestScreenShare:
    def test_start_stop(self, session):
        assert session.start_screen_share("alice") is True
        assert session.share_state["active"] is True
        assert session.share_state["presenter_id"] == "alice"
        assert session.stop_screen_share("alice") is True
        assert session.share_state["active"] is False

    def test_start_by_non_member(self, session):
        assert session.start_screen_share("stranger") is False

    def test_stop_by_wrong_presenter(self, session):
        session.start_screen_share("alice")
        assert session.stop_screen_share("bob") is False
        assert session.share_state["active"] is True

    def test_publish_and_watch_frames(self, session):
        session.start_screen_share("alice")
        assert session.watch_share("bob") is True
        assert session.share_state["viewer_count"] == 1
        frame_no = session.publish_frame("alice", {"data": "frame-1"})
        assert frame_no == 1
        session.publish_frame("alice", {"data": "frame-2"})
        latest = session.latest_frame()
        assert latest == {"data": "frame-2"}
        recent = session.recent_frames(2)
        assert len(recent) == 2
        assert session.share_state["frame_count"] == 2

    def test_publish_before_share(self, session):
        assert session.publish_frame("alice", {"data": "x"}) is None

    def test_share_session_type(self, session):
        session.start_screen_share("alice")
        assert isinstance(session._share, ScreenShareSession)

    def test_share_audit(self, session):
        session.start_screen_share("alice")
        session.stop_screen_share("alice")
        summary = session.get_audit_summary()
        assert summary["share_start"] == 1
        assert summary["share_stop"] == 1


# ── 变更历史 ────────────────────────────────────────────────────────────────

class TestChangeHistory:
    def test_version_count_grows(self, session):
        assert session.version_count == 0
        session.broadcast_operation(_op("alice", action="create"))
        assert session.version_count == 1
        session.broadcast_operation(_op("alice", action="update"))
        assert session.version_count == 2

    def test_change_history_entries(self, session):
        session.broadcast_operation(_op("alice", action="create", entity_id="n1"))
        history = session.get_change_history()
        assert len(history) == 1
        assert history[0]["version"] == 0
        assert history[0]["action"] == "create"
        assert history[0]["entity_id"] == "n1"

    def test_revert_to_version(self, session):
        session.broadcast_operation(_op("alice", action="create", entity_id="n1"))
        session.broadcast_operation(_op("alice", action="create", entity_id="n2"))
        assert len(session.get_state()["state"]["node"]) == 2
        session.revert_to_version(0)
        state = session.get_state()["state"]
        assert len(state.get("node", {})) == 1
        assert session.version_count == 1

    def test_revert_invalid_version(self, session):
        with pytest.raises(ValueError):
            session.revert_to_version(99)
        with pytest.raises(ValueError):
            session.revert_to_version(-1)


# ── 会话状态扩展 ────────────────────────────────────────────────────────────

class TestSessionState:
    def test_state_includes_media(self, session):
        session.voice_join("alice")
        session.start_screen_share("bob")
        state = session.get_state()
        assert state["voice"]["active"] is True
        assert state["screen_share"]["active"] is True
        assert state["audit_count"] >= 4
        assert "version_count" in state

    def test_global_session_registry(self, session):
        assert get_session("sess_media") is not None
