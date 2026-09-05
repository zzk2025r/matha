// -*- coding: utf-8 -*-
// ============================================================
// Matha Rust 原生前端（Rust → Matha IR）
// ============================================================
// 编译：rustc -o matha_rust_frontend.exe frontend.rs
// 使用：./matha_rust_frontend "fn foo(x: i32) -> i32 { x + 1 }"
// 输出 JSON
// ============================================================

use std::collections::HashMap;
use std::env;
use std::process;

#[derive(Debug, Clone)]
enum IRNode {
    Literal(i64),
    FloatLiteral(f64),
    StringLiteral(String),
    BoolLiteral(bool),
    Variable(String),
    BinaryOp {
        op: String,
        left: Box<IRNode>,
        right: Box<IRNode>,
    },
    UnaryOp {
        op: String,
        operand: Box<IRNode>,
    },
    FuncCall {
        name: String,
        args: Vec<IRNode>,
    },
    IfExpr {
        cond: Box<IRNode>,
        then_branch: Box<IRNode>,
        else_branch: Box<IRNode>,
    },
    Return(Box<IRNode>),
    Block {
        stmts: Vec<IRNode>,
    },
}

#[derive(Debug)]
struct CompileResult {
    language: String,
    source: String,
    functions: HashMap<String, Vec<IRNode>>,
    types: HashMap<String, String>,
    effects: HashMap<String, String>,
    errors: Vec<String>,
}

impl CompileResult {
    fn new(language: &str, source: &str) -> Self {
        CompileResult {
            language: language.to_string(),
            source: source.to_string(),
            functions: HashMap::new(),
            types: HashMap::new(),
            effects: HashMap::new(),
            errors: Vec::new(),
        }
    }

    fn to_json(&self) -> String {
        let mut json = String::from("{");
        json.push_str(&format!("\"language\":{},", json_str(&self.language)));
        json.push_str("\"functions\":{");
        let mut first = true;
        for (name, stmts) in &self.functions {
            if !first {
                json.push_str(",");
            }
            first = false;
            json.push_str(&format!("{}:{},", json_str(name), nodes_to_json(stmts)));
        }
        json.push_str("}");
        json.push_str(",\"types\":{");
        first = true;
        for (name, ty) in &self.types {
            if !first {
                json.push_str(",");
            }
            first = false;
            json.push_str(&format!("{}:{}", json_str(name), json_str(ty)));
        }
        json.push_str("}");
        json.push_str(",\"effects\":{");
        first = true;
        for (name, eff) in &self.effects {
            if !first {
                json.push_str(",");
            }
            first = false;
            json.push_str(&format!("{}:{}", json_str(name), json_str(eff)));
        }
        json.push_str("}");
        if !self.errors.is_empty() {
            json.push_str(",\"errors\":[");
            for (i, err) in self.errors.iter().enumerate() {
                if i > 0 {
                    json.push_str(",");
                }
                json.push_str(&json_str(err));
            }
            json.push_str("]");
        }
        json.push('}');
        json
    }
}

fn json_str(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c < ' ' => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn node_to_json(node: &IRNode) -> String {
    match node {
        IRNode::Literal(v) => format!("{{\"type\":\"literal\",\"value\":{},\"kind\":\"int\"}}", v),
        IRNode::FloatLiteral(v) => format!(
            "{{\"type\":\"literal\",\"value\":{},\"kind\":\"float\"}}",
            v
        ),
        IRNode::StringLiteral(v) => format!(
            "{{\"type\":\"literal\",\"value\":{},\"kind\":\"string\"}}",
            json_str(v)
        ),
        IRNode::BoolLiteral(v) => {
            format!("{{\"type\":\"literal\",\"value\":{},\"kind\":\"bool\"}}", v)
        }
        IRNode::Variable(name) => format!("{{\"type\":\"variable\",\"name\":{}}}", json_str(name)),
        IRNode::BinaryOp { op, left, right } => format!(
            "{{\"type\":\"binary\",\"op\":{},\"left\":{},\"right\":{}}}",
            json_str(op),
            node_to_json(left),
            node_to_json(right)
        ),
        IRNode::UnaryOp { op, operand } => format!(
            "{{\"type\":\"unary\",\"op\":{},\"operand\":{}}}",
            json_str(op),
            node_to_json(operand)
        ),
        IRNode::FuncCall { name, args } => {
            let args_json: Vec<String> = args.iter().map(|a| node_to_json(a)).collect();
            format!(
                "{{\"type\":\"call\",\"name\":{},\"args\":[{}]}}",
                json_str(name),
                args_json.join(",")
            )
        }
        IRNode::IfExpr {
            cond,
            then_branch,
            else_branch,
        } => format!(
            "{{\"type\":\"if\",\"cond\":{},\"then\":{},\"else\":{}}}",
            node_to_json(cond),
            node_to_json(then_branch),
            node_to_json(else_branch)
        ),
        IRNode::Return(expr) => format!("{{\"type\":\"return\",\"expr\":{}}}", node_to_json(expr)),
        IRNode::Block { stmts } => format!(
            "{{\"type\":\"block\",\"stmts\":[{}]}}",
            stmts.iter().map(node_to_json).collect::<Vec<_>>().join(",")
        ),
    }
}

fn nodes_to_json(nodes: &[IRNode]) -> String {
    format!(
        "[{}]",
        nodes.iter().map(node_to_json).collect::<Vec<_>>().join(",")
    )
}

// ── 词法分析 ──────────────────────────────────────────────────

fn tokenize(source: &str) -> Vec<(String, String)> {
    let mut tokens = Vec::new();
    let mut chars = source.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            ' ' | '\t' | '\r' => continue,
            '\n' => continue,
            ';' => tokens.push(("semi".into(), ";".into())),
            ',' => tokens.push(("comma".into(), ",".into())),
            '(' => tokens.push(("lparen".into(), "(".into())),
            ')' => tokens.push(("rparen".into(), ")".into())),
            '{' => tokens.push(("lbrace".into(), "{".into())),
            '}' => tokens.push(("rbrace".into(), "}".into())),
            '+' => tokens.push(("plus".into(), "+".into())),
            '-' => {
                if chars.peek() == Some(&'>') {
                    chars.next();
                    tokens.push(("arrow".into(), "->".into()));
                } else {
                    tokens.push(("minus".into(), "-".into()));
                }
            }
            '*' => tokens.push(("star".into(), "*".into())),
            '/' => {
                if chars.peek() == Some(&'/') {
                    while let Some(&nc) = chars.peek() {
                        if nc == '\n' {
                            chars.next();
                            break;
                        } else {
                            chars.next();
                        }
                    }
                } else {
                    tokens.push(("div".into(), "/".into()));
                }
            }
            '=' => {
                if chars.peek() == Some(&'=') {
                    chars.next();
                    tokens.push(("eq".into(), "==".into()));
                } else {
                    tokens.push(("assign".into(), "=".into()));
                }
            }
            '!' => {
                if chars.peek() == Some(&'=') {
                    chars.next();
                    tokens.push(("ne".into(), "!=".into()));
                } else {
                    tokens.push(("not".into(), "!".into()));
                }
            }
            '<' => {
                if chars.peek() == Some(&'=') {
                    chars.next();
                    tokens.push(("le".into(), "<=".into()));
                } else {
                    tokens.push(("lt".into(), "<".into()));
                }
            }
            '>' => {
                if chars.peek() == Some(&'=') {
                    chars.next();
                    tokens.push(("ge".into(), ">=".into()));
                } else {
                    tokens.push(("gt".into(), ">".into()));
                }
            }
            '&' => {
                if chars.peek() == Some(&'&') {
                    chars.next();
                    tokens.push(("and".into(), "&&".into()));
                } else {
                    tokens.push(("bit_and".into(), "&".into()));
                }
            }
            '|' => {
                if chars.peek() == Some(&'|') {
                    chars.next();
                    tokens.push(("or".into(), "||".into()));
                } else {
                    tokens.push(("bit_or".into(), "|".into()));
                }
            }
            '%' => tokens.push(("mod".into(), "%".into())),
            '.' => tokens.push(("dot".into(), ".".into())),
            '0'..='9' => {
                let mut num = String::from(c);
                while let Some(&nc) = chars.peek() {
                    if nc.is_ascii_digit() || nc == '.' {
                        num.push(nc);
                        chars.next();
                    } else {
                        break;
                    }
                }
                tokens.push(("literal".into(), num));
            }
            '"' => {
                let mut s = String::new();
                loop {
                    match chars.next() {
                        Some('"') => break,
                        Some('\\') => {
                            s.push(chars.next().unwrap_or(' '));
                        }
                        Some(c) => s.push(c),
                        None => break,
                    }
                }
                tokens.push(("string".into(), s));
            }
            'a'..='z' | 'A'..='Z' | '_' => {
                let mut ident = String::from(c);
                while let Some(&nc) = chars.peek() {
                    if nc.is_alphanumeric() || nc == '_' {
                        ident.push(nc);
                        chars.next();
                    } else {
                        break;
                    }
                }
                tokens.push(("ident".into(), ident));
            }
            _ => {}
        }
    }
    tokens
}

// ── 类型解析 ───────────────────────────────────────────────────

fn parse_type(ty: &str) -> String {
    match ty.trim() {
        "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16" | "usize" => "Int".to_string(),
        "isize" | "f32" | "f64" | "f128" => "Float".to_string(),
        "bool" => "Bool".to_string(),
        "String" | "&str" | "char" => "String".to_string(),
        _ => "Any".to_string(),
    }
}

// ── 表达式解析 ─────────────────────────────────────────────────

fn parse_expr(tokens: &[(String, String)], pos: &mut usize) -> Option<IRNode> {
    parse_term(tokens, pos)
}

fn parse_term(tokens: &[(String, String)], pos: &mut usize) -> Option<IRNode> {
    let left = parse_factor(tokens, pos)?;
    loop {
        if *pos >= tokens.len() {
            break;
        }
        let (ty, val) = &tokens[*pos];
        if ty == "plus" || ty == "minus" {
            *pos += 1;
            let right = parse_factor(tokens, pos)?;
            return Some(IRNode::BinaryOp {
                op: val.clone(),
                left: Box::new(left),
                right: Box::new(right),
            });
        }
        break;
    }
    Some(left)
}

fn parse_factor(tokens: &[(String, String)], pos: &mut usize) -> Option<IRNode> {
    if *pos >= tokens.len() {
        return None;
    }
    let ty = tokens[*pos].0.clone();
    let val = tokens[*pos].1.clone();

    match ty.as_str() {
        "literal" => {
            *pos += 1;
            if val.contains('.') {
                Some(IRNode::FloatLiteral(val.parse().unwrap_or(0.0)))
            } else {
                Some(IRNode::Literal(val.parse().unwrap_or(0)))
            }
        }
        "string" => {
            *pos += 1;
            Some(IRNode::StringLiteral(val))
        }
        "true" | "false" => {
            *pos += 1;
            Some(IRNode::BoolLiteral(val == "true"))
        }
        "not" => {
            *pos += 1;
            let operand = parse_factor(tokens, pos)?;
            Some(IRNode::UnaryOp {
                op: "not".to_string(),
                operand: Box::new(operand),
            })
        }
        "minus" => {
            *pos += 1;
            let operand = parse_factor(tokens, pos)?;
            Some(IRNode::UnaryOp {
                op: "-".to_string(),
                operand: Box::new(operand),
            })
        }
        "ident" => {
            *pos += 1;
            if *pos < tokens.len() && tokens[*pos].0 == "lparen" {
                let fn_name = val;
                *pos += 1; // skip (
                let mut args = Vec::new();
                while *pos < tokens.len() && tokens[*pos].0 != "rparen" {
                    if *pos > 0 && tokens[*pos - 1].0 == "comma" {
                        *pos += 1;
                    }
                    if let Some(arg) = parse_expr(tokens, pos) {
                        args.push(arg);
                    } else {
                        *pos += 1;
                    }
                }
                if *pos < tokens.len() {
                    *pos += 1;
                } // skip )
                Some(IRNode::FuncCall {
                    name: fn_name,
                    args,
                })
            } else {
                Some(IRNode::Variable(val))
            }
        }
        "lparen" => {
            *pos += 1;
            let expr = parse_expr(tokens, pos);
            if *pos < tokens.len() && tokens[*pos].0 == "rparen" {
                *pos += 1;
            }
            expr
        }
        _ => None,
    }
}

// ── 语句解析 ───────────────────────────────────────────────────

fn parse_stmts(tokens: &[(String, String)], start: usize, end: usize) -> Vec<IRNode> {
    let mut stmts = Vec::new();
    let mut pos = start;
    while pos < end {
        if tokens[pos].0 == "rbrace" {
            break;
        }

        if tokens[pos].0 == "ident" && tokens[pos].1 == "return" {
            pos += 1;
            if let Some(expr) = parse_expr(tokens, &mut pos) {
                stmts.push(IRNode::Return(Box::new(expr)));
            }
            continue;
        }

        if tokens[pos].0 == "ident" && tokens[pos].1 == "if" {
            pos += 1;
            let cond = parse_expr(tokens, &mut pos).unwrap_or(IRNode::Literal(0));
            let then_expr = parse_expr(tokens, &mut pos).unwrap_or(IRNode::Literal(0));
            stmts.push(IRNode::IfExpr {
                cond: Box::new(cond),
                then_branch: Box::new(then_expr),
                else_branch: Box::new(IRNode::Literal(0)),
            });
            continue;
        }

        if let Some(expr) = parse_expr(tokens, &mut pos) {
            stmts.push(expr);
        } else {
            pos += 1;
        }
    }
    stmts
}

// ── 函数定义解析 ───────────────────────────────────────────────

fn parse_func(
    tokens: &[(String, String)],
    start: usize,
) -> Option<(String, Vec<IRNode>, String, String)> {
    if start >= tokens.len() || tokens[start].0 != "ident" || tokens[start].1 != "fn" {
        return None;
    }
    let mut pos = start + 1; // skip "fn"

    if pos >= tokens.len() || tokens[pos].0 != "ident" {
        return None;
    }
    let name = tokens[pos].1.clone();
    pos += 1;

    let mut params = Vec::new();
    if pos < tokens.len() && tokens[pos].0 == "lparen" {
        pos += 1;
        while pos < tokens.len() && tokens[pos].0 != "rparen" {
            if tokens[pos].0 == "ident" {
                params.push(tokens[pos].1.clone());
            }
            pos += 1;
        }
        if pos < tokens.len() {
            pos += 1;
        }
    }

    let mut ret_type = "Any".to_string();
    if pos < tokens.len() && tokens[pos].0 == "arrow" {
        pos += 1;
        if pos < tokens.len() && tokens[pos].0 == "ident" {
            ret_type = parse_type(&tokens[pos].1);
            pos += 1;
        }
    }

    if pos >= tokens.len() || tokens[pos].0 != "lbrace" {
        return None;
    }
    pos += 1;

    let mut depth = 1;
    let mut end = pos;
    while end < tokens.len() && depth > 0 {
        if tokens[end].0 == "lbrace" {
            depth += 1;
        } else if tokens[end].0 == "rbrace" {
            depth -= 1;
        }
        end += 1;
    }

    let stmts = parse_stmts(tokens, pos, end - 1);
    Some((name, stmts, params.join(","), ret_type))
}

// ── 主编译逻辑 ─────────────────────────────────────────────────

fn compile(source: &str) -> CompileResult {
    let mut result = CompileResult::new("rust", source);
    let tokens = tokenize(source);

    let mut pos = 0;
    while pos < tokens.len() {
        if tokens[pos].0 == "ident" && tokens[pos].1 == "fn" {
            if let Some((name, stmts, _params, ret_type)) = parse_func(&tokens, pos) {
                let has_io = stmts.iter().any(|s| matches!(s, IRNode::FuncCall { name: n, .. } if n == "println" || n == "print"));
                result.functions.insert(name.clone(), stmts);
                result.types.insert(name.clone(), ret_type);
                result.effects.insert(
                    name,
                    if has_io {
                        "IO".to_string()
                    } else {
                        "Pure".to_string()
                    },
                );
            }
            pos += 1;
            continue;
        }
        pos += 1;
    }
    result
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: matha_rust_frontend <source.rs>");
        process::exit(1);
    }
    let source = &args[1];
    let result = compile(source);
    println!("{}", result.to_json());
}
