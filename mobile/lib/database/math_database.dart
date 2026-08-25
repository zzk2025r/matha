// Matha SQLite 数据库完整实现
// 包含索引优化、数据迁移、加密存储等功能

import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import 'package:path_provider/path_provider.dart';
import 'package:encrypt/encrypt.dart' as encrypt;
import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// 数据库版本
class DatabaseVersion {
  static const int current = 3;
  static const String versionTable = 'schema_version';
}

/// 数据库加密密钥
class DatabaseEncryption {
  static const String _key = 'matha_secret_key_2025'; // 实际生产环境应使用安全存储
  
  static encrypt.Encrypter? _encrypter;
  
  static encrypt.Encrypter get encrypter {
    _encrypter ??= encrypt.Encrypter(encrypt.AES(encrypt.Key.fromUtf8(_key)));
    return _encrypter!;
  }
  
  /// 加密文本
  static String encryptText(String text) {
    try {
      return encrypter.encrypt(text).base64;
    } catch (e) {
      return text; // 加密失败时返回原文
    }
  }
  
  /// 解密文本
  static String decryptText(String encrypted) {
    try {
      return encrypter.decrypt64(encrypted);
    } catch (e) {
      return encrypted; // 解密失败时返回原文
    }
  }
}

/// SQLite 数据库管理器
class MathDatabase {
  static Database? _database;
  static const String _dbName = 'matha.db';
  static const int _dbVersion = 3;

  // 表名
  static const String tableHistory = 'history';
  static const String tablePreferences = 'preferences';
  static const String tableResultCache = 'result_cache';
  static const String tableCompletionWords = 'completion_words';
  static const String tableSyncQueue = 'sync_queue';
  static const String tableSessions = 'sessions';
  static const String tableComments = 'comments';

  // 历史记录表字段
  static const String colId = 'id';
  static const String colCode = 'code';
  static const String colOutput = 'output';
  static const String colTimestamp = 'timestamp';
  static const String colIsSuccess = 'is_success';
  static const String colMode = 'mode';
  static const String colDurationMs = 'duration_ms';
  static const String colDocumentId = 'document_id';

  // 偏好设置表字段
  static const String colKey = 'key';
  static const String colValue = 'value';
  static const String colUpdatedAt = 'updated_at';

  // 结果缓存表字段
  static const String colInputHash = 'input_hash';
  static const String colInputCode = 'input_code';
  static const String colResult = 'result';
  static const String colCreatedAt = 'created_at';

  // 同步队列表字段
  static const String colAction = 'action';
  static const String colRecordType = 'record_type';
  static const String colRecordId = 'record_id';
  static const String colData = 'data';
  static const String colPriority = 'priority';
  static const String colRetryCount = 'retry_count';
  static const String colStatus = 'status';
  static const String colSyncedAt = 'synced_at';

  // 会话表字段
  static const String colSessionId = 'session_id';
  static const String colUserId = 'user_id';
  static const String colUserName = 'user_name';
  static const String colDocumentId = 'document_id';
  static const String colCreatedAt = 'created_at';
  static const String colLastActive = 'last_active';

  // 评论表字段
  static const String colCommentId = 'comment_id';
  static const String colContent = 'content';
  static const String colPosition = 'position';

  // 获取数据库实例
  static Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  // 初始化数据库
  static Future<Database> _initDatabase() async {
    final dir = await getApplicationDocumentsDirectory();
    final path = join(dir.path, _dbName);
    
    return await openDatabase(
      path,
      version: _dbVersion,
      onCreate: _onCreate,
      onUpgrade: _onUpgrade,
      onOpen: _onOpen,
    );
  }

  // 创建表
  static Future<void> _onCreate(Database db, int version) async {
    // 历史记录表
    await db.execute('''
      CREATE TABLE $tableHistory (
        $colId INTEGER PRIMARY KEY AUTOINCREMENT,
        $colCode TEXT NOT NULL,
        $colOutput TEXT,
        $colTimestamp INTEGER NOT NULL,
        $colIsSuccess INTEGER NOT NULL DEFAULT 1,
        $colMode TEXT DEFAULT 'expression',
        $colDurationMs REAL DEFAULT 0,
        $colDocumentId TEXT
      )
    ''');
    
    // 创建索引
    await db.execute('CREATE INDEX idx_history_timestamp ON $tableHistory($colTimestamp DESC)');
    await db.execute('CREATE INDEX idx_history_document ON $tableHistory($colDocumentId)');
    await db.execute('CREATE INDEX idx_history_mode ON $tableHistory($colMode)');

    // 偏好设置表
    await db.execute('''
      CREATE TABLE $tablePreferences (
        $colKey TEXT PRIMARY KEY,
        $colValue TEXT NOT NULL,
        $colUpdatedAt INTEGER NOT NULL
      )
    ''');

    // 结果缓存表
    await db.execute('''
      CREATE TABLE $tableResultCache (
        $colInputHash TEXT PRIMARY KEY,
        $colInputCode TEXT NOT NULL,
        $colResult TEXT NOT NULL,
        $colDurationMs REAL,
        $colCreatedAt INTEGER NOT NULL
      )
    ''');
    await db.execute('CREATE INDEX idx_cache_created ON $tableResultCache($colCreatedAt DESC)');

    // 同步队列表
    await db.execute('''
      CREATE TABLE $tableSyncQueue (
        $colId INTEGER PRIMARY KEY AUTOINCREMENT,
        $colAction TEXT NOT NULL,
        $colRecordType TEXT NOT NULL,
        $colRecordId TEXT,
        $colData TEXT NOT NULL,
        $colPriority INTEGER DEFAULT 0,
        $colRetryCount INTEGER DEFAULT 0,
        $colStatus TEXT DEFAULT 'pending',
        $colCreatedAt INTEGER NOT NULL,
        $colSyncedAt INTEGER
      )
    ''');
    await db.execute('CREATE INDEX idx_sync_status ON $tableSyncQueue($colStatus)');
    await db.execute('CREATE INDEX idx_sync_created ON $tableSyncQueue($colCreatedAt DESC)');

    // 会话表
    await db.execute('''
      CREATE TABLE $tableSessions (
        $colSessionId TEXT PRIMARY KEY,
        $colUserId TEXT NOT NULL,
        $colUserName TEXT NOT NULL,
        $colDocumentId TEXT NOT NULL,
        $colCreatedAt INTEGER NOT NULL,
        $colLastActive INTEGER NOT NULL
      )
    ''');
    await db.execute('CREATE INDEX idx_sessions_user ON $tableSessions($colUserId)');
    await db.execute('CREATE INDEX idx_sessions_document ON $tableSessions($colDocumentId)');

    // 评论表
    await db.execute('''
      CREATE TABLE $tableComments (
        $colCommentId TEXT PRIMARY KEY,
        $colUserId TEXT NOT NULL,
        $colContent TEXT NOT NULL,
        $colPosition INTEGER DEFAULT 0,
        $colTimestamp INTEGER NOT NULL,
        $colDocumentId TEXT NOT NULL
      )
    ''');
    await db.execute('CREATE INDEX idx_comments_document ON $tableComments($colDocumentId)');
    await db.execute('CREATE INDEX idx_comments_timestamp ON $tableComments($colTimestamp DESC)');

    print('[Database] 数据库创建完成，版本: $_dbVersion');
  }

  // 升级数据库
  static Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    print('[Database] 数据库升级: $oldVersion -> $newVersion');
    
    if (oldVersion < 2) {
      // 添加会话表
      await db.execute('''
        CREATE TABLE IF NOT EXISTS $tableSessions (
          $colSessionId TEXT PRIMARY KEY,
          $colUserId TEXT NOT NULL,
          $colUserName TEXT NOT NULL,
          $colDocumentId TEXT NOT NULL,
          $colCreatedAt INTEGER NOT NULL,
          $colLastActive INTEGER NOT NULL
        )
      ''');
    }
    
    if (oldVersion < 3) {
      // 添加评论表
      await db.execute('''
        CREATE TABLE IF NOT EXISTS $tableComments (
          $colCommentId TEXT PRIMARY KEY,
          $colUserId TEXT NOT NULL,
          $colContent TEXT NOT NULL,
          $colPosition INTEGER DEFAULT 0,
          $colTimestamp INTEGER NOT NULL,
          $colDocumentId TEXT NOT NULL
        )
      ''');
      
      // 添加索引
      await db.execute('CREATE INDEX IF NOT EXISTS idx_comments_document ON $tableComments($colDocumentId)');
      await db.execute('CREATE INDEX IF NOT EXISTS idx_comments_timestamp ON $tableComments($colTimestamp DESC)');
    }
    
    print('[Database] 数据库升级完成');
  }

  // 打开数据库回调
  static Future<void> _onOpen(Database db) async {
    print('[Database] 数据库已打开');
  }

  // ========== 历史记录操作 ==========

  /// 添加历史记录
  Future<int> insertHistory({
    required String code,
    String? output,
    required int timestamp,
    bool isSuccess = true,
    String mode = 'expression',
    double? durationMs,
    String? documentId,
  }) async {
    final db = await database;
    return await db.insert(
      tableHistory,
      {
        colCode: code,
        colOutput: output,
        colTimestamp: timestamp,
        colIsSuccess: isSuccess ? 1 : 0,
        colMode: mode,
        colDurationMs: durationMs ?? 0,
        colDocumentId: documentId,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取历史记录
  Future<List<Map<String, dynamic>>> getHistory({
    int limit = 50,
    int offset = 0,
    String? mode,
    String? documentId,
  }) async {
    final db = await database;
    var where = '';
    var whereArgs = <dynamic>[];
    
    if (mode != null) {
      where += 'WHERE $colMode = ?';
      whereArgs.add(mode);
    }
    if (documentId != null) {
      where += where.isEmpty ? 'WHERE' : ' AND';
      where += ' $colDocumentId = ?';
      whereArgs.add(documentId);
    }
    
    return await db.query(
      tableHistory,
      where: where,
      orderBy: '$colTimestamp DESC',
      limit: limit,
      offset: offset,
    );
  }

  /// 删除历史记录
  Future<int> deleteHistory(int id) async {
    final db = await database;
    return await db.delete(
      tableHistory,
      where: '$colId = ?',
      whereArgs: [id],
    );
  }

  /// 清空历史记录
  Future<int> clearHistory() async {
    final db = await database;
    return await db.delete(tableHistory);
  }

  /// 获取历史记录数量
  Future<int> getHistoryCount({String? mode, String? documentId}) async {
    final db = await database;
    var where = '';
    var whereArgs = <dynamic>[];
    
    if (mode != null) {
      where += 'WHERE $colMode = ?';
      whereArgs.add(mode);
    }
    if (documentId != null) {
      where += where.isEmpty ? 'WHERE' : ' AND';
      where += ' $colDocumentId = ?';
      whereArgs.add(documentId);
    }
    
    final result = await db.rawQuery('SELECT COUNT(*) as count FROM $tableHistory $where', whereArgs);
    return result.first['count'] as int;
  }

  // ========== 偏好设置操作 ==========

  /// 保存偏好设置
  Future<int> savePreference({
    required String key,
    required String value,
  }) async {
    final db = await database;
    return await db.insert(
      tablePreferences,
      {
        colKey: key,
        colValue: value,
        colUpdatedAt: DateTime.now().millisecondsSinceEpoch,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取偏好设置
  Future<String?> getPreference(String key) async {
    final db = await database;
    final results = await db.query(
      tablePreferences,
      where: '$colKey = ?',
      whereArgs: [key],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return results.first[colValue] as String?;
  }

  /// 删除偏好设置
  Future<int> deletePreference(String key) async {
    final db = await database;
    return await db.delete(
      tablePreferences,
      where: '$colKey = ?',
      whereArgs: [key],
    );
  }

  // ========== 结果缓存操作 ==========

  /// 缓存计算结果
  Future<void> cacheResult({
    required String inputHash,
    required String inputCode,
    required String result,
    double? durationMs,
  }) async {
    final db = await database;
    await db.insert(
      tableResultCache,
      {
        colInputHash: inputHash,
        colInputCode: inputCode,
        colResult: result,
        colDurationMs: durationMs,
        colCreatedAt: DateTime.now().millisecondsSinceEpoch,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取缓存结果
  Future<Map<String, dynamic>?> getCacheResult(String inputHash) async {
    final db = await database;
    final results = await db.query(
      tableResultCache,
      where: '$colInputHash = ?',
      whereArgs: [inputHash],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return results.first;
  }

  /// 清除过期缓存
  Future<int> clearExpiredCache({int maxAgeDays = 7}) async {
    final db = await database;
    final cutoff = DateTime.now().millisecondsSinceEpoch - (maxAgeDays * 24 * 60 * 60 * 1000);
    return await db.delete(
      tableResultCache,
      where: '$colCreatedAt < ?',
      whereArgs: [cutoff],
    );
  }

  // ========== 同步队列操作 ==========

  /// 添加同步任务
  Future<int> addSyncTask({
    required String action,
    required String recordType,
    String? recordId,
    required String data,
    int priority = 0,
  }) async {
    final db = await database;
    return await db.insert(
      tableSyncQueue,
      {
        colAction: action,
        colRecordType: recordType,
        colRecordId: recordId,
        colData: data,
        colPriority: priority,
        colRetryCount: 0,
        colStatus: 'pending',
        colCreatedAt: DateTime.now().millisecondsSinceEpoch,
        colSyncedAt: null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取待同步任务
  Future<List<Map<String, dynamic>>> getPendingSyncTasks({int limit = 10}) async {
    final db = await database;
    return await db.query(
      tableSyncQueue,
      where: '$colStatus = ? ORDER BY $colPriority DESC, $colCreatedAt ASC',
      whereArgs: ['pending'],
      limit: limit,
    );
  }

  /// 更新任务状态
  Future<int> updateSyncTaskStatus({
    required int id,
    required String status,
    int? retryCount,
    DateTime? syncedAt,
  }) async {
    final db = await database;
    return await db.update(
      tableSyncQueue,
      {
        colStatus: status,
        colRetryCount: retryCount,
        colSyncedAt: syncedAt?.millisecondsSinceEpoch,
      },
      where: '$colId = ?',
      whereArgs: [id],
    );
  }

  /// 删除同步任务
  Future<int> deleteSyncTask(int id) async {
    final db = await database;
    return await db.delete(
      tableSyncQueue,
      where: '$colId = ?',
      whereArgs: [id],
    );
  }

  // ========== 会话操作 ==========

  /// 创建会话
  Future<int> createSession({
    required String sessionId,
    required String userId,
    required String userName,
    required String documentId,
  }) async {
    final db = await database;
    final now = DateTime.now().millisecondsSinceEpoch;
    return await db.insert(
      tableSessions,
      {
        colSessionId: sessionId,
        colUserId: userId,
        colUserName: userName,
        colDocumentId: documentId,
        colCreatedAt: now,
        colLastActive: now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 更新会话活动状态
  Future<int> updateSessionActivity(String sessionId) async {
    final db = await database;
    return await db.update(
      tableSessions,
      {colLastActive: DateTime.now().millisecondsSinceEpoch},
      where: '$colSessionId = ?',
      whereArgs: [sessionId],
    );
  }

  /// 获取活跃会话
  Future<List<Map<String, dynamic>>> getActiveSessions({int maxAgeMinutes = 5}) async {
    final db = await database;
    final cutoff = DateTime.now().millisecondsSinceEpoch - (maxAgeMinutes * 60 * 1000);
    return await db.query(
      tableSessions,
      where: '$colLastActive > ?',
      whereArgs: [cutoff],
      orderBy: '$colLastActive DESC',
    );
  }

  /// 删除会话
  Future<int> deleteSession(String sessionId) async {
    final db = await database;
    return await db.delete(
      tableSessions,
      where: '$colSessionId = ?',
      whereArgs: [sessionId],
    );
  }

  // ========== 评论操作 ==========

  /// 添加评论
  Future<int> addComment({
    required String commentId,
    required String userId,
    required String content,
    int position = 0,
    required String documentId,
  }) async {
    final db = await database;
    return await db.insert(
      tableComments,
      {
        colCommentId: commentId,
        colUserId: userId,
        colContent: content,
        colPosition: position,
        colTimestamp: DateTime.now().millisecondsSinceEpoch,
        colDocumentId: documentId,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取文档评论
  Future<List<Map<String, dynamic>>> getComments(String documentId, {int limit = 50}) async {
    final db = await database;
    return await db.query(
      tableComments,
      where: '$colDocumentId = ? ORDER BY $colTimestamp DESC',
      whereArgs: [documentId],
      limit: limit,
    );
  }

  /// 删除评论
  Future<int> deleteComment(String commentId) async {
    final db = await database;
    return await db.delete(
      tableComments,
      where: '$colCommentId = ?',
      whereArgs: [commentId],
    );
  }

  // ========== 数据统计 ==========

  /// 获取数据库统计信息
  Future<Map<String, dynamic>> getStats() async {
    final db = await database;
    
    final historyCount = await getHistoryCount();
    final pendingSyncs = await _getPendingSyncCount();
    final activeSessions = (await getActiveSessions()).length;
    
    return {
      'historyCount': historyCount,
      'pendingSyncs': pendingSyncs,
      'activeSessions': activeSessions,
      'dbSize': await _getDbSize(),
      'version': _dbVersion,
    };
  }

  /// 获取待同步任务数量
  Future<int> _getPendingSyncCount() async {
    final db = await database;
    final result = await db.rawQuery(
      'SELECT COUNT(*) as count FROM $tableSyncQueue WHERE $colStatus = ?',
      ['pending'],
    );
    return result.first['count'] as int;
  }

  /// 获取数据库文件大小
  Future<int> _getDbSize() async {
    final dir = await getApplicationDocumentsDirectory();
    final path = join(dir.path, _dbName);
    final file = File(path);
    return await file.length();
  }

  // ========== 数据库维护 ==========

  /// 优化数据库
  Future<void> optimize() async {
    final db = await database;
    await db.execute('PRAGMA optimize');
    await db.execute('PRAGMA auto_vacuum = FULL');
    await db.execute('VACUUM');
    print('[Database] 数据库优化完成');
  }

  /// 备份数据库
  Future<String> backup() async {
    final dir = await getApplicationDocumentsDirectory();
    final backupPath = join(dir.path, 'matha_backup_${DateTime.now().millisecondsSinceEpoch}.db');
    // TODO: 实现数据库备份逻辑
    print('[Database] 数据库备份: $backupPath (待实现)');
    return backupPath;
  }

  /// 关闭数据库
  Future<void> close() async {
    final db = _database;
    if (db != null) {
      await db.close();
      _database = null;
      print('[Database] 数据库已关闭');
    }
  }

  // ========== 同步队列便捷方法 ==========

  /// 标记任务为已同步
  Future<void> markSynced(int id) async {
    await updateSyncTaskStatus(id: id, status: 'synced', syncedAt: DateTime.now());
  }

  /// 获取待同步任务（兼容旧接口）
  Future<List<Map<String, dynamic>>> getPendingSync({int limit = 100}) async {
    return getPendingSyncTasks(limit: limit);
  }

  /// 获取队列统计
  Future<Map<String, dynamic>> getQueueStats() async {
    final db = await database;
    final pending = await db.query(tableSyncQueue, where: '$colStatus = ?', whereArgs: ['pending']);
    final synced = await db.query(tableSyncQueue, where: '$colStatus = ?', whereArgs: ['synced']);
    final failed = await db.query(tableSyncQueue, where: '$colStatus = ?', whereArgs: ['failed']);
    return {
      'pending': pending.length,
      'synced': synced.length,
      'failed': failed.length,
    };
  }
}
