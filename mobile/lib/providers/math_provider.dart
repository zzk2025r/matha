import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import 'package:shared_preferences/shared_preferences.dart';
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
      // TODO: 初始化 SQLite 数据库
      debugPrint('数据库路径: $_dbPath');
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
      // TODO: 集成 Pyodide 执行 Python 代码
      // 目前先模拟执行
      final output = await _simulateExecution(code);
      final duration = DateTime.now().millisecondsSinceEpoch - startTime;

      final result = ResultItem(
        code: code,
        output: output,
        isSuccess: true,
        duration: duration / 1000,
      );

      final historyItem = HistoryItem(
        code: code,
        output: output,
        timestamp: DateTime.now(),
        isSuccess: true,
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

  // 保存到离线存储
  Future<void> _saveToOfflineStorage(HistoryItem item) async {
    try {
      // TODO: 集成 SQLite 存储
      debugPrint('保存历史记录: ${item.code}');
    } catch (e) {
      debugPrint('保存历史记录失败: $e');
    }
  }

  // 从离线存储加载历史记录
  Future<void> _loadFromOfflineStorage() async {
    try {
      // TODO: 从 SQLite 加载
      debugPrint('从离线存储加载历史记录');
    } catch (e) {
      debugPrint('加载历史记录失败: $e');
    }
  }

  // 模拟执行（实际应调用 Pyodide）
  Future<String> _simulateExecution(String code) async {
    // 模拟延迟
    await Future.delayed(const Duration(milliseconds: 100));

    // 简单的模拟逻辑
    if (code.contains('matrix') || code.contains('multiply')) {
      return 'Matrix([[5, 8], [11, 14]])';
    }
    if (code.contains('mean') || code.contains('平均')) {
      return '42.5';
    }
    if (code.contains('sum') || code.contains('求和')) {
      return '100';
    }
    return '执行完成';
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
      // TODO: 实现与云端的数据同步
      await Future.delayed(const Duration(seconds: 1));
      _syncStatus = '同步完成';
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
      // TODO: 清除本地缓存
      _history.clear();
      _results.clear();
      notifyListeners();
    } catch (e) {
      debugPrint('清除缓存失败: $e');
    }
  }

  @override
  void dispose() {
    super.dispose();
  }
}
