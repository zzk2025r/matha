// ============================================================
// Matha JavaScript 原生前端（JS → Matha IR）
// ============================================================
// 运行：node frontend.js "function foo(x) { return x + 1 }"
// 输出 JSON
// ============================================================

const fs = require('fs');

/**
 * JS 类型映射
 */
function parseJSType(ty) {
    const map = {
        'number': 'Float', 'float': 'Float', 'double': 'Float',
        'int': 'Int', 'integer': 'Int', 'bigint': 'Int',
        'boolean': 'Bool', 'bool': 'Bool',
        'string': 'String',
        'null': 'Any', 'undefined': 'Any',
    };
    return map[ty?.toLowerCase()] || 'Any';
}

/**
 * JS Token 化
 */
function tokenize(source) {
    const tokens = [];
    const re = /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`|0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+|\d+\.\d+|\d+|=>|===|!==|==|!=|<=|>=|&&|\|\||[a-zA-Z_$][a-zA-Z0-9_$]*|[+\-*/%=<>!&|^~?:.,;(){}\[\]@])/g;
    let match;
    while ((match = re.exec(source)) !== null) {
        const tok = match[0];
        if (/^\s+$/.test(tok)) continue;
        let type = 'symbol';
        if (/^["'`](.*)["'`]$/.test(tok)) type = 'string';
        else if (/^-?\d+\.\d+$/.test(tok)) type = 'literal_float';
        else if (/^-?\d+$/.test(tok)) type = 'literal_int';
        else if (/^(true|false|null|undefined)$/.test(tok)) type = 'literal_bool';
        else if (/^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(tok)) type = 'ident';
        tokens.push({ type, value: tok });
    }
    return tokens;
}

/**
 * 解析表达式
 */
function parseExpr(tokens, pos) {
    if (pos >= tokens.length) return null;
    const tok = tokens[pos];

    // 字面量
    if (tok.type === 'literal_int') return { type: 'literal', value: parseInt(tok.value), kind: 'int' };
    if (tok.type === 'literal_float') return { type: 'literal', value: parseFloat(tok.value), kind: 'float' };
    if (tok.type === 'string') return { type: 'literal', value: tok.value.slice(1, -1), kind: 'string' };
    if (tok.type === 'literal_bool') return { type: 'literal', value: tok.value === 'true', kind: 'bool' };

    // 变量
    if (tok.type === 'ident') {
        pos++;
        // 函数调用
        if (pos < tokens.length && tokens[pos].value === '(') {
            pos++; // skip (
            const args = [];
            while (pos < tokens.length && tokens[pos].value !== ')') {
                const arg = parseExpr(tokens, pos);
                if (arg) { args.push(arg); pos += 1; }
                else pos++;
                if (pos < tokens.length && tokens[pos].value === ',') pos++;
            }
            if (pos < tokens.length) pos++; // skip )
            return { type: 'call', name: tok.value, args };
        }
        return { type: 'variable', name: tok.value };
    }

    // 括号表达式
    if (tok.value === '(') {
        pos++;
        const expr = parseExpr(tokens, pos);
        if (expr && pos < tokens.length && tokens[pos].value === ')') pos++;
        return expr;
    }

    // 一元运算
    if (tok.value === '!' || tok.value === '-') {
        const operand = parseExpr(tokens, pos + 1);
        return { type: 'unary', op: tok.value, operand };
    }

    // 二元运算（简化）
    if (['+', '-', '*', '/', '%', '==', '!=', '<', '>', '<=', '>=', '&&', '||'].includes(tok.value)) {
        const left = parseExpr(tokens, pos - 1);
        const right = parseExpr(tokens, pos + 1);
        return { type: 'binary', op: tok.value, left, right };
    }

    return null;
}

/**
 * 解析 JS 函数
 */
function parseFunction(tokens, pos) {
    const funcs = [];

    // function 声明
    while (pos < tokens.length) {
        if (tokens[pos].value === 'function' || tokens[pos].value === 'const' || tokens[pos].value === 'let' || tokens[pos].value === 'var') {
            let name = '';
            let retType = 'Any';

            if (tokens[pos].value === 'function') {
                pos++; // skip 'function'
                if (pos < tokens.length && tokens[pos].type === 'ident') {
                    name = tokens[pos].value;
                    pos++;
                }
            } else {
                // const/let/var x = (...) => ... 或 function
                pos++;
                if (pos < tokens.length && tokens[pos].type === 'ident') {
                    name = tokens[pos].value;
                    pos++;
                }
                // 跳过 =
                while (pos < tokens.length && tokens[pos].value !== '=>' && tokens[pos].value !== '(' && tokens[pos].value !== '{') pos++;
            }

            // 参数
            const params = [];
            if (pos < tokens.length && tokens[pos].value === '(') {
                pos++;
                while (pos < tokens.length && tokens[pos].value !== ')') {
                    if (tokens[pos].type === 'ident' && tokens[pos].value !== 'const' && tokens[pos].value !== 'let') {
                        params.push(tokens[pos].value);
                    }
                    pos++;
                }
                if (pos < tokens.length) pos++; // skip )
            }

            // 箭头函数
            if (pos < tokens.length && tokens[pos].value === '=>') {
                pos++; // skip =>
                // 函数体
                let bodyTokens = [];
                let depth = 0;
                if (pos < tokens.length && tokens[pos].value === '{') {
                    pos++;
                    depth = 1;
                    while (pos < tokens.length && depth > 0) {
                        if (tokens[pos].value === '{') depth++;
                        else if (tokens[pos].value === '}') depth--;
                        if (depth > 0) bodyTokens.push(tokens[pos]);
                        pos++;
                    }
                } else {
                    // 单表达式
                    bodyTokens.push(tokens[pos]);
                    pos++;
                }
                const body = parseExpr(bodyTokens, 0);
                funcs.push({ name, params, body, retType });
                continue;
            }

            // 普通函数体
            if (pos < tokens.length && tokens[pos].value === '{') {
                pos++;
                let bodyTokens = [];
                let depth = 1;
                while (pos < tokens.length && depth > 0) {
                    if (tokens[pos].value === '{') depth++;
                    else if (tokens[pos].value === '}') depth--;
                    if (depth > 0) bodyTokens.push(tokens[pos]);
                    pos++;
                }
                const stmts = parseStatements(bodyTokens);
                funcs.push({ name, params, stmts, retType });
            }
        } else {
            pos++;
        }
    }
    return funcs;
}

function parseStatements(tokens) {
    const stmts = [];
    let pos = 0;
    while (pos < tokens.length) {
        if (tokens[pos].value === 'return') {
            pos++;
            const expr = parseExpr(tokens, pos);
            if (expr) stmts.push({ type: 'return', expr });
        } else if (tokens[pos].value === 'if') {
            pos++;
            const cond = parseExpr(tokens, pos);
            pos++;
            stmts.push({ type: 'if', cond });
        } else {
            const expr = parseExpr(tokens, pos);
            if (expr) stmts.push(expr);
            pos++;
        }
    }
    return stmts;
}

/**
 * 编译
 */
function compile(source) {
    const tokens = tokenize(source);
    const funcs = parseFunction(tokens, 0);

    const functions = {};
    const types = {};
    const effects = {};

    for (const f of funcs) {
        functions[f.name] = f.stmts || f.body;
        types[f.name] = f.retType;
        // 效应分析
        const src = JSON.stringify(f.stmts || f.body || '');
        effects[f.name] = /console\.|document\.|window\.|alert\(|prompt\(|fetch\(/.test(src) ? 'IO' : 'Pure';
    }

    return {
        language: 'javascript',
        source,
        functions,
        types,
        effects,
        errors: []
    };
}

// ── 入口 ──────────────────────────────────────────────────────

if (require.main === module) {
    const source = process.argv[2] || '';
    const result = compile(source);
    console.log(JSON.stringify(result, null, 2));
}

module.exports = { compile, tokenize, parseExpr };
