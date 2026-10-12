// Matha 远程数据通道 - Web 实现（浏览器 HttpRequest）

import 'dart:convert';
import 'dart:html' as html;

Future<Map<String, dynamic>?> remoteGet(
  String baseUrl,
  String recordType,
  String recordId,
) async {
  try {
    final uri = '$baseUrl/${Uri.encodeComponent(recordType)}/${Uri.encodeComponent(recordId)}';
    final res = await html.HttpRequest.request(uri, method: 'GET');
    if (res.status == 404) return null;
    if (res.status != 200) return null;
    return jsonDecode(res.responseText!) as Map<String, dynamic>;
  } catch (_) {
    return null;
  }
}

Future<bool> remotePut(
  String baseUrl,
  String recordType,
  String recordId,
  Map<String, dynamic> data,
) async {
  try {
    final uri = '$baseUrl/${Uri.encodeComponent(recordType)}/${Uri.encodeComponent(recordId)}';
    final res = await html.HttpRequest.request(
      uri,
      method: 'PUT',
      sendData: jsonEncode(data),
      requestHeaders: {'Content-Type': 'application/json'},
    );
    final status = res.status ?? 0;
    return status >= 200 && status < 300;
  } catch (_) {
    return false;
  }
}