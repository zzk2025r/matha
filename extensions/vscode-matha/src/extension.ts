# -*- coding: utf-8 -*-
"""Matha VS Code 扩展 — 主入口

提供：
1. 语法高亮（通过 tmGrammar 配置）
2. 智能补全（CompletionItemProvider）
3. 意图解析（Language Server Protocol）
4. 命令面板集成
5. 计算执行（调用 Matha 后端）
"""
import vscode from 'vscode';
import { MathaLanguageClient } from './language-client';
import { MathaCompletionProvider } from './completion-provider';
import { MathaHoverProvider } from './hover-provider';
import { MathaSignatureHelpProvider } from './signature-help';
import { execFile } from 'child_process';
import * as path from 'path';
import * as os from 'os';

let client: MathaLanguageClient;

/**
 * 查找 Matha Python 解释器路径
 */
function findMathaPython(): string {
    const pythonPaths = [
        'python',
        'python3',
        'py',
        'python.exe',
    ];
    for (const p of pythonPaths) {
        try {
            const result = execFile.sync(p, ['--version'], { timeout: 2000 });
            if (result.stdout) return p;
        } catch { /* try next */ }
    }
    return 'python';
}

/**
 * 调用 Matha 后端执行计算
 */
async function callMathaCompute(text: string): Promise<{ success: boolean; value?: any; error?: string }> {
    try {
        const python = findMathaPython();
        // 使用 subprocess 调用 src/repl.py 的 eval 命令
        const script = `
import sys
sys.path.insert(0, r"${path.join(__dirname, '..', '..', '..')}")
from src.repl import _cmd_eval
from src.interp import interpret
result = None
try:
    outputs, trace = interpret(${JSON.stringify(text)})
    result = outputs[-1] if outputs else None
except Exception as e:
    result = str(e)
print("RESULT:" + str(result))
`;
        return new Promise((resolve) => {
            execFile(python, ['-c', script], { timeout: 10000 }, (error, stdout, stderr) => {
                if (error) {
                    resolve({ success: false, error: stderr || error.message });
                    return;
                }
                const output = stdout.trim();
                const match = output.match(/RESULT:(.*)$/);
                if (match) {
                    const value = match[1];
                    resolve({ success: true, value });
                } else {
                    resolve({ success: true, value: output || '计算完成' });
                }
            });
        });
    } catch (err) {
        return { success: false, error: String(err) };
    }
}

export function activate(context: vscode.ExtensionContext) {
    console.log('Matha 扩展已激活');

    // 注册补全提供者
    const completionProvider = vscode.languages.registerCompletionItemProvider(
        'matha',
        new MathaCompletionProvider(),
        ' ', '(', '.', 'π', 'e'
    );

    // 注册悬浮提示
    const hoverProvider = vscode.languages.registerHoverProvider(
        'matha',
        new MathaHoverProvider()
    );

    // 注册签名帮助
    const signatureHelpProvider = vscode.languages.registerSignatureHelpProvider(
        'matha',
        new MathaSignatureHelpProvider(),
        '(', ','
    );

    // 注册命令
    const parseCommand = vscode.commands.registerCommand('matha.parse', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;

        const selection = editor.selection;
        const text = selection.isEmpty
            ? editor.document.getText()
            : editor.document.getText(selection);

        vscode.window.showInformationMessage(`解析: ${text.substring(0, 50)}...`);
    });

    const computeCommand = vscode.commands.registerCommand('matha.compute', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;

        const text = editor.document.getText(editor.selection);
        const result = await callMathaCompute(text);

        if (result.success) {
            vscode.window.showInformationMessage(`计算结果: ${result.value}`);
        } else {
            vscode.window.showErrorMessage(`计算失败: ${result.error}`);
        }
    });

    const proveCommand = vscode.commands.registerCommand('matha.prove', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;

        const text = editor.document.getText(editor.selection);
        vscode.window.showInformationMessage(`验证: ${text}`);
    });

    context.subscriptions.push(
        completionProvider,
        hoverProvider,
        signatureHelpProvider,
        parseCommand,
        computeCommand,
        proveCommand
    );
}

export function deactivate() {}

