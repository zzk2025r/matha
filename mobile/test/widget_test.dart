// Matha Mobile - 应用冒烟测试
// 验证主应用可以正常启动

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/main.dart';

void main() {
  testWidgets('MathaMobileApp 启动测试', (WidgetTester tester) async {
    await tester.pumpWidget(const MathaMobileApp());
    await tester.pump();

    // 验证主应用标题存在
    expect(find.text('Matha'), findsOneWidget);
  });

  testWidgets('代码编辑器可交互', (WidgetTester tester) async {
    await tester.pumpWidget(const MathaMobileApp());
    await tester.pump();

    // 验证代码输入区域存在
    expect(find.byType(TextField), findsWidgets);
  });
}
