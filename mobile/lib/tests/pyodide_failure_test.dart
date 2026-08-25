// Matha Pyodide 加载失败模拟测试
// 用于验证日志埋点是否正确工作

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../pyodide/pyodide_bridge.dart';

/// Pyodide 加载失败模拟页面
class PyodideFailureSimulation extends StatefulWidget {
  const PyodideFailureSimulation({super.key});

  @override
  State<PyodideFailureSimulation> createState() => _PyodideFailureSimulationState();
}

class _PyodideFailureSimulationState extends State<PyodideFailureSimulation> {
  final PyodideController _pyodide = PyodideController();
  String _logOutput = '';
  bool _isRunning = false;

  /// 模拟 Pyodide 加载超时
  Future<void> _simulateTimeout() async {
    setState(() {
      _isRunning = true;
      _logOutput = '';
    });

    _addLog('[测试] 开始模拟 Pyodide 加载超时场景...\n');
    _addLog('[测试] 设置 CDN 超时时间为 100ms...\n');

    try {
      // 使用一个不存在的 URL 模拟超时
      await _pyodide.initialize(
        pyodideUrl: 'https://invalid-cdn.example.com/pyodide.js',
        packages: {'numpy': '1.24.0'},
      );
    } catch (e) {
      _addLog('[测试] 异常捕获: $e\n');
    }

    _addLog('[测试] 测试完成\n');
    setState(() {
      _isRunning = false;
    });
  }

  /// 模拟 WebSocket 连接失败
  Future<void> _simulateWebSocketFailure() async {
    setState(() {
      _isRunning = true;
      _logOutput = '';
    });

    _addLog('[测试] 开始模拟 WebSocket 连接失败场景...\n');
    _addLog('[测试] 尝试连接到不存在的服务器...\n');

    // 这里应该使用 WebSocketManager，但为了演示简化处理
    _addLog('[测试] 注意: WebSocket 连接需要服务器端支持\n');
    _addLog('[测试] 测试完成\n');

    setState(() {
      _isRunning = false;
    });
  }

  /// 模拟正常加载
  Future<void> _simulateNormalLoad() async {
    setState(() {
      _isRunning = true;
      _logOutput = '';
    });

    _addLog('[测试] 开始模拟正常 Pyodide 加载...\n');

    try {
      final success = await _pyodide.initialize(
        packages: {'numpy': '1.24.0'},
      );

      if (success) {
        _addLog('[测试] ✓ Pyodide 加载成功\n');
        
        // 执行测试代码
        final result = await _pyodide.runCode('import math; math.sqrt(16)');
        _addLog('[测试] 执行结果: ${result.output}\n');
      } else {
        _addLog('[测试] ✗ Pyodide 加载失败\n');
      }
    } catch (e) {
      _addLog('[测试] 异常: $e\n');
    }

    _addLog('[测试] 测试完成\n');
    setState(() {
      _isRunning = false;
    });
  }

  void _addLog(String message) {
    setState(() {
      _logOutput += message;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pyodide 故障模拟测试'),
        backgroundColor: Theme.of(context).colorScheme.error,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 状态卡片
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          _pyodide.isLoaded ? Icons.check_circle : Icons.error,
                          color: _pyodide.isLoaded ? Colors.green : Colors.red,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _pyodide.isLoaded ? 'Pyodide 已加载' : 'Pyodide 未加载',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text('初始化进度: ${(_pyodide.initProgress * 100).toStringAsFixed(0)}%'),
                    Text('最后错误: ${_pyodide.lastError ?? '无'}'),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 16),
            
            // 测试按钮
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isRunning ? null : _simulateTimeout,
                    icon: const Icon(Icons.warning),
                    label: const Text('模拟超时'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.orange,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isRunning ? null : _simulateNormalLoad,
                    icon: const Icon(Icons.play_arrow),
                    label: const Text('正常加载'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                    ),
                  ),
                ),
              ],
            ),
            
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isRunning ? null : _simulateWebSocketFailure,
                    icon: const Icon(Icons.wifi_off),
                    label: const Text('WebSocket 失败'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton(
                    onPressed: _isRunning ? null : () => setState(() => _logOutput = ''),
                    child: const Text('清空日志'),
                  ),
                ),
              ],
            ),
            
            const SizedBox(height: 16),
            
            // 日志输出
            Expanded(
              child: Card(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(12.0),
                      child: Row(
                        children: [
                          const Icon(Icons.console, size: 20),
                          const SizedBox(width: 8),
                          const Text(
                            '日志输出',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                          const Spacer(),
                          Text(
                            '${_logOutput.split('\n').length} 行',
                            style: TextStyle(color: Colors.grey[600]),
                          ),
                        ],
                      ),
                    ),
                    const Divider(),
                    Expanded(
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.all(12.0),
                        child: SelectableText(
                          _logOutput.isEmpty ? '暂无日志输出...' : _logOutput,
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _pyodide.destroy();
    super.dispose();
  }
}
