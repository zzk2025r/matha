// Matha 协作功能 - WebSocket 连接工厂（平台自适应）
// VM 使用 dart:io 实现（支持自定义 headers），Web 使用 HtmlWebSocketChannel

import 'package:web_socket_channel/web_socket_channel.dart';
import 'ws_connection_io.dart' if (dart.library.html) 'ws_connection_web.dart' as platform;

/// 创建跨平台 WebSocket 连接
WebSocketChannel createCollabChannel(String url, {Map<String, dynamic>? headers}) =>
    platform.createCollabChannel(url, headers: headers);