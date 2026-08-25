# -*- coding: utf-8 -*-
"""Matha VS Code 扩展 — 主入口

提供：
1. 语法高亮（通过 tmGrammar 配置）
2. 智能补全（CompletionItemProvider）
3. 意图解析（Language Server Protocol）
4. 命令面板集成
"""
import vscode from 'vscode';
import { MathaLanguageClient } from './language-client';
import { MathaCompletionProvider } from './completion-provider';
import { MathaHoverProvider } from './hover-provider';
import { MathaSignatureHelpProvider } from './signature-help';

let client: MathaLanguageClient;

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

async function callMathaCompute(text: string): Promise<{ success: boolean; value?: any; error?: string }> {
    // TODO: 集成 Matha 后端
    return { success: true, value: '计算中...' };
}

export function deactivate() {}
