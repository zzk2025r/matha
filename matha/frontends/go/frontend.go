// ============================================================
// Matha Go 原生前端（Go → Matha IR）
// ============================================================
// 编译：go build -o matha_go_frontend.exe frontend.go
// 使用：./matha_go_frontend "func foo(x int) int { return x + 1 }"
// 输出 JSON
// ============================================================

package main

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"strings"
)

type CompileResult struct {
	Language  string            `json:"language"`
	Source    string            `json:"source"`
	Functions map[string][]json.RawMessage `json:"functions"`
	Types     map[string]string         `json:"types"`
	Effects   map[string]string         `json:"effects"`
	Errors    []string                  `json:"errors,omitempty"`
}

func NewResult(source string) *CompileResult {
	return &CompileResult{
		Language:  "go",
		Source:    source,
		Functions: make(map[string][]json.RawMessage),
		Types:     make(map[string]string),
		Effects:   make(map[string]string),
	}
}

func parseGoType(ty string) string {
	switch strings.TrimSpace(ty) {
	case "int", "int8", "int16", "int32", "int64", "uint", "uint8", "uint16", "uint32", "uint64", "byte", "rune":
		return "Int"
	case "float32", "float64":
		return "Float"
	case "bool":
		return "Bool"
	case "string":
		return "String"
	default:
		return "Any"
	}
}

func tokenizeGo(source string) []string {
	re := regexp.MustCompile(`\s+|([{}();,\[\]:=<>\+\-\*/%!=|&^~@.])`)
	return re.Split(source, -1)
}

func parseGoFunc(source string, pos *int, tokens []string) (string, []json.RawMessage, string, []string) {
	name := ""
	var stmts []json.RawMessage

	*pos++ // skip "func"
	if *pos < len(tokens) && tokens[*pos] != "" {
		name = tokens[*pos]
		*pos++
	}

	// 跳过参数列表
	if *pos < len(tokens) && tokens[*pos] == "(" {
		*pos++
		for *pos < len(tokens) && tokens[*pos] != ")" {
			if tokens[*pos] != "" && tokens[*pos] != "," {
				// 参数类型跳过
			}
			*pos++
		}
		if *pos < len(tokens) { *pos++ }
	}

	// 返回类型
	retType := "Any"
	if *pos < len(tokens) && tokens[*pos] != "" && tokens[*pos] != "{" {
		retType = parseGoType(tokens[*pos])
		*pos++
	}

	// 函数体
	if *pos < len(tokens) && tokens[*pos] == "{" {
		*pos++
		bodyTokens := []string{}
		depth := 1
		for *pos < len(tokens) && depth > 0 {
			if tokens[*pos] == "{" {
				depth++
			} else if tokens[*pos] == "}" {
				depth--
			}
			if depth > 0 && tokens[*pos] != "" {
				bodyTokens = append(bodyTokens, tokens[*pos])
			}
			*pos++
		}
		stmts = parseGoStmts(bodyTokens)
	}

	return name, stmts, retType, nil
}

func parseGoStmts(tokens []string) []json.RawMessage {
	var stmts []json.RawMessage
	pos := 0
	for pos < len(tokens) {
		tok := tokens[pos]
		switch tok {
		case "return":
			pos++
			if pos < len(tokens) {
				expr, _ := json.Marshal(map[string]interface{}{"type": "return", "expr": tokenizeGoExpr(tokens[pos:])})
				stmts = append(stmts, expr)
			}
		case "if":
			pos++
			expr, _ := json.Marshal(map[string]interface{}{"type": "if", "cond": tokens[pos]})
			stmts = append(stmts, expr)
			pos++
		case "for":
			pos++
			expr, _ := json.Marshal(map[string]interface{}{"type": "for"})
			stmts = append(stmts, expr)
		case "fmt", "fmt.Println", "fmt.Printf":
			expr, _ := json.Marshal(map[string]interface{}{"type": "call", "name": tok})
			stmts = append(stmts, expr)
			pos++
		default:
			expr, _ := json.Marshal(map[string]interface{}{"type": "expr", "tokens": tokens[pos:]})
			stmts = append(stmts, expr)
			pos++
		}
	}
	return stmts
}

func tokenizeGoExpr(tokens []string) interface{} {
	if len(tokens) == 0 { return nil }
	tok := tokens[0]
	if tok == "" { return nil }
	var f float64
	if _, err := fmt.Sscanf(tok, "%f", &f); err == nil { return f }
	var i int
	if _, err := fmt.Sscanf(tok, "%d", &i); err == nil { return i }
	return tok
}

func compile(source string) *CompileResult {
	result := NewResult(source)
	tokens := tokenizeGo(source)
	pos := 0

	for pos < len(tokens) {
		if tokens[pos] == "func" {
			name, stmts, retType, _ := parseGoFunc(source, &pos, tokens)
			if name != "" {
				result.Functions[name] = stmts
				result.Types[name] = retType
				hasIO := false
				for _, s := range stmts {
					smap := map[string]interface{}{}
					json.Unmarshal(s, &smap)
					if n, ok := smap["name"].(string); ok {
						if strings.Contains(n, "Print") || strings.Contains(n, "Scan") {
							hasIO = true
						}
					}
				}
				if hasIO {
					result.Effects[name] = "IO"
				} else {
					result.Effects[name] = "Pure"
				}
			}
		} else {
			pos++
		}
	}
	return result
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: matha_go_frontend <source.go>\n")
		os.Exit(1)
	}
	result := compile(os.Args[1])
	out, _ := json.MarshalIndent(result, "", "  ")
	fmt.Println(string(out))
}
