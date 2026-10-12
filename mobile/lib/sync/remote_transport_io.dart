// Matha 远程数据通道 - VM 实现（dart:io HttpClient）

import 'dart:convert';
import 'dart:io';

Future<Map<String, dynamic>?> remoteGet(
  String baseUrl,
  String recordType,
  String recordId,
) async {
  final client = HttpClient();
  try {
    final uri = Uri.parse(
      '$baseUrl/${Uri.encodeComponent(recordType)}/${Uri.encodeComponent(recordId)}',
    );
    final req = await client.getUrl(uri);
    final res = await req.close();
    if (res.statusCode == 404) return null;
    if (res.statusCode != 200) return null;
    final body = await res.transform(utf8.decoder).join();
    return jsonDecode(body) as Map<String, dynamic>;
  } catch (_) {
    return null;
  } finally {
    client.close();
  }
}

Future<bool> remotePut(
  String baseUrl,
  String recordType,
  String recordId,
  Map<String, dynamic> data,
) async {
  final client = HttpClient();
  try {
    final uri = Uri.parse(
      '$baseUrl/${Uri.encodeComponent(recordType)}/${Uri.encodeComponent(recordId)}',
    );
    final req = await client.putUrl(uri);
    req.headers.contentType = ContentType.json;
    req.write(jsonEncode(data));
    final res = await req.close();
    await res.drain<void>();
    return res.statusCode >= 200 && res.statusCode < 300;
  } catch (_) {
    return false;
  } finally {
    client.close();
  }
}