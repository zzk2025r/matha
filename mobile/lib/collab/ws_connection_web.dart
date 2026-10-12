// Matha 协作功能 - WebSocket 连接工厂（Web 实现）
// 浏览器环境不支持自定义 headers

import 'package:web_socket_channel/html.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// 使用 HtmlWebSocketChannel 创建 WebSocket 连接
WebSocketChannel createCollabChannel(String url, {Map<String, dynamic>? headers}) =>
    HtmlWebSocketChannel.connect(Uri.parse(url));