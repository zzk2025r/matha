# -*- coding: utf-8 -*-
"""新旧 Matha 模板互转工具

旧模板特征：#N：{ ... } 有段号，多段分散
新模板特征：#：{ ... } 无段号，整合为一代码块

转换规则：
  旧 → 新：
    1. 去掉段号 #N： → #：
    2. 合并多个段为一个代码块
    3. 命令段用 >> 链式连接
    4. 可选添加 【*/说明/*】 和 @：【内容】
  新 → 旧：
    1. 添加段号 #：→ #1：, #2：, ...
    2. 拆分代码块为多个段
    3. 去掉 【*/说明/*】 和 @：【内容】（可选）
"""
import re
from typing import Tuple


def old_to_new(src: str, title: str = "", code_id: str = "") -> str:
    """旧模板 → 新模板

    将 #N：{ ... } 形式的多段代码合并为 #：{ ... } 单代码块。
    段号被去除，语句被整合，输出行保留 …（x/y）【子文件】 后缀。
    code_id：可选代码编号前缀（如 "？" 或 "1"），放在 #： 之前。
    """
    lines = src.strip().split("\n")
    out_lines = []
    in_block = False
    block_lines = []
    outputs = []
    suffixes = []

    for ln in lines:
        stripped = ln.strip()
        # 跳过 #：【文件】 结束标记
        if stripped == "#：【文件】":
            continue
        # 匹配 #N：{ 代码块开始
        m = re.match(r'#\d+：\{', stripped)
        if m:
            in_block = True
            continue
        # 匹配 #N：[输出] 行（带后缀）
        m2 = re.match(r'#\d+：\[(.+?)\](.*)', stripped)
        if m2 and not in_block:
            outputs.append(m2.group(1))
            if m2.group(2):
                suffixes.append(m2.group(2))
            continue
        # 代码块结束
        if stripped == "}" and in_block:
            in_block = False
            continue
        # 代码块内的语句
        if in_block and stripped:
            block_lines.append(stripped)

    # 组装新模板（可选代码编号前缀）
    prefix = code_id if code_id else ""
    result = f"{prefix}#：{{\n"
    if title:
        result += f"  【*/{title}/*】\n"
    # 合并语句
    for bl in block_lines:
        result += f"  {bl}\n"
    # 输出行
    for i, out in enumerate(outputs):
        suf = suffixes[i] if i < len(suffixes) else ""
        # 将 …N（ 改为 …（ （去段号）
        suf = re.sub(r'…\d+（', '…（', suf)
        result += f"  #：[{out}]{suf}\n"
    result += "}\n"
    if not title:
        result += "#：【文件】\n"
    return result


def new_to_old(src: str) -> str:
    """新模板 → 旧模板

    将 [？|N]#：{ ... } 单代码块拆分为 #：{ } #2：{ } ... 多段代码。
    绑定语句和其后的输出行放在同一段中（保持变量作用域）。
    段号自动递增，@：和【*/.../*】被去除。
    代码编号前缀（？/N）被去除（旧模板无此概念）。
    """
    lines = src.strip().split("\n")
    seg_num = 0
    segments = []  # [(seg_num, [stmts])]
    current_stmts = []
    in_block = False

    for ln in lines:
        stripped = ln.strip()
        if stripped == "#：【文件】":
            continue
        # 处理 [？|N]#：{ 前缀（去除代码编号）
        m_code = re.match(r'^(？|\d+)?#：\{', stripped)
        if m_code:
            in_block = True
            continue
        if stripped == "}" and in_block:
            in_block = False
            if current_stmts:
                seg_num += 1
                segments.append((seg_num, current_stmts[:]))
                current_stmts = []
            continue
        if not in_block or not stripped:
            continue
        # 跳过 【*/.../*】 说明
        if stripped.startswith("【*/") and stripped.endswith("/*】"):
            continue
        # 跳过 @：【内容】 命令式设定（保留 @：变量=值）
        if stripped.startswith("@：【") and "=" not in stripped.split("】")[0]:
            # 提取 】 后面的 ，变量=值 部分
            after = stripped.split("】", 1)
            if len(after) > 1 and after[1].strip():
                # 保留 @：变量=值 部分
                current_stmts.append("@" + after[1].strip().lstrip("，"))
            continue
        # 跳过 #：【命令】 链式行
        if stripped.startswith("#：【"):
            continue
        # #：[输出] 行 → 加入当前段（不单独分段）
        m = re.match(r'#：\[(.+?)\](.*)', stripped)
        if m:
            current_stmts.append(f"[{m.group(1)}]{m.group(2)}")
            continue
        # 普通语句
        current_stmts.append(stripped)

    if current_stmts:
        seg_num += 1
        segments.append((seg_num, current_stmts[:]))

    result = ""
    for num, stmts in segments:
        result += f"#{num}：{{\n"
        for s in stmts:
            result += f"  {s}\n"
        result += "}\n"
    result += "#：【文件】\n"
    return result


def convert(src: str, direction: str = "auto") -> Tuple[str, str]:
    """自动检测并转换模板格式

    direction: "auto" | "old_to_new" | "new_to_old"
    返回: (转换结果, 实际使用的方向)
    """
    if direction == "auto":
        # 检测：有 #N： → 旧模板；有 #： 但无 #N： → 新模板
        has_old = bool(re.search(r'#\d+：', src))
        has_new = bool(re.search(r'#：[{\[]', src)) and not has_old
        if has_old:
            direction = "old_to_new"
        elif has_new:
            direction = "new_to_old"
        else:
            return src, "no_change"

    if direction == "old_to_new":
        return old_to_new(src), "old_to_new"
    elif direction == "new_to_old":
        return new_to_old(src), "new_to_old"
    return src, "no_change"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python template_convert.py <file.matha> [direction]")
        print("direction: auto(默认) | old_to_new | new_to_old")
        sys.exit(1)

    fname = sys.argv[1]
    direction = sys.argv[2] if len(sys.argv) > 2 else "auto"
    src = open(fname, encoding="utf-8").read()
    result, used = convert(src, direction)
    print(f"转换方向: {used}")
    print(result)
