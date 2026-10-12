// Matha 协作功能 - WebSocket 连接工厂（VM/IO 实现，支持自定义 headers）

import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// 使用 dart:io 创建 WebSocket 连接
WebSocketChannel createCollabChannel(String url, {Map<String, dynamic>? headers}) =>
    IOWebSocketChannel.connect(Uri.parse(url), headers: headers ?? const {});