import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../database/math_database.dart';
import '../pyodide/math_executor.dart';
import '../sync/offline_sync_manager.dart';
import '../widgets/result_panel.dart';
import '../widgets/history_panel.dart';

class MathProvider extends ChangeNotifier {
  String _mode = 'expr';
  String _currentCode = '';
  List<ResultItem> _results = [];
  List<HistoryItem> _history = [];
  bool _isDarkMode = false;
  bool _showLineNumbers = true;
  bool _autoComplete = true;
  bool _isOffline = false;
  bool _isSyncing = false;
  String _syncStatus = '未同步';

  // 本地存储
  String? _dbPath;
  SharedPreferences? _prefs;

  // Getters
  String get mode => _mode;
  String get currentCode => _currentCode;
  List<ResultItem> get results => _results;
  List<HistoryItem> get history => _history;
  bool get isDarkMode => _isDarkMode;
  bool get showLineNumbers => _showLineNumbers;
  bool get autoComplete => _autoComplete;
  bool get isOffline => _isOffline;
  bool get isSyncing => _isSyncing;
  String get syncStatus => _syncStatus;
  String? get dbPath => _dbPath;

  // 初始化
  Future<void> init() async {
    await _loadPreferences();
    await _initDatabase();
    notifyListeners();
  }

  // 初始化数据库
  Future<void> _initDatabase() async {
    try {
      final dir = await getApplicationDocumentsDirectory();
      _dbPath = '${dir.path}/matha.db';
      // 初始化 SQLite 数据库（建表与索引）
      await MathDatabase.database;
      debugPrint('数据库已初始化: $_dbPath');
    } catch (e) {
      debugPrint('初始化数据库失败: $e');
    }
  }

  // 加载偏好设置
  Future<void> _loadPreferences() async {
    try {
      _prefs = await SharedPreferences.getInstance();
      _isDarkMode = _prefs?.getBool('dark_mode') ?? false;
      _showLineNumbers = _prefs?.getBool('show_line_numbers') ?? true;
      _autoComplete = _prefs?.getBool('auto_complete') ?? true;
      _isOffline = _prefs?.getBool('offline_mode') ?? false;
    } catch (e) {
      debugPrint('加载偏好设置失败: $e');
    }
  }

  // 保存偏好设置
  Future<void> _savePreferences() async {
    try {
      if (_prefs == null) {
        _prefs = await SharedPreferences.getInstance();
      }
      await _prefs!.setBool('dark_mode', _isDarkMode);
      await _prefs!.setBool('show_line_numbers', _showLineNumbers);
      await _prefs!.setBool('auto_complete', _autoComplete);
      await _prefs!.setBool('offline_mode', _isOffline);
    } catch (e) {
      debugPrint('保存偏好设置失败: $e');
    }
  }

  // 设置模式
  void setMode(String mode) {
    _mode = mode;
    notifyListeners();
  }

  // 设置代码
  void setCode(String code) {
    _currentCode = code;
    notifyListeners();
  }

  // 执行代码
  Future<void> executeCode(String code) async {
    final startTime = DateTime.now().millisecondsSinceEpoch;

    try {
      // 集成 Pyodide 执行 Python 代码（Web 端）
      final execResult = await _execute(code);
      final output = execResult.output;
      final isSuccess = execResult.isSuccess;
      final duration = DateTime.now().millisecondsSinceEpoch - startTime;

      final result = ResultItem(
        code: code,
        output: output,
        isSuccess: isSuccess,
        duration: duration / 1000,
      );

      final historyItem = HistoryItem(
        code: code,
        output: output,
        timestamp: DateTime.now(),
        isSuccess: isSuccess,
      );

      _results.add(result);
      _history.add(historyItem);

      // 保存到离线存储
      await _saveToOfflineStorage(historyItem);

      notifyListeners();
    } catch (e) {
      final result = ResultItem(
        code: code,
        output: '错误: $e',
        isSuccess: false,
      );

      final historyItem = HistoryItem(
        code: code,
        output: '错误: $e',
        timestamp: DateTime.now(),
        isSuccess: false,
      );

      _results.add(result);
      _history.add(historyItem);
      notifyListeners();
    }
  }

  // 执行代码（离线时使用本地模拟，联网时调用平台执行器）
  Future<MathExecuteResult> _execute(String code) {
    if (_isOffline) {
      return Future.value(MathExecuteResult(output: simulateOutput(code), isSuccess: true));
    }
    return executeMathCode(code);
  }

  // 保存到离线存储
  Future<void> _saveToOfflineStorage(HistoryItem item) async {
    try {
      // 集成 SQLite 存储
      await MathDatabase().saveHistory(
        code: item.code,
        output: item.output,
        timestamp: item.timestamp.millisecondsSinceEpoch,
        isSuccess: item.isSuccess,
        mode: _mode,
      );
      debugPrint('历史记录已保存到 SQLite: ${item.code}');
    } catch (e) {
      debugPrint('保存历史记录失败: $e');
    }
  }

  // 清空结果
  void clearResults() {
    _results.clear();
    notifyListeners();
  }

  // 清空代码
  void clearCode() {
    _currentCode = '';
    notifyListeners();
  }

  // 清空历史
  void clearHistory() {
    _history.clear();
    notifyListeners();
  }

  // 切换深色模式
  void toggleDarkMode() {
    _isDarkMode = !_isDarkMode;
    _savePreferences();
    notifyListeners();
  }

  // 设置显示行号
  void setShowLineNumbers(bool show) {
    _showLineNumbers = show;
    _savePreferences();
    notifyListeners();
  }

  // 设置自动补全
  void setAutoComplete(bool enable) {
    _autoComplete = enable;
    _savePreferences();
    notifyListeners();
  }

  // 切换离线模式
  void toggleOfflineMode() {
    _isOffline = !_isOffline;
    _savePreferences();
    _updateSyncStatus();
    notifyListeners();
  }

  // 更新同步状态
  void _updateSyncStatus() {
    if (_isOffline) {
      _syncStatus = '离线模式';
    } else {
      _syncStatus = '已连接';
    }
  }

  // 插入代码片段
  void insertSnippet(String type) {
    switch (type) {
      case 'matrix':
        _currentCode = 'A = zeros(3, 3)\nB = eye(3)\nC = matrix_multiply(A, B)';
        break;
      case 'statistics':
        _currentCode = 'data = [1, 2, 3, 4, 5]\nmean(data)';
        break;
      case 'calculus':
        _currentCode = 'symbolic_derivative(x**2 + 2*x + 1)';
        break;
      case 'probability':
        _currentCode = 'dist = NormalDistribution(mu=0, sigma=1)\ndist.pdf(1.0)';
        break;
      case 'graph':
        _currentCode = 'g = Graph()\ng.add_edge(1, 2)\ng.dijkstra(1)';
        break;
    }
    notifyListeners();
  }

  // 请求同步（联网时）
  Future<void> requestSync() async {
    if (_isOffline) return;

    _isSyncing = true;
    _syncStatus = '同步中...';
    notifyListeners();

    try {
      // 实现与云端的数据同步
      final manager = OfflineSyncManager();
      await manager.performSync();
      _syncStatus = manager.syncStatus;
    } catch (e) {
      _syncStatus = '同步失败';
    } finally {
      _isSyncing = false;
      notifyListeners();
    }
  }

  // 清除本地缓存
  Future<void> clearLocalCache() async {
    try {
      // 清除 SQLite 数据库缓存
      final db = MathDatabase();
      await db.clearHistory();
      await db.cleanExpiredHistory(maxAgeDays: 0);
      await db.cleanExpiredCache(maxAgeDays: 0);
      _history.clear();
      _results.clear();
      notifyListeners();
      debugPrint('本地缓存已清除');
    } catch (e) {
      debugPrint('清除缓存失败: $e');
    }
  }

  @override
  void dispose() {
    super.dispose();
  }
}
