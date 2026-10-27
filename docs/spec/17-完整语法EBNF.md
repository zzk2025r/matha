# 17 - 完整语法 EBNF

> 本章用 EBNF（ISO/IEC 14977 风格）定义 Matha 的完整语法。已整合 [02](02-词法结构.md)–[16](16-形式化语义.md) 各章定稿的产生式。标注 `(* 草案 *)` 的为待确认项。

## EBNF 约定

- 终结符用双引号：`"+"`、`"【"`
- 非终结符用尖括号：`<expr>`
- `=` 定义，`;` 结束，`,` 拼接，`|` 选择，`[ ... ]` 可选，`{ ... }` 重复，`( ... )` 分组
- Matha 含多字节 Unicode 符号（`？【】〔〕《》#：`），按字面终结符处理
- 注释：`(* ... *)`

---

## 1. 顶层结构

```ebnf
<program>    = { <top_level> } ;

<top_level>  = <module_decl> | <import_decl> | <nl_block> | <mech_unit> | <command_unit> | <decl> ;

<decl>       = <binding> | <func_def> | <type_def> ;
```

---

## 2. 词法层：Matha 符号体系（[02](02-词法结构.md)）

### 2.1 运算符号

```ebnf
<plus>      = "+" ;
<minus>     = "-" ;
<star>      = "*" ;
<slash>     = "/" ;
<power>     = "^" ;                       (* 双语义：中缀次方 2^3=8 / 前缀开方 ^9=3，语法层按位置消解 *)
<assign>    = "=" ;
<lt>        = "<" ;
<gt>        = ">" ;
<le>        = "<=" ;
<ge>        = ">=" ;
<angle>     = "<<" ;                      (* 角度运算：<<90 表示 90° *)
<next>      = ">>" ;                      (* 步进/迭代/属于 *)

<arith_op>  = <plus> | <minus> | <star> | <slash> | <power> ;
<rel_op>    = <lt> | <gt> | <le> | <ge> | <assign> ;
```

> 已确认（M1 走查）：`<<` 角度、`>>` 步进、`^` 次方、`<=`/`>=` 主流形式。最长匹配优先。

### 2.2 变量与占位

```ebnf
<placeholder> = "？" ;                    (* 公式通用占位，可用 26 字母替代 *)
<identifier>  = <letter> , { <letter> | <digit> | "_" } ;
<letter>      = <ascii_letter> | <cjk_letter> ;
<ascii_letter> = "a" | "b" | ... | "z" | "A" | ... | "Z" ;
<cjk_letter>  = (* U+4E00–U+9FFF 等 CJK 表意文字 *) ;
<variable>    = <placeholder> | <identifier> ;
```

### 2.3 读取符号

```ebnf
<read_open>  = "【" | "〔" ;
<read_close> = "】" | "〕" ;
<read_block> = <read_open> , <read_content> , <read_close> ;
<read_natural> = <read_open> , <annotation> , <read_close> , <natural_lang> ;
<read_command> = <read_open> , <command_literal> , <read_close> ;
```

> 已确认：`【】` 与 `〔〕` 等价，可互换。配对须一致（`【` 配 `】`，`〔` 配 `〕`）。

### 2.4 输出 / 标注 / 命令 / 分隔 / 设定 / 代码块

```ebnf
<output>           = "[" , [ <expr> ] , "]" ;
<annotation>       = "*/" , <annot_text> , [ "*" , <expr> ] , "/*" ;   (* 文字 + 可选公式：*/文字/* 或 */文字*公式/* *)
<annot_text>       = <identifier> | <natural_lang_fragment> ;
(* 命令字面量：《文字》 与 【文字】 两种写法共存（M3.1 已确认，完全等价） *)
<command_literal>  = <cn_command_literal> | <bracket_command_literal> ;
<cn_command_literal> = "《" , <command_text> , "》" ;
<bracket_command_literal> = "【" , <command_text> , "】" ;
<command_text>     = <identifier> | <natural_lang_fragment> ;
<generate>         = "#：" ;                                          (* 无段号生成/运行（模板/不可编辑代码用） *)
<gen_command>      = "#：" , <command_literal> ;                      (* 无段号生成命令 *)
<chained_command>  = <command_literal> , { ">>" , ( <command_literal> | <output_trail> | <set_up> | <gen_stmt> | <gen_stmt_seg> ) } ;
<separator>        = "|" ;
<cn_separator>     = "，" | "," ;                                   (* 中文逗号分格 / 英文逗号 等价 *)

(* @ 设定：双形式（两者都支持） *)
<set_up>           = <set_up_paren> | <set_up_prefix> ;
<set_up_paren>     = "@" , "(" , <set_up_item> , { "|" , <set_up_item> } , ")" ;
<set_up_prefix>    = "@" , ( ":" | "：" ) , <set_up_item> , { <cn_separator> , <set_up_item> } ;
<set_up_item>      = ( <variable> | <path_expr> ) , [ <annotation> ] , [ "=" , <expr> ] ;  (* 变量/路径 + 标注 + 可选绑定 *)

(* 单位后缀：纯字符串，不做量纲处理 *)
<unit>             = <cjk_letter> , { <cjk_letter> } ;              (* 米 / 秒 / 千克 / 元 …… *)

(* 代码块 { } （与集合构造在语法层统一由最外层消解） *)
<code_block>       = "{" , <newline> , { <mech_stmt> , <newline> } , "}" ;
```

> 已确认（综合用户示例 M2）：
> - `@` 设定两种等价形式：`@(a|b)` 与 `@:a，b`（中文逗号分格）
> - `>>` 统一为「下一个 / 到 / 下一级」四重语义：步进 / 属于 / 路径距离 / **通用链式执行**（M3.1 新增）
> - 单位 `米/秒/千克` 等为字符串，不做量纲换算
> - `{代码}` 代表「一串代码是整体」，用作最外层机械单元或嵌套代码块

### 2.5 段编号 / 带段号生成 & 设定（M3 新增）

```ebnf
(* 段序号：从 1 起排列，任意位整数（M3 已确认） *)
<seg_id>         = <digit_1_9> , { <digit> } ;
<digit_1_9>      = "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

(* 带段号生成/运行 #N：或 #N：（半/全角冒号都允许，M3 已确认） *)
<generate_seg>   = "#" , <seg_id> , ( ":" | "：" ) ;
<gen_command_seg> = <generate_seg> , <command_literal> ;

(* 带段号设定 @N(...) / @N:xxx，yyy（半/全角冒号都允许） *)
<set_up_seg>         = <set_up_seg_paren> | <set_up_seg_prefix> ;
<set_up_seg_paren>   = "@" , <seg_id> , "(" , <set_up_item> , { "|" , <set_up_item> } , ")" ;
<set_up_seg_prefix>  = "@" , <seg_id> , ( ":" | "：" ) , <set_up_item> , { <cn_separator> , <set_up_item> } ;
```

### 2.6 循环后缀（硬性区分段级 / 全局）+ 全局编号 + 文件标记（M3 新增）

```ebnf
(* 循环分数：半角 (x/y) 与全角（x/y）等价（M3 已确认） *)
<loop_fraction>  = ( "(" | "（" ) , <digit_seq> , "/" , <digit_seq> , ( ")" | "）" ) ;
<digit_seq>      = <digit> , { <digit> } ;

(* 段级循环后缀：单省略号 … （硬性区分：段级必须一个，M3 已确认） *)
<seg_loop_suffix>    = "…" , [ <seg_id> ] , <loop_fraction> ;

(* 全局循环后缀：双省略号 …… （硬性区分：全局必须两个，M3 已确认） *)
<global_loop_suffix> = "……" , <loop_fraction> ;

(* 输出 + 段循环 + 子文件 + 全局编号 + 全局循环 + 文件路径（M3.3 更新：按位置区分子文件/文件，取代原 inline_path_ref） *)
<output_trail>       = <output>
                     , [ <seg_loop_suffix>
                       , [ <subfile_ref> ]                       (* 段循环后：子文件，下位文件补充/扩充，| 分隔多个 *)
                       , [ <global_code_id> ]
                       , [ <global_loop_suffix>
                         , [ <file_ref> ]                        (* 全局循环后：文件路径，当前文件被分割成多文件 *)
                         ]
                       ] ;
(* M3.2 推荐的分行写法：循环+子文件+路径单独一行写为 <seg_loop_line> *)
<seg_loop_line>      = <generate_seg> , <seg_loop_suffix> , [ <subfile_ref> ] , [ <global_code_id> ] , [ <global_loop_suffix> , [ <file_ref> ] ] ;

(* 段循环后子文件引用：下位文件，补充/扩充当前段；多个用 | 分隔（M3.3 新增） *)
<subfile_ref>        = ( "【" | "〔" ) , <path_content> , { "|" , <path_content> } , ( "】" | "〕" ) ;
(* 全局循环后文件路径：当前代码文件被分割/分化成多个文件使用（M3.3 新增） *)
<file_ref>           = ( "【" | "〔" ) , <path_content> , ( "】" | "〕" ) ;

(* 全局代码编号：任意位数字，不固定位数（M3 已确认） *)
<global_code_id>     = <digit_seq> ;
<global_id_stmt>     = <global_code_id> ;     (* 跨文件绑定：下一文件最开头单独一行全局编号 *)

(* >> 通用链式：可连接任意语句类型（M3.1 已确认；M3.2 强调触发条件——单条命令/单条输出不足以完成任务时才启用；否则优先使用命令/输出的独立读取能力） *)
<chain_stmt>         = <mech_stmt> , { ">>" , <mech_stmt> } ;

(* 资源字面量：命令 <bracket_command_literal> 与输出 <output> 均可独立读取 URL/网站/文件/文件夹/端口（M3.2 升格为一等能力，语义层识别资源类型，语法层复用已有产生式） *)

(* 文件尾标记 / 路径引用（文件/文件夹路径都合法，M3 已确认：用于输入文件名/文件夹查找引用） *)
<file_marker>    = <generate> , <read_open> , <path_content> , <read_close> ;
<path_content>   = "文件" | <identifier> | <path_literal> ;
<path_literal>   = { <path_char> } ;                               (* 路径字符：字母/数字/_/-/./\\ /:/空格 … *)
<path_char>      = <letter> | <digit> | "_" | "-" | "." | "/" | "\\" | ":" | " " ;
```

> 已确认（综合用户示例 M3）：
> - 段序号从 1 起排列，任意位整数；`#N:`/`@N:` 半/全角冒号都允许
> - 省略号硬性区分：`…`(单) = 段级循环；`……`(双) = 全局循环
> - 分数括号半/全角都可：`(0/1)` 与 `（0/1）` 等价
> - 全局代码编号任意位都行，不固定位数
> - `#：【文件名/文件夹路径】`：用于输入文件名称/文件夹路径，按路径查找引用
> - `#：【文件】` 放在每段 `{}` 尾行，代表当前文件里的这部分代码到此结束

> 已确认（M3.3 用户示例）：
> - 段循环后缀 `…N（x/y）` 后可跟 **`<subfile_ref>`**：子文件（下位文件），**补充/扩充**当前段，多个用 `|` 分隔
> - 全局循环后缀 `……（x/y）` 后可跟 **`<file_ref>`**：当前代码文件被**分割/分化**成多个文件使用
> - 两种路径引用**按位置区分**语义，取代原先笼统的 `<inline_path_ref>`（同行路径引用）
> - 完整末行形态：`#：[输出]…（x/y）【子文件|…】<全局编号>……（x/y）【文件/路径】`

### 2.7 字面量

```ebnf
<integer>    = <digit> , { <digit> } , [ <unit> ] ;    (* 整数可带单位：100米、50秒 *)
<float>      = <integer> , "." , { <digit> } , [ <unit> ] ;   (* 浮点数可带单位：262.5米 *)
<string>     = '"' , { <char> } , '"' ;               (* 转义规则草案 *)
<bool>       = "真" | "假" | "true" | "false" ;       (* 草案 *)
<digit>      = "0" | ... | "9" ;
```

---

## 3. 自然语言前端（[03](03-自然语言前端.md)）

```ebnf
<nl_block>      = <read_natural> ;
<natural_lang>  = { <nl_char> } ;
<nl_char>       = <letter> | <digit> | <punct> | <whitespace> ;
<nl_intent>     = <annotation> , ":" , <natural_lang> ;   (* 意图骨架，草案 *)
```

---

## 4. 数学核心（[04](04-数学核心（机械语言）.md)）

```ebnf
(* 机械单元：可无段号（模板）或带段号（可编辑） *)
<mech_unit>   = ( <generate> | <generate_seg> ) , ( <code_block> | <mech_stmt> | <mech_body> ) ;
<mech_body>   = { <mech_stmt> } ;

<mech_stmt>   = <binding> | <set_construct> | <iteration> | <output> | <output_trail>
              | <expr> | <set_up> | <set_up_seg>
              | <gen_stmt> | <gen_stmt_seg>
              | <file_marker> | <global_id_stmt> | <statement> ;

(* 通用生成语句（无段号 / 带段号）—— 可作用于命令/表达式/输出追踪 *)
<gen_stmt>      = <generate> , ( <command_literal> | <expr> | <output_trail> ) ;
<gen_stmt_seg>  = <generate_seg> , ( <command_literal> | <expr> | <output_trail> ) ;

(* 绑定：左侧可为 变量、标注变量、路径 形式 *)
<binding>        = ( <variable> | <path_expr> ) , [ <annotation> ] , "=" , <expr> ;
<path_expr>      = <variable> , ">>" , <variable> ;                              (* a>>b 路径/距离 *)
<set_construct>  = "{" , ( <var_list> , "|" , <cond_list> | <literal_list> ) , "}" ;
<var_list>       = <variable> | "(" , <variable> , { "," , <variable> } , ")" ;
<literal_list>   = <expr> , { ( "," | "，" ) , <expr> } ;                        (* 枚举集合 {1,2,3} *)
<cond_list>      = <expr> , { "|" , <expr> } ;
<iteration>      = ( <placeholder> , <variable> | <variable> ) , ">>" , <expr> , <block> ;
```

---

## 5. 类型系统（[05](05-类型系统.md)）

```ebnf
<type_expr>       = <basic_type> | <set_type> | <func_type> | <tuple_type> | <param_type> | <annotated_type> ;
<basic_type>      = "Int" | "Float" | "Bool" | "String" | "Unit" | "Angle" ;
<set_type>        = "Set" , "[" , <type_expr> , "]" ;
<func_type>       = <type_expr> , "->" , <type_expr> ;               (* 右结合 *)
<tuple_type>      = "(" , <type_expr> , { "," , <type_expr> } , ")" ;
<param_type>      = <identifier> , "[" , <type_expr> , { "," , <type_expr> } , "]" ;
<annotated_type>  = <type_expr> , <annotation> ;
```

---

## 6. 表达式与运算符（[06](06-表达式与运算符.md)）

```ebnf
<expr>       = <rel_expr> ;
<rel_expr>   = <add_expr> , [ <rel_op> , <add_expr> ] ;
<add_expr>   = <mul_expr> , { ("+" | "-") , <mul_expr> } ;
<mul_expr>   = <pow_expr> , { ("*" | "/") , <pow_expr> } ;
<pow_expr>   = <unary> , [ "^" , <pow_expr> ] ;                      (* 中缀次方，右结合 *)
<unary>      = [ "-" | "^" ] , <postfix> ;                           (* - 一元负 / ^ 前缀开方 *)
<postfix>    = <primary> , { <primary> } ;                           (* 函数应用，左结合 *)
<primary>    = <integer> | <float> | <string> | <bool> | <variable>
             | <angle_expr> | <path_expr> | <set_construct> | <read_block>
             | <output> | <set_up> | <lambda> | <code_block> | "(" , <expr> , ")" ;
<angle_expr> = "<<" , <expr> ;                                       (* 角度前缀 *)
<belongs>    = <expr> , ">>" , <expr> ;                              (* 属于判断（表达式语境） *)
<lambda>     = "(" , <params> , ")" , "=>" , <expr> ;
<params>     = <param> , { "," , <param> } ;
<param>      = <variable> , [ <annotation> ] ;

<set_op>     = "∪" | "∩" | "\" | "~" | "×" | "⊆" ;                   (* 草案：Unicode 集合运算 *)
```

> `>>` 三语义由位置消解：
> - 出现在 `<iteration>` 循环头 + 后接 `<block>` → **步进迭代**
> - 出现在表达式内部（`<belongs>`）→ **属于判断**
> - 出现在 `<binding>` / `<set_up_item>` 左侧（`<path_expr>`）→ **路径/距离**

---

## 7. 语句与控制流（[07](07-语句与控制流.md)）

```ebnf
<statement>  = <binding> | <if_stmt> | <loop_stmt> | <match_stmt> | <output> | <output_trail>
             | <set_up> | <set_up_seg> | <gen_stmt> | <gen_stmt_seg>
             | <file_marker> | <global_id_stmt> | <expr> ;

<if_expr>    = <expr> , "?" , <expr> , ":" , <expr> ;                 (* 三元 *)
<if_stmt>    = <expr> , <block> , [ "否则" , ( <expr> , <block> | <block> ) ] ;   (* 草案 *)

<loop_step>  = ( <placeholder> , <variable> | <variable> ) , ">>" , <expr> , <block> ;  (* 步进循环（？x>>S） *)
<loop_while> = <expr> , "?" , <block> ;                              (* 条件循环，草案 *)

<match_stmt> = "match" , <expr> , { "|" , <pattern> , "=>" , <expr> } ;
<pattern>    = <literal> | <variable> | <constructor> | "_" | <belongs_pat> ;
<belongs_pat> = <variable> , ">>" , <expr> ;

<block>      = <indent_block> | <code_block> ;                         (* 两种等价形式 *)
<indent_block> = <newline> , <indent> , { <mech_stmt> } ;              (* 缩进块 *)
```

---

## 8. 函数（[08](08-函数与抽象.md)）

```ebnf
<func_def>   = <identifier> , [ <annotation> ] , ":" , <func_type> , "=" , <lambda> ;
<func_short> = <identifier> , "(" , <params> , ")" , [ ":" , <type_expr> ] , "=" , <expr> ;   (* 草案简写 *)
```

---

## 9. 类型定义（[09](09-用户自定义类型.md)）

```ebnf
<type_def>   = <struct_def> | <enum_def> | <alias_def> ;

<struct_def> = "struct" , <identifier> , [ <type_params> ] , [ <annotation> ] , "=" , "{" , <fields> , "}" ;
<enum_def>   = "enum" , <identifier> , [ <type_params> ] , [ <annotation> ] , "=" , "{" , <ctors> , "}" ;
<alias_def>  = "type" , <identifier> , [ <type_params> ] , "=" , <type_expr> ;

<type_params> = "[" , <typevar> , { "," , <typevar> } , "]" ;
<fields>      = <field> , { "|" , <field> } ;
<field>       = <identifier> , ":" , <type_expr> , [ <annotation> ] ;
<ctors>       = <ctor> , { "|" , <ctor> } ;
<ctor>        = <identifier> , [ <type_expr> ] ;
<constructor> = <identifier> , { <expr> } ;
```

---

## 10. 模块系统（[10](10-模块系统.md)）

```ebnf
<module_decl> = "module" , <module_name> , [ <annotation> ] , "=" , "{" , { <decl> } , "}" ;
<import_decl> = "use" , <module_name> , [ "{" , <import_list> , "}" ] , [ "as" , <identifier> ] ;
<module_name> = <identifier> , { "." , <identifier> } ;
<import_list> = <identifier> , { "|" , <identifier> } ;
```

---

## 11. 并发（[11](11-并发模型.md)）

```ebnf
<go_stmt>      = "go" , <expr> ;
<chan_expr>    = "chan" , <type_expr> , [ "," , <integer> ] ;
<send_expr>    = <expr> , "<-" , <expr> ;                       (* ch <- v *)
<recv_expr>    = "<-" , <expr> ;                                (* <- ch *)
<select_stmt>  = "select" , { "|" , <select_branch> } ;
<select_branch> = ( <send_expr> | <recv_expr> ) , "=>" , <expr> ;
```

---

## 12. 可读输出层（[13](13-可读输出层.md)）

```ebnf
<command_unit> = <gen_command> | <command_literal> | <output> ;
<cmd_display>  = <output> , <command_literal> ;                 (* 展示命令，草案 *)
```

---

## 13. 错误处理（[12](12-错误处理.md)）

```ebnf
<error_type>  = "Result" , "[" , <type_expr> , "," , <type_expr> , "]"
              | "Option" , "[" , <type_expr> , "]" ;
<propagate>   = <expr> , "?" ;                                  (* 错误传播，草案 *)
```

---

## 14. 保留关键字（草案）

```
struct  enum  type  match  module  use  as  go  chan  select  否则
```

> Matha 以符号体系为主，保留关键字极少。最终表见 [19-附录](19-附录.md)。

---

## 15. 待确认项汇总

| 项 | 涉及章节 | 状态 |
|----|---------|------|
| 集合运算符号（Unicode vs ASCII） | 06 | 待确认 |
| 条件循环 / 提前退出语法 | 07 | 待确认 |
| 模式匹配是否用 `match` 关键字 | 07/09 | 待确认 |
| 函数简写形式 | 08 | 待确认 |
| 字段访问 `.` vs `<<` | 09 | 待确认 |
| 缓冲 channel 语法 | 11 | 待确认 |
| `?` 错误传播操作符 | 12 | 待确认 |
| 命令展示格式 | 13 | 待确认 |
| 注释语法 | 02 | 待确认 |
| ~~`<=`/`>=` 形式~~ | 02/06 | **已确认** |
| ~~`^` 次方/开方双语义~~ | 02/04/06 | **已确认** |
| ~~`@` 设定符号 + 双形式~~ | 02/04/06/17 | **已确认** |
| ~~标注公式扩展 `*/文字*公式/*`~~ | 02/05 | **已确认** |
| ~~`>>` 三语义（步进/属于/路径距离）~~ | 02/04/06/07/17 | **已确认** |
| ~~单位为字符串（不做量纲换算）~~ | 02/04/06/17 | **已确认** |
| ~~`{ }` 代码块（串代码整体）~~ | 04/07/17 | **已确认** |
| ~~中文逗号 `，` 与英文逗号 `,` 等价分格~~ | 02/06/17 | **已确认** |
| ~~段序号从 1 起排列 + 任意位整数~~ | 02/04/07/17 | **已确认** |
| ~~省略号硬性区分单 `…`(段级) / 双 `……`(全局)~~ | 02/04/06/07/17 | **已确认** |
| ~~循环分数 `(x/y)` / `（x/y）` 半全角括号等价~~ | 02/04/06/07/17 | **已确认** |
| ~~全局代码编号任意位都行（不固定位数）~~ | 02/04/06/17 | **已确认** |
| ~~`#：【文件】` 结束标记 / `#：【路径】` 引用文件/文件夹~~ | 02/04/07/17 | **已确认** |
| ~~`#N:`/`@N:` 半/全角冒号都允许~~ | 02/04/07/17 | **已确认** |
| ~~M3.1 段内顺序 命令→变量→？公式→字母公式→输出（固定）~~ | 04/07/17 | **已确认** |
| ~~M3.1 【命令】与《命令》两种写法共存~~ | 02/04/07/17 | **已确认** |
| ~~M3.1 >> 通用链式（命令/输出/任意语句）~~ | 02/04/07/17 | **已确认** |
| ~~M3.1 命令换行分格，公式/变量逗号分格~~ | 07/17 | **已确认** |
| ~~M3.1 ？公式=简化抽象；字母公式=精确化~~ | 04/07/17 | **已确认** |
| ~~M3.1 公式跨段共享与调用~~ | 04/07 | **已确认** |
| ~~M3.1 输出追踪路径引用可同行或分行~~ | 04/07/17 | **已确认** |
| ~~M3.1 命令/输出可读取 URL/文件/文件夹/端口~~ | 07 | **已确认** |
| ~~M3.1 段内各步可按需省略~~ | 07 | **已确认** |
| ~~M3.2 命令/输出各自独立拥有读取能力（无需 >> 链式）~~ | 04/07/17 | **已确认** |
| ~~M3.2 `>>` 链式触发条件=单条命令/单条输出无法满足需求时才启用~~ | 04/07/17 | **已确认** |
| ~~M3.2 段内允许多条命令/变量/公式并存，并可按需被其他段调用~~ | 04/07 | **已确认** |
| ~~M3.2 段内 5 步推荐分行书写：主输出行与循环/路径独立~~ | 04/07/17 | **已确认** |

---

## 16. 解析器验证

本 EBNF 应能被标准解析器（如 Python `lark`）解析。实现阶段需验证：
- 所有终结符无歧义（最长匹配规则）。
- `<<`/`>>`/`<=`/`>=` 的词法优先级。
- **`^` 的位置消解**：parser 依据前一个 Token 判定 `^` 为中缀次方（前有操作数）或前缀开方（前无操作数）。
- `【】`/`〔〕` 配对一致性。
- `#：` 的双字符识别（`#` + `：`，全角冒号）。
- **`@` 设定双形式**：`@(...)`（`|` 分格）与 `@:xxx，yyy`（`，/ ,` 分格）均合法。
- **`>>` 三语义消解**：
  - 循环语境（后跟 `<block>`）→ 步进迭代；
  - 表达式内部 `<belongs>` → 属于判断；
  - 绑定/设定左侧 `<path_expr>` → 路径/距离。
- **标注公式 `*/文字*公式/*`**：`*/` 起始后，识别标注文字，若遇 `*` 则后续至 `/*` 为公式表达式，需递归解析 `<expr>`。
- **`{ }` 代码块 vs 集合构造消解**：
  - `{` 后紧跟 `变量 |` → 集合构造（理解形式）；
  - `{` 后紧跟 `值,值,值` → 集合构造（枚举形式）；
  - 其余外层语境（尤其 `#：{` 后）→ 代码块。
- **整数/浮点数 + 单位**：字面量后续紧邻 CJK 字符时合并为带单位字面量；若出现单位字符串但非紧邻时独立处理。
- **`？` 占位符**：在绑定、参数、循环变量位置可与字母结合（如 `？x >> S`），在表达式中作为通用占位。
- **段号冒号最长匹配**：`#`/`@` 后遇到数字优先归为 `#N`/`@N`，再匹配其后的 `:`/`：`；若 `#` 后无数字、直接跟 `：` 则归为无段号 `#：`。
- **省略号硬性区分**：`……`(两个字符 U+2026U+2026) 优先级高于 `…`(单个)，词法层最长匹配。凡省略号位置不匹配数量应报错，不做容错降级。
- **分数括号半/全角归一**：词法阶段将 `（x/y）` 归一为 `(x/y)` 内部表示；但分隔分数线 `/` 必须保留在分数内，避免与除法 `/` 混淆——只有位于配对括号 `(…/…)` 内的 `/` 才归为循环分数。
- **输出追踪后缀顺序**：必须为 `[输出] … [段号] (x/y) [全局编号] ……(x/y)`；中间项可缺但顺序不能乱（段循环 → 全局编号 → 全局循环）。
- **全局 ID 语句 vs 字面量区分**：纯数字行若位于跨文件首行且后续紧接 `#N：{` 语境 → 归为 `<global_id_stmt>` 绑定标识；否则归为 `<integer>` 字面量。
- **`#：【路径】` vs `#：【文件】` 内容消解**：路径内容若仅为字符串字面「文件」两字 → 视为 `<file_marker>` 结束；若包含 `/`、`\\`、`.`、盘符或其他文件名特征 → 视为跨文件路径查找引用。路径内容支持纯文件名、相对路径与绝对路径。
- **`>>` 四重语义消解（M3.1 新增链式）**：`>>` 为通用符号，按位置消解为四种语义：
  - 链式语境（M3.1）：`>>` 两侧均为语句（`【】>>【】`、`[]>>[]`、`@:>>@:` 等）且不在循环头/绑定左侧/表达式内部 → `<chain_stmt>`
  - 循环语境：`？x >> S` 后跟缩进块 → `<loop_step>` 步进迭代
  - 表达式语境：`x >> S` 在表达式内部 → `<belongs>` 属于判断
  - 绑定语境：`a>>b=...` 在赋值左侧 → `<path_expr>` 路径/距离
- **`【命令】` vs `《命令》` 共存**：两种命令写法完全等价，parser 按最长匹配优先匹配；`【】` 在命令语境中与在读取语境中通过位置消解（`#N：【...】` 优先归为命令，`【...】` 独立行优先归为读取）。
- **资源字面量识别（M3.2 新增一等能力）**：命令 `【…】` 与输出 `[…]` 内容若包含 URL 特征（`://`）、盘符（如 `d:\`）、文件夹分隔（`/`、`\`）、端口特征（`host:port`）等 → 在语义层直接识别为"读取资源"，无需依赖 `>>` 链式。语法层复用 `<bracket_command_literal>` / `<output>`，不新增产生式。
- **`>>` 链式触发条件（M3.2 收紧）**：仅当**单条命令或单条输出不足以完成任务**时，`>>` 才归为 `<chain_stmt>`；否则优先用命令/输出的独立读取能力。位置消解规则不变，仅提升"单条优先"的优先级。
- **命令换行 vs 公式/变量逗号分格**：段内多命令通过换行分格；段内多公式/变量通过逗号分格。parser 通过段内步骤编号（命令=步骤①、公式=步骤③/④、变量=步骤②）自动判断分隔方式。
