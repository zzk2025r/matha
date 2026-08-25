# -*- coding: utf-8 -*-
"""Matha VS Code 扩展 — 智能补全提供者

提供：
1. 数学函数补全（sin, cos, tan, log, sqrt...）
2. 数学常量补全（π, e, φ）
3. 关键词补全（函数, 如果, 循环, 返回...）
4. 意图模板补全
"""
import vscode from 'vscode';

export class MathaCompletionProvider implements vscode.CompletionItemProvider {
    private static readonly MATH_FUNCTIONS = [
        'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2',
        'log', 'log2', 'log10', 'exp', 'sqrt', 'cbrt',
        'abs', 'floor', 'ceil', 'round', 'trunc',
        'gcd', 'lcm', 'factorial', 'is_prime',
        'power', 'mod', 'min', 'max', 'sum',
    ];

    private static readonly MATH_CONSTANTS = [
        { label: 'π', insertText: 'π', detail: '圆周率 ≈ 3.14159', kind: vscode.CompletionItemKind.Constant },
        { label: 'e', insertText: 'e', detail: '自然常数 ≈ 2.71828', kind: vscode.CompletionItemKind.Constant },
        { label: 'φ', insertText: 'φ', detail: '黄金比例 ≈ 1.61803', kind: vscode.CompletionItemKind.Constant },
        { label: '∞', insertText: '∞', detail: '无穷大', kind: vscode.CompletionItemKind.Constant },
    ];

    private static readonly KEYWORDS = [
        { label: '函数', insertText: '函数 ${1:name}(${2:params})\n  ${0:body}\n结束', detail: '定义函数', kind: vscode.CompletionItemKind.Snippet },
        { label: '如果', insertText: '如果 ${1:条件}:\n  ${2:then}\n否则:\n  ${3:else}\n结束', detail: '条件语句', kind: vscode.CompletionItemKind.Snippet },
        { label: '循环', insertText: '循环 ${1:i} 从 ${2:0} 到 ${3:n}:\n  ${0:body}', detail: '循环语句', kind: vscode.CompletionItemKind.Snippet },
        { label: '返回', insertText: '返回 ${0:result}', detail: '返回结果', kind: vscode.CompletionItemKind.Snippet },
    ];

    private static readonly MATH_OPERATORS = [
        { label: '∧', insertText: '∧', detail: '逻辑与', kind: vscode.CompletionItemKind.Operator },
        { label: '∨', insertText: '∨', detail: '逻辑或', kind: vscode.CompletionItemKind.Operator },
        { label: '¬', insertText: '¬', detail: '逻辑非', kind: vscode.CompletionItemKind.Operator },
        { label: '→', insertText: '→', detail: '蕴含', kind: vscode.CompletionItemKind.Operator },
        { label: '↔', insertText: '↔', detail: '等价', kind: vscode.CompletionItemKind.Operator },
        { label: '∈', insertText: '∈', detail: '属于', kind: vscode.CompletionItemKind.Operator },
        { label: '⊆', insertText: '⊆', detail: '子集', kind: vscode.CompletionItemKind.Operator },
        { label: '∪', insertText: '∪', detail: '并集', kind: vscode.CompletionItemKind.Operator },
        { label: '∩', insertText: '∩', detail: '交集', kind: vscode.CompletionItemKind.Operator },
        { label: '∑', insertText: '∑', detail: '求和', kind: vscode.CompletionItemKind.Operator },
        { label: '∏', insertText: '∏', detail: '求积', kind: vscode.CompletionItemKind.Operator },
        { label: '∫', insertText: '∫', detail: '积分', kind: vscode.CompletionItemKind.Operator },
        { label: '∂', insertText: '∂', detail: '偏导数', kind: vscode.CompletionItemKind.Operator },
        { label: '√', insertText: '√', detail: '开方', kind: vscode.CompletionItemKind.Operator },
        { label: '≈', insertText: '≈', detail: '近似相等', kind: vscode.CompletionItemKind.Operator },
        { label: '≠', insertText: '≠', detail: '不等', kind: vscode.CompletionItemKind.Operator },
    ];

    provideCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        token: vscode.CancellationToken,
        context: vscode.CompletionContext
    ): vscode.CompletionItem[] | vscode.CompletionList {
        const line = document.lineAt(position).text;
        const word = document.getText(new vscode.Range(
            new vscode.Position(position.line, Math.max(0, position.character - 10)),
            position
        )).toLowerCase();

        const items: vscode.CompletionItem[] = [];

        // 函数补全
        for (const fn of this.MATH_FUNCTIONS) {
            const item = new vscode.CompletionItem(fn, vscode.CompletionItemKind.Function);
            item.detail = `数学函数`;
            item.insertText = new vscode.SnippetString(`${fn}(${0})`);
            items.push(item);
        }

        // 常量补全
        items.push(...this.MATH_CONSTANTS);

        // 关键词补全
        items.push(...this.KEYWORDS);

        // 运算符补全
        items.push(...this.MATH_OPERATORS);

        // 意图模板补全
        const intentTemplates = this.getIntentTemplates(line, word);
        items.push(...intentTemplates);

        return items;
    }

    private getIntentTemplates(line: string, word: string): vscode.CompletionItem[] {
        const templates: vscode.CompletionItem[] = [];

        // 自动检测意图类型
        if (word.includes('计算') || word.includes('求')) {
            templates.push(new vscode.CompletionItem('📐 计算模板', vscode.CompletionItemKind.Snippet));
        }
        if (word.includes('证明') || word.includes('验证')) {
            templates.push(new vscode.CompletionItem('✅ 证明模板', vscode.CompletionItemKind.Snippet));
        }
        if (word.includes('积分') || word.includes('微分')) {
            templates.push(new vscode.CompletionItem('📊 微积分模板', vscode.CompletionItemKind.Snippet));
        }
        if (word.includes('素数') || word.includes('质数')) {
            templates.push(new vscode.CompletionItem('🔢 数论模板', vscode.CompletionItemKind.Snippet));
        }

        return templates;
    }
}
