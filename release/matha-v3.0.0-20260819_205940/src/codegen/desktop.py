# -*- coding: utf-8 -*-
"""DesktopGenerator：把 Matha 规格编译为 Python Tkinter 桌面应用成品。

输出文件：
  - main.py  可直接 `python main.py` 运行的桌面程序

支持的控件（16 种）：
  label/h1/h2/h3/p  → Label
  input             → Entry（单行输入）
  textarea/text     → Text（多行文本框）
  button            → Button
  checkbox          → Checkbutton（复选框）
  radio             → Radiobutton（单选框）
  select            → ttk.Combobox（下拉选择）
  list              → Listbox（列表框）
  slider            → Scale（滑块）
  canvas            → Canvas（画布）
  image             → Label + PhotoImage（图片）
  separator         → ttk.Separator（分隔线）
  frame/div         → Frame（容器）
  group             → LabelFrame（分组容器）
  table             → ttk.Treeview（表格）
  tab               → ttk.Notebook（标签页容器）

布局方式（通过属性指定）：
  默认：pack（垂直堆叠）
  grid：设置 row/col 属性 → grid(row=, column=)
  place：设置 x/y 属性 → place(x=, y=)

窗口属性（通过规格额外字段）：
  尺寸 = "400x300"
  背景 = "#f0f0f0"
  可调整 = "否"

事件处理：
  onclick 属性指定处理函数名，生成器自动绑定。
  处理函数可引用 self.控件名 取值/设值。
  支持弹窗：messagebox/filedialog/simpledialog/colorchooser。
"""

from __future__ import annotations
from src.codegen.base import Generator, CodegenResult, Element


class DesktopGenerator(Generator):
    """桌面应用生成器：AppSpec → Python Tkinter 脚本。"""

    def generate(self) -> CodegenResult:
        try:
            py = self._build_python()
            path = self._write("main.py", py)
        except Exception as e:
            return CodegenResult(成功=False, 类型="桌面", 名称=self.app.name,
                                 错误=str(e))
        return CodegenResult(
            成功=True, 类型="桌面", 名称=self.app.name,
            文件=[path], 入口=path,
        )

    def _build_python(self) -> str:
        """构建 Python Tkinter 脚本。"""
        title = self.app.title or self.app.name
        cls = self._class_name()

        # 窗口属性
        geometry = self.app.meta.get("尺寸", "")
        bg_color = self.app.meta.get("背景", "")
        resizable = self.app.meta.get("可调整", "是")

        # 生成控件代码和处理函数
        widget_lines: list[str] = []
        handler_defs: list[str] = []
        seen_handlers: set[str] = set()
        var_decls: list[str] = []

        for i, el in enumerate(self.app.elements):
            var_name = f"self.w{i}"
            code, handlers, vars = self._widget_code(el, i, var_name)
            widget_lines.append(code)
            for h in handlers:
                if h not in seen_handlers:
                    handler_defs.append(h)
                    seen_handlers.add(h)
            var_decls.extend(vars)

        # 布局代码
        layout_lines = self._build_layout()

        widgets_str = "\n        ".join(widget_lines) if widget_lines else "pass"
        layout_str = "\n        ".join(layout_lines) if layout_lines else "pass"
        handlers_str = "\n    ".join(handler_defs) if handler_defs else "pass"
        vars_str = "\n        ".join(var_decls) if var_decls else ""

        # 窗口设置
        win_setup = f'        root.title("{self._escape_py(title)}")\n'
        if geometry:
            win_setup += f'        root.geometry("{geometry}")\n'
        if bg_color:
            win_setup += f'        root.configure(bg="{bg_color}")\n'
        if resizable == "否":
            win_setup += '        root.resizable(False, False)\n'

        result = (
            "# -*- coding: utf-8 -*-\n"
            f"# 由 Matha codegen 生成：{title}\n"
            "# 运行：python main.py\n"
            "import tkinter as tk\n"
            "from tkinter import ttk, messagebox, filedialog, simpledialog, colorchooser\n"
            "from tkinter.scrolledtext import ScrolledText\n"
            "import os\n\n\n"
            f"class {cls}App:\n"
            f'    """{self._escape_py(title)} — Matha 生成的桌面应用。"""\n\n'
            "    def __init__(self, root):\n"
            "        self.root = root\n"
            f"{win_setup}"
        )
        if vars_str:
            result += f"        {vars_str}\n"
        result += f"        {widgets_str}\n"
        result += f"        {layout_str}\n\n"
        result += f"    {handlers_str}\n\n\n"
        result += (
            "if __name__ == '__main__':\n"
            "    root = tk.Tk()\n"
            f"    {cls}App(root)\n"
            "    root.mainloop()\n"
        )
        return result

    def _widget_code(self, el: Element, idx: int, var_name: str) -> tuple[str, list[str], list[str]]:
        """生成单个控件的 Python 代码。

        Returns:
            (控件创建代码, 处理函数定义列表, 变量声明列表)
        """
        tag = el.tag.lower()
        text = self._escape_py(el.text)
        attrs = self._attrs_dict(el)
        handlers: list[str] = []
        var_decls: list[str] = []

        # 标签类
        if tag in ("h1", "h2", "h3", "p", "label", "span"):
            size = 18 if tag == "h1" else (14 if tag == "h2" else 12)
            bold = "bold" if tag in ("h1", "h2") else "normal"
            return (f'{var_name} = tk.Label(root, text="{text}", font=("", {size}, "{bold}"))',
                    handlers, var_decls)

        # 单行输入
        if tag == "input":
            width = attrs.get("width", "20")
            code = f'{var_name} = tk.Entry(root, width={width})'
            if text:
                code += f'\n        {var_name}.insert(0, "{text}")'
            return (code, handlers, var_decls)

        # 多行文本框
        if tag in ("textarea", "text"):
            width = attrs.get("width", "40")
            height = attrs.get("height", "10")
            code = f'{var_name} = ScrolledText(root, width={width}, height={height})'
            if text:
                code += f'\n        {var_name}.insert("1.0", "{text}")'
            return (code, handlers, var_decls)

        # 按钮
        if tag == "button":
            onclick = attrs.get("onclick", "")
            cmd = "None"
            if onclick:
                handler_name = self._extract_handler(onclick)
                if handler_name:
                    handlers.append(
                        f'def {handler_name}(self):\n'
                        f'            """按钮 {text} 的点击事件。"""\n'
                        f'            pass  # 用户可在此实现具体逻辑'
                    )
                    cmd = f"self.{handler_name}"
            return (f'{var_name} = tk.Button(root, text="{text}", command={cmd})',
                    handlers, var_decls)

        # 复选框
        if tag == "checkbox":
            var_decl = f'{var_name}_var = tk.IntVar()'
            var_decls.append(var_decl)
            checked = "1" if attrs.get("checked") == "true" else "0"
            return (f'{var_name}_var.set({checked})\n'
                    f'        {var_name} = tk.Checkbutton(root, text="{text}", variable={var_name}_var)',
                    handlers, var_decls)

        # 单选框
        if tag == "radio":
            group = attrs.get("group", "radio_group")
            value = attrs.get("value", text)
            var_decl = f'self.{group}_var = tk.StringVar()'
            if var_decl not in var_decls:
                var_decls.append(var_decl)
            return (f'{var_name} = tk.Radiobutton(root, text="{text}", '
                    f'variable=self.{group}_var, value="{value}")',
                    handlers, var_decls)

        # 下拉选择
        if tag in ("select", "combobox"):
            options = attrs.get("options", "")
            opts_list = options.split("|") if options else []
            var_decl = f'{var_name}_var = tk.StringVar()'
            var_decls.append(var_decl)
            opts_str = ", ".join(f'"{self._escape_py(o)}"' for o in opts_list)
            return (f'{var_name} = ttk.Combobox(root, textvariable={var_name}_var, '
                    f'values=[{opts_str}], state="readonly")\n'
                    f'        {var_name}.set("{self._escape_py(opts_list[0]) if opts_list else ""}")',
                    handlers, var_decls)

        # 列表框
        if tag in ("list", "listbox"):
            code = f'{var_name} = tk.Listbox(root, height={attrs.get("height", "6")})'
            # 添加选项（从子元素或 text 属性）
            items = text.split("|") if text else []
            for item in items:
                code += f'\n        {var_name}.insert(tk.END, "{self._escape_py(item)}")'
            return (code, handlers, var_decls)

        # 滑块
        if tag in ("slider", "scale"):
            frm = attrs.get("min", "0")
            to = attrs.get("max", "100")
            orient = "tk.HORIZONTAL" if attrs.get("orient", "horizontal") == "horizontal" else "tk.VERTICAL"
            return (f'{var_name} = tk.Scale(root, from_={frm}, to={to}, '
                    f'orient={orient})',
                    handlers, var_decls)

        # 画布
        if tag == "canvas":
            width = attrs.get("width", "300")
            height = attrs.get("height", "200")
            bg = attrs.get("bg", "white")
            return (f'{var_name} = tk.Canvas(root, width={width}, height={height}, bg="{bg}")',
                    handlers, var_decls)

        # 图片
        if tag == "image":
            src = attrs.get("src", "")
            return (f'{var_name}_img = tk.PhotoImage(file="{src}")\n'
                    f'        {var_name} = tk.Label(root, image={var_name}_img)\n'
                    f'        root.image = {var_name}_img  # 防止被回收',
                    handlers, var_decls)

        # 分隔线
        if tag == "separator":
            orient = "tk.HORIZONTAL" if attrs.get("orient", "horizontal") == "horizontal" else "tk.VERTICAL"
            return (f'{var_name} = ttk.Separator(root, orient={orient})',
                    handlers, var_decls)

        # 容器
        if tag in ("frame", "div"):
            code = f'{var_name} = tk.Frame(root)'
            if text:
                code = f'{var_name} = tk.LabelFrame(root, text="{text}")'
            # 子元素
            child_codes = []
            for j, child in enumerate(el.children):
                child_var = f"{var_name}_c{j}"
                ccode, chandlers, cvars = self._widget_code(child, j, child_var)
                child_codes.append(ccode)
                handlers.extend(chandlers)
                var_decls.extend(cvars)
            for cc in child_codes:
                code += f'\n        {cc}\n        {cc.split(" = ")[0]}.pack(padx=4, pady=2)'
            return (code, handlers, var_decls)

        # 表格
        if tag in ("table", "treeview"):
            columns = attrs.get("columns", "列1|列2|列3").split("|")
            cols_str = ", ".join(f'"{self._escape_py(c)}"' for c in columns)
            code = (f'{var_name} = ttk.Treeview(root, columns=[{cols_str}], show="headings")\n')
            for c in columns:
                code += f'        {var_name}.heading("{self._escape_py(c)}", text="{self._escape_py(c)}")\n'
                code += f'        {var_name}.column("{self._escape_py(c)}", width=80)\n'
            # 数据行（从子元素）
            for child in el.children:
                row_vals = child.text.split("|") if child.text else []
                vals_str = ", ".join(f'"{self._escape_py(v)}"' for v in row_vals)
                code += f'        {var_name}.insert("", tk.END, values=[{vals_str}])\n'
            code = code.rstrip("\n")
            return (code, handlers, var_decls)

        # 标签页容器
        if tag in ("tab", "notebook"):
            code = f'{var_name} = ttk.Notebook(root)'
            for j, child in enumerate(el.children):
                tab_title = child.attrs[0][1] if child.attrs and len(child.attrs[0]) == 2 else f"标签{j+1}"
                child_var = f"{var_name}_t{j}"
                ccode, chandlers, cvars = self._widget_code(child, j, child_var)
                # Normalize indentation of multi-line code
                indented = "\n".join(f"        {l.strip()}" for l in ccode.splitlines() if l.strip())
                code += f'\n{indented}'
                code += f'\n        {child_var}_frame = tk.Frame({var_name})\n'
                code += f'        {child_var}_frame.pack(fill="both", expand=True)\n'
                code += f'        {var_name}.add({child_var}_frame, text="{self._escape_py(tab_title)}")'
            return (code, handlers, var_decls)

        # 默认：Label
        return (f'{var_name} = tk.Label(root, text="{text}")', handlers, var_decls)

    def _build_layout(self) -> list[str]:
        """生成布局代码（pack/grid/place）。"""
        lines = []
        for i, el in enumerate(self.app.elements):
            var_name = f"self.w{i}"
            attrs = self._attrs_dict(el)
            # grid 布局
            if "row" in attrs or "col" in attrs:
                row = attrs.get("row", "0")
                col = attrs.get("col", "0")
                rowspan = attrs.get("rowspan", "1")
                columnspan = attrs.get("columnspan", "1")
                lines.append(f'{var_name}.grid(row={row}, column={col}, '
                             f'rowspan={rowspan}, columnspan={columnspan}, padx=4, pady=4)')
            # place 布局
            elif "x" in attrs or "y" in attrs:
                x = attrs.get("x", "0")
                y = attrs.get("y", "0")
                w = attrs.get("width", "")
                h = attrs.get("height", "")
                place_args = f'x={x}, y={y}'
                if w:
                    place_args += f', width={w}'
                if h:
                    place_args += f', height={h}'
                lines.append(f'{var_name}.place({place_args})')
            # 默认 pack
            else:
                fill = attrs.get("fill", "x")
                lines.append(f'{var_name}.pack(padx=4, pady=4, fill="{fill}")')
        return lines

    def _attrs_dict(self, el: Element) -> dict[str, str]:
        return {k: v for k, v in el.attrs}

    @staticmethod
    def _extract_handler(onclick: str) -> str:
        """从 onclick="foo()" 或 onclick="foo" 提取函数名 foo。"""
        s = onclick.strip()
        if "(" in s:
            name = s.split("(", 1)[0].strip().replace("self.", "")
            return name if name else "handler"
        # 无括号形式：onclick="save" → handler 名即为 "save"
        return s if s else "handler"

    def _class_name(self) -> str:
        """把应用名转为合法 Python 类名前缀。"""
        name = self.app.name
        result = ""
        for ch in name:
            if ch.isalnum():
                result += ch
            elif ch in ("_", "-"):
                result += "_"
        return result or "App"

    @staticmethod
    def _escape_py(text: str) -> str:
        """Python 字符串转义。"""
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
