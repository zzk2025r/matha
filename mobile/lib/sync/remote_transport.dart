// Matha 远程数据通道 - 平台自动适配
// VM 使用 dart:io HttpClient；Web 使用浏览器 HttpRequest

import 'remote_transport_io.dart' if (dart.library.html) 'remote_transport_web.dart' as impl;

/// 获取远程记录；记录不存在或请求失败返回 null
Future<Map<String, dynamic>?> remoteGet(
  String baseUrl,
  String recordType,
  String recordId,
) => impl.remoteGet(baseUrl, recordType, recordId);

/// 保存记录到远程
Future<bool> remotePut(
  String baseUrl,
  String recordType,
  String recordId,
  Map<String, dynamic> data,
) => impl.remotePut(baseUrl, recordType, recordId, data);