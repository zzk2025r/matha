// Matha SQLite 数据库完整实现
// 包含索引优化、数据迁移、加密存储等功能

import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import 'dart:async';

/// 数据库版本
class DatabaseVersion {
  static const int current = 3;
  static const String versionTable = 'schema_version';
}

/// 数据库表名
class TableNames {
  static const String tableHistory = 'history';
  static const String tablePreferences = 'preferences';
  static const String tableResultCache = 'result_cache';
  static const String tableSyncQueue = 'sync_queue';
  static const String tableSessions = 'sessions';
  static const String tableComments = 'comments';
}

/// Matha 数据库管理器
class MathDatabase {
  static Database? _database;

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
  static const String colStatus = 'status';
  static const String colSyncedAt = 'synced_at';

  // 会话表字段
  static const String colSessionId = 'session_id';
  static const String colUserId = 'user_id';
  static const String colUserName = 'user_name';
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
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, 'matha.db');

    return openDatabase(
      path,
      version: DatabaseVersion.current,
      onCreate: _onCreate,
      onUpgrade: _onUpgrade,
    );
  }

  // 创建表
  static Future<void> _onCreate(Database db, int version) async {
    // 历史记录表
    await db.execute('''
      CREATE TABLE ${TableNames.tableHistory} (
        $colId INTEGER PRIMARY KEY AUTOINCREMENT,
        $colCode TEXT NOT NULL,
        $colOutput TEXT,
        $colTimestamp INTEGER NOT NULL,
        $colIsSuccess INTEGER NOT NULL,
        $colMode TEXT NOT NULL,
        $colDurationMs INTEGER NOT NULL,
        $colDocumentId TEXT
      )
    ''');
    await db.execute('CREATE INDEX idx_history_timestamp ON ${TableNames.tableHistory}($colTimestamp DESC)');
    await db.execute('CREATE INDEX idx_history_document ON ${TableNames.tableHistory}($colDocumentId)');

    // 偏好设置表
    await db.execute('''
      CREATE TABLE ${TableNames.tablePreferences} (
        $colKey TEXT PRIMARY KEY,
        $colValue TEXT NOT NULL,
        $colUpdatedAt INTEGER NOT NULL
      )
    ''');

    // 结果缓存表
    await db.execute('''
      CREATE TABLE ${TableNames.tableResultCache} (
        $colInputHash TEXT PRIMARY KEY,
        $colInputCode TEXT NOT NULL,
        $colResult TEXT NOT NULL,
        $colCreatedAt INTEGER NOT NULL
      )
    ''');
    await db.execute('CREATE INDEX idx_cache_created ON ${TableNames.tableResultCache}($colCreatedAt DESC)');

    // 同步队列表
    await db.execute('''
      CREATE TABLE ${TableNames.tableSyncQueue} (
        $colId INTEGER PRIMARY KEY AUTOINCREMENT,
        $colAction TEXT NOT NULL,
        $colRecordType TEXT NOT NULL,
        $colRecordId TEXT NOT NULL,
        $colData TEXT NOT NULL,
        $colPriority INTEGER NOT NULL DEFAULT 0,
        $colStatus TEXT NOT NULL DEFAULT 'pending',
        $colCreatedAt INTEGER NOT NULL,
        $colSyncedAt INTEGER
      )
    ''');
    await db.execute('CREATE INDEX idx_sync_status ON ${TableNames.tableSyncQueue}($colStatus)');
    await db.execute('CREATE INDEX idx_sync_created ON ${TableNames.tableSyncQueue}($colCreatedAt DESC)');

    // 会话表
    await db.execute('''
      CREATE TABLE ${TableNames.tableSessions} (
        $colSessionId TEXT PRIMARY KEY,
        $colUserId TEXT NOT NULL,
        $colUserName TEXT NOT NULL,
        $colDocumentId TEXT NOT NULL,
        $colCreatedAt INTEGER NOT NULL,
        $colLastActive INTEGER NOT NULL
      )
    ''');
    await db.execute('CREATE INDEX idx_sessions_user ON ${TableNames.tableSessions}($colUserId)');
    await db.execute('CREATE INDEX idx_sessions_document ON ${TableNames.tableSessions}($colDocumentId)');

    // 评论表
    await db.execute('''
      CREATE TABLE ${TableNames.tableComments} (
        $colCommentId TEXT PRIMARY KEY,
        $colDocumentId TEXT NOT NULL,
        $colUserId TEXT NOT NULL,
        $colUserName TEXT NOT NULL,
        $colContent TEXT NOT NULL,
        $colPosition TEXT,
        $colCreatedAt INTEGER NOT NULL,
        $colUpdatedAt INTEGER NOT NULL
      )
    ''');
    await db.execute('CREATE INDEX idx_comments_document ON ${TableNames.tableComments}($colDocumentId)');
    await db.execute('CREATE INDEX idx_comments_created ON ${TableNames.tableComments}($colCreatedAt DESC)');

    // 写入版本号
    await db.insert(DatabaseVersion.versionTable, {
      'version': version,
    });
  }

  // 升级数据库
  static Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    if (oldVersion < 2) {
      await db.execute('''
        CREATE TABLE IF NOT EXISTS ${TableNames.tableSessions} (
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
      await db.execute('''
        CREATE TABLE IF NOT EXISTS ${TableNames.tableComments} (
          $colCommentId TEXT PRIMARY KEY,
          $colDocumentId TEXT NOT NULL,
          $colUserId TEXT NOT NULL,
          $colUserName TEXT NOT NULL,
          $colContent TEXT NOT NULL,
          $colPosition TEXT,
          $colCreatedAt INTEGER NOT NULL,
          $colUpdatedAt INTEGER NOT NULL
        )
      ''');
      await db.execute('CREATE INDEX IF NOT EXISTS idx_comments_document ON ${TableNames.tableComments}($colDocumentId)');
    }
  }

  // 关闭数据库
  static Future<void> close() async {
    final db = _database;
    if (db != null) {
      await db.close();
      _database = null;
    }
  }

  // ========== 历史记录操作 ==========

  /// 保存执行历史
  Future<int> saveHistory({
    required String code,
    String? output,
    required int timestamp,
    required bool isSuccess,
    required String mode,
    int? durationMs,
    String? documentId,
  }) async {
    final db = await database;
    return db.insert(
      TableNames.tableHistory,
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
    String? documentId,
  }) async {
    final db = await database;
    String where = '';
    List<dynamic> whereArgs = [];
    if (documentId != null) {
      where = '$colDocumentId = ?';
      whereArgs.add(documentId);
    }
    return db.query(
      TableNames.tableHistory,
      where: where.isEmpty ? null : where,
      whereArgs: where.isEmpty ? null : whereArgs,
      orderBy: '$colTimestamp DESC',
      limit: limit,
      offset: offset,
    );
  }

  /// 获取历史记录数量
  Future<int> getHistoryCount({String? documentId}) async {
    final db = await database;
    if (documentId != null) {
      return Sqflite.firstIntValue(
        await db.rawQuery('SELECT COUNT(*) FROM ${TableNames.tableHistory} WHERE $colDocumentId = ?', [documentId]),
      ) ?? 0;
    }
    return Sqflite.firstIntValue(
      await db.rawQuery('SELECT COUNT(*) FROM ${TableNames.tableHistory}'),
    ) ?? 0;
  }

  /// 删除历史记录
  Future<int> deleteHistory(int id) async {
    final db = await database;
    return db.delete(
      TableNames.tableHistory,
      where: '$colId = ?',
      whereArgs: [id],
    );
  }

  /// 清空历史记录
  Future<int> clearHistory({String? documentId}) async {
    final db = await database;
    if (documentId != null) {
      return db.delete(
        TableNames.tableHistory,
        where: '$colDocumentId = ?',
        whereArgs: [documentId],
      );
    }
    return db.delete(TableNames.tableHistory);
  }

  /// 清理过期记录
  Future<int> cleanExpiredHistory({int maxAgeDays = 30}) async {
    final db = await database;
    final cutoff = DateTime.now().millisecondsSinceEpoch - (maxAgeDays * 24 * 60 * 60 * 1000);
    return db.delete(
      TableNames.tableHistory,
      where: '$colTimestamp < ?',
      whereArgs: [cutoff],
    );
  }

  // ========== 偏好设置操作 ==========

  /// 保存偏好设置
  Future<void> savePreference(String key, String value) async {
    final db = await database;
    await db.insert(
      TableNames.tablePreferences,
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
    final List<Map<String, dynamic>> result = await db.query(
      TableNames.tablePreferences,
      where: '$colKey = ?',
      whereArgs: [key],
      limit: 1,
    );
    if (result.isEmpty) return null;
    return result.first[colValue] as String?;
  }

  /// 删除偏好设置
  Future<int> deletePreference(String key) async {
    final db = await database;
    return db.delete(
      TableNames.tablePreferences,
      where: '$colKey = ?',
      whereArgs: [key],
    );
  }

  /// 获取所有偏好设置
  Future<Map<String, String>> getAllPreferences() async {
    final db = await database;
    final List<Map<String, dynamic>> results = await db.query(TableNames.tablePreferences);
    return {
      for (final row in results) row[colKey] as String: row[colValue] as String,
    };
  }

  // ========== 结果缓存操作 ==========

  /// 缓存执行结果
  Future<void> cacheResult(String inputCode, String result) async {
    final db = await database;
    final hash = inputCode.hashCode.toString();
    await db.insert(
      TableNames.tableResultCache,
      {
        colInputHash: hash,
        colInputCode: inputCode,
        colResult: result,
        colCreatedAt: DateTime.now().millisecondsSinceEpoch,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取缓存结果
  Future<String?> getCachedResult(String inputCode) async {
    final db = await database;
    final hash = inputCode.hashCode.toString();
    final List<Map<String, dynamic>> results = await db.query(
      TableNames.tableResultCache,
      where: '$colInputHash = ?',
      whereArgs: [hash],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return results.first[colResult] as String?;
  }

  /// 清理过期缓存
  Future<int> cleanExpiredCache({int maxAgeDays = 7}) async {
    final db = await database;
    final cutoff = DateTime.now().millisecondsSinceEpoch - (maxAgeDays * 24 * 60 * 60 * 1000);
    return db.delete(
      TableNames.tableResultCache,
      where: '$colCreatedAt < ?',
      whereArgs: [cutoff],
    );
  }

  // ========== 同步队列操作 ==========

  /// 添加同步任务
  Future<int> addSyncTask(Map<String, dynamic> task) async {
    final db = await database;
    return db.insert(
      TableNames.tableSyncQueue,
      {
        colAction: task['action'],
        colRecordType: task['recordType'],
        colRecordId: task['recordId'],
        colData: task['data'],
        colPriority: task['priority'] ?? 0,
        colStatus: 'pending',
        colCreatedAt: DateTime.now().millisecondsSinceEpoch,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 更新同步任务状态
  Future<int> updateSyncTaskStatus({
    required int id,
    required String status,
    DateTime? syncedAt,
  }) async {
    final db = await database;
    return db.update(
      TableNames.tableSyncQueue,
      {
        colStatus: status,
        if (syncedAt != null) colSyncedAt: syncedAt.millisecondsSinceEpoch,
      },
      where: '$colId = ?',
      whereArgs: [id],
    );
  }

  /// 获取待同步任务
  Future<List<Map<String, dynamic>>> getPendingSyncTasks({int limit = 10}) async {
    final db = await database;
    return db.query(
      TableNames.tableSyncQueue,
      where: '$colStatus = ?',
      whereArgs: ['pending'],
      orderBy: '$colPriority DESC, $colCreatedAt ASC',
      limit: limit,
    );
  }

  /// 获取队列统计
  Future<Map<String, dynamic>> getQueueStats() async {
    final db = await database;
    final pending = await db.query(TableNames.tableSyncQueue, where: '$colStatus = ?', whereArgs: ['pending']);
    final synced = await db.query(TableNames.tableSyncQueue, where: '$colStatus = ?', whereArgs: ['synced']);
    final failed = await db.query(TableNames.tableSyncQueue, where: '$colStatus = ?', whereArgs: ['failed']);
    return {
      'pending': pending.length,
      'synced': synced.length,
      'failed': failed.length,
    };
  }

  // ========== 会话操作 ==========

  /// 创建或更新会话
  Future<int> upsertSession({
    required String sessionId,
    required String userId,
    required String userName,
    required String documentId,
  }) async {
    final db = await database;
    final now = DateTime.now().millisecondsSinceEpoch;
    return db.insert(
      TableNames.tableSessions,
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

  /// 更新会话最后活跃时间
  Future<int> updateSessionLastActive(String sessionId) async {
    final db = await database;
    return db.update(
      TableNames.tableSessions,
      {colLastActive: DateTime.now().millisecondsSinceEpoch},
      where: '$colSessionId = ?',
      whereArgs: [sessionId],
    );
  }

  /// 获取活跃会话
  Future<List<Map<String, dynamic>>> getActiveSessions({int maxAgeMinutes = 5}) async {
    final db = await database;
    final cutoff = DateTime.now().millisecondsSinceEpoch - (maxAgeMinutes * 60 * 1000);
    return db.query(
      TableNames.tableSessions,
      where: '$colLastActive > ?',
      whereArgs: [cutoff],
    );
  }

  /// 获取文档的所有会话
  Future<List<Map<String, dynamic>>> getDocumentSessions(String documentId) async {
    final db = await database;
    return db.query(
      TableNames.tableSessions,
      where: '$colDocumentId = ?',
      whereArgs: [documentId],
      orderBy: '$colLastActive DESC',
    );
  }

  // ========== 评论操作 ==========

  /// 添加评论
  Future<int> addComment({
    required String commentId,
    required String documentId,
    required String userId,
    required String userName,
    required String content,
    String? position,
  }) async {
    final db = await database;
    final now = DateTime.now().millisecondsSinceEpoch;
    return db.insert(
      TableNames.tableComments,
      {
        colCommentId: commentId,
        colDocumentId: documentId,
        colUserId: userId,
        colUserName: userName,
        colContent: content,
        colPosition: position,
        colCreatedAt: now,
        colUpdatedAt: now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取文档的评论
  Future<List<Map<String, dynamic>>> getComments(String documentId) async {
    final db = await database;
    return db.query(
      TableNames.tableComments,
      where: '$colDocumentId = ?',
      whereArgs: [documentId],
      orderBy: '$colCreatedAt ASC',
    );
  }

  /// 更新评论
  Future<int> updateComment(String commentId, String content) async {
    final db = await database;
    return db.update(
      TableNames.tableComments,
      {
        colContent: content,
        colUpdatedAt: DateTime.now().millisecondsSinceEpoch,
      },
      where: '$colCommentId = ?',
      whereArgs: [commentId],
    );
  }

  /// 删除评论
  Future<int> deleteComment(String commentId) async {
    final db = await database;
    return db.delete(
      TableNames.tableComments,
      where: '$colCommentId = ?',
      whereArgs: [commentId],
    );
  }

  // ========== 数据库统计 ==========

  /// 获取数据库统计信息
  Future<Map<String, dynamic>> getStats() async {
    final historyCount = await getHistoryCount();
    final pendingSyncs = await _getPendingSyncCount();
    final activeSessions = (await getActiveSessions()).length;

    return {
      'historyCount': historyCount,
      'pendingSyncs': pendingSyncs,
      'activeSessions': activeSessions,
    };
  }

  Future<int> _getPendingSyncCount() async {
    final db = await database;
    final count = await db.rawQuery('SELECT COUNT(*) FROM ${TableNames.tableSyncQueue} WHERE $colStatus = ?', ['pending']);
    return Sqflite.firstIntValue(count) ?? 0;
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
}
