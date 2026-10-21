// Matha 移动端 - 协作中心
// 将协作子模块（连接 / 在线用户 / 变更历史 / 审计日志 / 语音 / 屏幕共享 /
// 聊天 / 评论）统一接入 UI，使其可实际使用。

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/collab_provider.dart';
import '../collab/change_history.dart';
import '../collab/audit_log.dart';
import '../collab/voice_call.dart';
import '../collab/screen_share.dart';
import '../collab/chat_system.dart';

class CollaborationScreen extends StatefulWidget {
  const CollaborationScreen({super.key});

  @override
  State<CollaborationScreen> createState() => _CollaborationScreenState();
}

class _CollaborationScreenState extends State<CollaborationScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 7, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final collab = context.read<CollabProvider>();
      collab.ensureIdentity(userId: 'user_${DateTime.now().millisecond}', userName: '我');
    });
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final collab = context.watch<CollabProvider>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('协作中心'),
        bottom: TabBar(
          controller: _tabs,
          isScrollable: true,
          tabs: const [
            Tab(icon: Icon(Icons.wifi), text: '连接'),
            Tab(icon: Icon(Icons.people), text: '在线'),
            Tab(icon: Icon(Icons.history), text: '变更'),
            Tab(icon: Icon(Icons.event_note), text: '审计'),
            Tab(icon: Icon(Icons.headset), text: '语音'),
            Tab(icon: Icon(Icons.screen_share), text: '共享'),
            Tab(icon: Icon(Icons.chat_bubble_outline), text: '聊天'),
          ],
        ),
      ),
      body: Column(
        children: [
          _ConnectionBar(collab: collab),
          const Divider(height: 1),
          Expanded(
            child: TabBarView(
              controller: _tabs,
              children: [
                _ConnectTab(collab: collab),
                _OnlineTab(collab: collab),
                _HistoryTab(manager: collab.changeHistory),
                _AuditTab(manager: collab.audit),
                _VoiceTab(manager: collab.voice),
                _ScreenShareTab(manager: collab.screenShare),
                _ChatTab(manager: collab.chat, documentId: collab.documentId),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ========== 连接状态栏 ==========

class _ConnectionBar extends StatelessWidget {
  final CollabProvider collab;

  const _ConnectionBar({required this.collab});

  @override
  Widget build(BuildContext context) {
    final connected = collab.isConnected;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: connected
          ? Colors.green.withValues(alpha: 0.12)
          : Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Row(
        children: [
          Icon(
            connected ? Icons.check_circle : Icons.circle_outlined,
            size: 16,
            color: connected ? Colors.green : Colors.grey,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              connected
                  ? '已连接 · ${collab.serverUrl}'
                  : (collab.lastError ?? '未连接（本地模式）'),
              style: const TextStyle(fontSize: 12),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Text(
            collab.userName,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

// ========== 连接 ==========

class _ConnectTab extends StatefulWidget {
  final CollabProvider collab;

  const _ConnectTab({required this.collab});

  @override
  State<_ConnectTab> createState() => _ConnectTabState();
}

class _ConnectTabState extends State<_ConnectTab> {
  final _urlController = TextEditingController(text: 'ws://localhost:8080/ws');
  bool _busy = false;

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    setState(() => _busy = true);
    final collab = widget.collab;
    if (collab.isConnected || collab.enabled) {
      await collab.disconnect();
    } else {
      await collab.connect(serverUrl: _urlController.text.trim());
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final collab = widget.collab;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        TextField(
          controller: _urlController,
          decoration: const InputDecoration(
            labelText: '协作服务器地址',
            hintText: 'ws://host:port/ws',
            prefixIcon: Icon(Icons.link),
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: _busy ? null : _toggle,
          icon: _busy
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Icon(collab.isConnected ? Icons.link_off : Icons.link),
          label: Text(collab.isConnected ? '断开连接' : '连接'),
        ),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('当前身份', style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                _kv('用户 ID', collab.userId),
                _kv('用户名', collab.userName),
                _kv('文档 ID', collab.documentId),
                _kv('状态', collab.isConnected ? '已连接' : '本地模式'),
                _kv('版本', collab.engine.version.toString()),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          '未连接时，变更历史 / 审计 / 聊天等仍可本地记录，连接后自动同步。',
          style: TextStyle(fontSize: 12, color: Colors.grey),
        ),
      ],
    );
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 80, child: Text(k, style: const TextStyle(color: Colors.grey))),
            Expanded(child: Text(v)),
          ],
        ),
      );
}

// ========== 在线用户 ==========

class _OnlineTab extends StatelessWidget {
  final CollabProvider collab;

  const _OnlineTab({required this.collab});

  @override
  Widget build(BuildContext context) {
    final users = collab.engine.onlineUsers;
    if (users.isEmpty) {
      return const Center(child: Text('暂无在线用户'));
    }
    return ListView(
      children: [
        for (final u in users)
          ListTile(
            leading: CircleAvatar(child: Text(u.isNotEmpty ? u[0].toUpperCase() : '?')),
            title: Text(u),
          ),
      ],
    );
  }
}

// ========== 变更历史 ==========

class _HistoryTab extends StatelessWidget {
  final ChangeHistoryManager manager;

  const _HistoryTab({required this.manager});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: manager,
      builder: (context, _) {
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Chip(label: Text('版本 ${manager.currentVersion}/${manager.versionCount - 1}')),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.undo),
                    tooltip: '撤销',
                    onPressed: manager.canUndo ? () {
                      manager.undo();
                      _snack(context, '已撤销到版本 ${manager.currentVersion}');
                    } : null,
                  ),
                  IconButton(
                    icon: const Icon(Icons.redo),
                    tooltip: '重做',
                    onPressed: manager.canRedo ? () {
                      manager.redo();
                      _snack(context, '已重做到版本 ${manager.currentVersion}');
                    } : null,
                  ),
                  IconButton(
                    icon: const Icon(Icons.add),
                    tooltip: '记录一次变更',
                    onPressed: () => manager.addChange(
                      action: '编辑',
                      entityId: 'doc',
                      data: {'v': manager.versionCount},
                    ),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: manager.changes.isEmpty
                  ? const Center(child: Text('暂无变更记录，点 + 添加'))
                  : ListView.builder(
                      itemCount: manager.changes.length,
                      itemBuilder: (context, i) {
                        final c = manager.changes[i];
                        final active = i == manager.currentVersion;
                        return ListTile(
                          dense: true,
                          selected: active,
                          leading: CircleAvatar(
                            radius: 12,
                            child: Text('${c.version}', style: const TextStyle(fontSize: 10)),
                          ),
                          title: Text(c.action),
                          subtitle: Text('${c.entityType} · ${_time(c.timestamp)}'),
                          trailing: IconButton(
                            icon: const Icon(Icons.restore, size: 18),
                            tooltip: '回退到此',
                            onPressed: () {
                              manager.revertTo(c.version);
                              _snack(context, '已回退到版本 ${c.version}');
                            },
                          ),
                        );
                      },
                    ),
            ),
          ],
        );
      },
    );
  }

  static void _snack(BuildContext context, String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }
}

// ========== 审计日志 ==========

class _AuditTab extends StatelessWidget {
  final AuditManager manager;

  const _AuditTab({required this.manager});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: manager,
      builder: (context, _) {
        final entries = manager.recent(200);
        if (entries.isEmpty) {
          return const Center(child: Text('暂无审计记录'));
        }
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Expanded(child: Text('共 ${manager.count} 条', style: const TextStyle(fontSize: 12))),
                  TextButton.icon(
                    icon: const Icon(Icons.clear_all, size: 16),
                    label: const Text('清空'),
                    onPressed: manager.clear,
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: ListView.builder(
                itemCount: entries.length,
                itemBuilder: (context, i) {
                  final e = entries[i];
                  return ListTile(
                    dense: true,
                    leading: const Icon(Icons.event_note, size: 18),
                    title: Text('${e.userId} · ${e.action}'),
                    subtitle: e.detail.isEmpty ? null : Text(e.detail),
                    trailing: Text(_time(e.timestamp), style: const TextStyle(fontSize: 11)),
                  );
                },
              ),
            ),
          ],
        );
      },
    );
  }
}

// ========== 语音通话 ==========

class _VoiceTab extends StatelessWidget {
  final VoiceCallManager manager;

  const _VoiceTab({required this.manager});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: manager,
      builder: (context, _) {
        return ListView(
          padding: const EdgeInsets.all(12),
          children: [
            VoiceCallPanel(manager: manager),
            const SizedBox(height: 12),
            if (manager.isMember(manager.memberList.isNotEmpty
                    ? manager.memberList.first.userId
                    : ''))
              const SizedBox.shrink(),
            OutlinedButton.icon(
              icon: const Icon(Icons.sim_card_alert),
              label: const Text('模拟成员发言状态'),
              onPressed: manager.memberList.isEmpty
                  ? null
                  : () {
                      final m = manager.memberList.first;
                      manager.setSpeaking(m.userId, !m.speaking);
                    },
            ),
          ],
        );
      },
    );
  }
}

// ========== 屏幕共享 ==========

class _ScreenShareTab extends StatefulWidget {
  final ScreenShareManager manager;

  const _ScreenShareTab({required this.manager});

  @override
  State<_ScreenShareTab> createState() => _ScreenShareTabState();
}

class _ScreenShareTabState extends State<_ScreenShareTab> {
  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.manager,
      builder: (context, _) {
        final m = widget.manager;
        return ListView(
          padding: const EdgeInsets.all(12),
          children: [
            ScreenShareWidget(manager: m),
            const SizedBox(height: 12),
            Row(
              children: [
                if (!m.isActive)
                  FilledButton.icon(
                    icon: const Icon(Icons.cast),
                    label: const Text('开始共享'),
                    onPressed: m.start,
                  )
                else ...[
                  if (m.amPresenter)
                    FilledButton.tonalIcon(
                      icon: const Icon(Icons.stop),
                      label: const Text('停止共享'),
                      onPressed: () => m.stop(),
                    ),
                  const SizedBox(width: 8),
                  Text('观看者 ${m.viewerCount} · 帧 ${m.frameCount}'),
                ],
              ],
            ),
            if (m.isActive && !m.amPresenter)
              OutlinedButton.icon(
                icon: Icon(m.amViewer ? Icons.visibility_off : Icons.visibility),
                label: Text(m.amViewer ? '退出观看' : '进入观看'),
                onPressed: m.amViewer ? m.unwatch : m.watch,
              ),
            if (m.isActive && m.amPresenter)
              OutlinedButton.icon(
                icon: const Icon(Icons.add_photo_alternate),
                label: const Text('推送一帧（演示）'),
                onPressed: () => m.publishFrame({'bytes': <int>[]}),
              ),
          ],
        );
      },
    );
  }
}

// ========== 聊天 ==========

class _ChatTab extends StatefulWidget {
  final ChatManager manager;
  final String documentId;

  const _ChatTab({required this.manager, required this.documentId});

  @override
  State<_ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends State<_ChatTab> {
  final _input = TextEditingController();

  @override
  void initState() {
    super.initState();
    widget.manager.getOrCreateSession(widget.documentId);
    widget.manager.switchSession(widget.documentId);
  }

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty) return;
    await widget.manager.sendMessage(sessionId: widget.documentId, content: text);
    _input.clear();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.manager,
      builder: (context, _) {
        final messages = widget.manager.getMessages(widget.documentId);
        return Column(
          children: [
            Expanded(
              child: messages.isEmpty
                  ? const Center(child: Text('暂无消息'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(8),
                      itemCount: messages.length,
                      itemBuilder: (context, i) {
                        final m = messages[i];
                        return ChatMessageWidget(message: m);
                      },
                    ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _input,
                      decoration: const InputDecoration(
                        hintText: '输入消息...',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    icon: const Icon(Icons.send),
                    onPressed: _send,
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

// ========== 时间格式 ==========

String _time(DateTime t) =>
    '${t.hour.toString().padLeft(2, '0')}:'
    '${t.minute.toString().padLeft(2, '0')}:'
    '${t.second.toString().padLeft(2, '0')}';
