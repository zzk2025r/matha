# -*- coding: utf-8 -*-
"""Matha 文档生成器

从 Matha 源代码自动提取文档信息，生成 API 参考文档。

支持格式：
  - Markdown
  - HTML
  - JSON（用于静态站点生成器）

使用方式：
  from src.tools.doc_generator import MathaDocGenerator
  generator = MathaDocGenerator(['src/stdlib'])
  generator.generate_markdown('docs/api.md')
"""
from __future__ import annotations
import inspect
import os
import sys
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FunctionDoc:
    """函数文档信息"""
    name: str
    module: str
    description: str
    parameters: List[Dict[str, str]]
    returns: Optional[str]
    examples: List[str]
    source_file: str
    source_line: int


@dataclass
class ClassDoc:
    """类文档信息"""
    name: str
    module: str
    description: str
    attributes: List[Dict[str, str]]
    methods: List[FunctionDoc]
    source_file: str
    source_line: int


@dataclass
class ModuleDoc:
    """模块文档信息"""
    name: str
    file_path: str
    description: str
    classes: List[ClassDoc]
    functions: List[FunctionDoc]
    submodules: List[str]


class MathaDocGenerator:
    """
    Matha 文档生成器

    从源代码提取文档信息，支持多种输出格式。
    """

    # 已知的文档块标记
    DOC_MARKERS = {
        'examples': [],
        '数学表达': [],
        '用法': [],
        '参数': [],
        '返回': [],
        '注意': [],
        '示例': [],
    }

    def __init__(self, source_dirs: List[str], exclude_patterns: Optional[List[str]] = None):
        """
        初始化文档生成器

        Args:
            source_dirs: 源代码目录列表
            exclude_patterns: 排除的文件模式列表
        """
        self.source_dirs = [Path(d) for d in source_dirs]
        self.exclude_patterns = exclude_patterns or ['__pycache__', '.pyc', 'test_']
        self._modules: Dict[str, ModuleDoc] = {}

    def discover_modules(self) -> List[Path]:
        """
        发现所有 Python 模块文件

        Returns:
            模块文件路径列表
        """
        modules = []
        for src_dir in self.source_dirs:
            if not src_dir.exists():
                continue
            for py_file in src_dir.rglob('*.py'):
                # 排除测试文件
                if any(pat in str(py_file) for pat in self.exclude_patterns):
                    continue
                # 排除 __init__.py
                if py_file.name == '__init__.py':
                    continue
                modules.append(py_file)
        return sorted(modules)

    def extract_docstring(self, obj: Any) -> str:
        """
        提取对象的 docstring

        Args:
            obj: 对象（函数、类、模块）

        Returns:
            docstring 内容
        """
        doc = inspect.getdoc(obj) or ""
        return doc.strip()

    def parse_docstring(self, docstring: str) -> Dict[str, Any]:
        """
        解析 docstring，提取结构化信息

        Args:
            docstring: 原始 docstring

        Returns:
            解析后的字典
        """
        result = {
            'description': '',
            'parameters': [],
            'returns': None,
            'examples': [],
            'mathematical': [],
            'usage': [],
        }

        if not docstring:
            return result

        lines = docstring.split('\n')
        current_section = 'description'
        current_param = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 检测段落标记
            if stripped.startswith('Args:'):
                current_section = 'parameters'
                continue
            elif stripped.startswith('Returns:'):
                current_section = 'returns'
                continue
            elif stripped.startswith('Examples:') or stripped.startswith('用法：'):
                current_section = 'examples'
                continue
            elif stripped.startswith('数学表达：') or stripped.startswith('数学表达'):
                current_section = 'mathematical'
                continue
            elif stripped.startswith('注意：') or stripped.startswith('Note:'):
                current_section = 'notes'
                continue

            # 解析参数
            if current_section == 'parameters':
                param_match = re.match(r'(\w+)\s*[:\-]', stripped)
                if param_match:
                    current_param = param_match.group(1)
                    result['parameters'].append({
                        'name': current_param,
                        'description': stripped.split(':', 1)[1].strip() if ':' in stripped else ''
                    })
                elif current_param and stripped:
                    # 多行参数描述
                    for p in result['parameters']:
                        if p['name'] == current_param:
                            p['description'] += ' ' + stripped
                            break

            # 解析返回值
            elif current_section == 'returns':
                if result['returns'] is None:
                    result['returns'] = stripped
                else:
                    result['returns'] += ' ' + stripped

            # 解析示例
            elif current_section in ('examples', 'usage'):
                if stripped.startswith('>>>'):
                    result['examples'].append(stripped[3:].strip())
                elif stripped and not stripped.startswith('#') and not stripped.startswith('...'):
                    # 跳过 continuation lines
                    if result['examples'] and result['examples'][-1].startswith('>>>'):
                        result['examples'][-1] += '\n' + stripped
                    else:
                        result['examples'].append(stripped)

            # 解析数学表达式
            elif current_section == 'mathematical':
                if stripped and not stripped.startswith('#'):
                    result['mathematical'].append(stripped)

            # 描述部分
            else:
                if not result['description']:
                    result['description'] = stripped
                elif stripped and not stripped.startswith('#'):
                    result['description'] += ' ' + stripped

        return result

    def inspect_function(self, func) -> Optional[FunctionDoc]:
        """
        检查函数对象，提取文档信息

        Args:
            func: 函数对象

        Returns:
            FunctionDoc 对象
        """
        try:
            sig = inspect.signature(func)
            docstring = self.extract_docstring(func)
            parsed = self.parse_docstring(docstring)

            # 提取参数信息（增强版：支持复杂类型注解）
            parameters = []
            for name, param in sig.parameters.items():
                if name == 'self':
                    continue
                param_info = {'name': name}

                # 处理类型注解
                if param.annotation != inspect.Parameter.empty:
                    param_info['type'] = self._format_type_annotation(param.annotation)

                # 处理默认值
                if param.default != inspect.Parameter.empty:
                    param_info['default'] = str(param.default)

                # 处理参数位置
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    param_info['kind'] = 'positional_only'
                elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                    param_info['kind'] = '*args'
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    param_info['kind'] = '**kwargs'
                elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                    param_info['kind'] = 'keyword_only'
                else:
                    param_info['kind'] = 'positional_or_keyword'

                # 从 docstring 补充描述
                for p in parsed['parameters']:
                    if p['name'] == name:
                        param_info['description'] = p['description']
                        break
                parameters.append(param_info)

            # 提取返回值信息（增强版）
            returns = None
            if sig.return_annotation != inspect.Parameter.empty:
                returns = self._format_type_annotation(sig.return_annotation)
            if parsed['returns']:
                returns = parsed['returns']

            # 获取源文件信息
            try:
                source_file = inspect.getfile(func)
                source_line = inspect.getsourcelines(func)[1]
            except (OSError, TypeError):
                source_file = 'unknown'
                source_line = 0

            return FunctionDoc(
                name=func.__name__,
                module=func.__module__,
                description=parsed['description'],
                parameters=parameters,
                returns=returns,
                examples=parsed['examples'],
                source_file=source_file,
                source_line=source_line
            )
        except Exception as e:
            logger.warning(f"无法检查函数 {func}: {e}")
            return None

    def _format_type_annotation(self, annotation) -> str:
        """
        格式化类型注解

        支持：
        - 简单类型：int, str, float
        - 泛型类型：List[int], Dict[str, int]
        - 可选类型：Optional[int]
        - 联合类型：int | str
        - 复杂类型：Tuple[int, str], Callable[[int], str]
        """
        try:
            # 处理字符串注解
            if isinstance(annotation, str):
                return annotation

            # 处理 None
            if annotation is type(None):
                return 'None'

            # 处理 typing 模块类型
            origin = getattr(annotation, '__origin__', None)
            if origin is not None:
                # List, Dict, Tuple 等
                if hasattr(annotation, '__args__') and annotation.__args__:
                    args = ', '.join(self._format_type_annotation(a) for a in annotation.__args__)
                    return f'{origin.__name__}[{args}]' if hasattr(origin, '__name__') else str(annotation)
                return origin.__name__ if hasattr(origin, '__name__') else str(annotation)

            # 处理普通类型
            if hasattr(annotation, '__name__'):
                return annotation.__name__

            return str(annotation)
        except Exception:
            return str(annotation)

    def inspect_class(self, cls) -> Optional[ClassDoc]:
        """
        检查类对象，提取文档信息

        Args:
            cls: 类对象

        Returns:
            ClassDoc 对象
        """
        try:
            docstring = self.extract_docstring(cls)
            parsed = self.parse_docstring(docstring)

            # 提取属性
            attributes = []
            for name, value in vars(cls).items():
                if name.startswith('_') and name != '__init__':
                    continue
                if inspect.isfunction(value) or inspect.ismethod(value):
                    continue
                attr_info = {'name': name}
                if hasattr(value, '__annotations__'):
                    attr_info['type'] = str(value.__annotations__.get('type', ''))
                attributes.append(attr_info)

            # 提取方法
            methods = []
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if name.startswith('_'):
                    continue
                func_doc = self.inspect_function(method)
                if func_doc:
                    methods.append(func_doc)

            # 获取源文件信息
            try:
                source_file = inspect.getfile(cls)
                source_line = inspect.getsourcelines(cls)[1]
            except (OSError, TypeError):
                source_file = 'unknown'
                source_line = 0

            return ClassDoc(
                name=cls.__name__,
                module=cls.__module__,
                description=parsed['description'],
                attributes=attributes,
                methods=methods,
                source_file=source_file,
                source_line=source_line
            )
        except Exception as e:
            logger.warning(f"无法检查类 {cls}: {e}")
            return None

    def process_module(self, module_path: Path) -> Optional[ModuleDoc]:
        """
        处理单个模块文件

        Args:
            module_path: 模块文件路径

        Returns:
            ModuleDoc 对象
        """
        try:
            # 计算模块名 - 找到所有源目录中的相对路径
            rel_path = module_path
            for src_dir in self.source_dirs:
                try:
                    rel_path = module_path.relative_to(src_dir)
                    break
                except ValueError:
                    continue
            module_name = '.'.join(rel_path.with_suffix('').parts)

            # 读取文件内容
            content = module_path.read_text(encoding='utf-8')
            module_docstring = ''
            for line in content.split('\n'):
                if line.startswith('"""') or line.startswith("'''"):
                    if '"""' in line[3:]:
                        module_docstring = line[3:line.index('"""', 3)]
                        break
                    else:
                        # 多行 docstring
                        lines = []
                        for l in content.split('\n')[content.index(line):]:
                            lines.append(l)
                            if "'''\"" in l or '\"\"\"' in l:
                                break
                        module_docstring = '\n'.join(lines)
                        break

            # 动态导入模块
            sys.path.insert(0, str(module_path.parent))
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                sys.path.pop(0)

            # 提取类和函数
            classes = []
            functions = []
            submodules = []

            for name, obj in inspect.getmembers(module):
                if name.startswith('_'):
                    continue
                if inspect.isclass(obj):
                    class_doc = self.inspect_class(obj)
                    if class_doc:
                        classes.append(class_doc)
                elif inspect.isfunction(obj):
                    func_doc = self.inspect_function(obj)
                    if func_doc:
                        functions.append(func_doc)
                elif inspect.ismodule(obj):
                    submodules.append(name)

            return ModuleDoc(
                name=module_name,
                file_path=str(module_path),
                description=module_docstring.strip(),
                classes=classes,
                functions=functions,
                submodules=submodules
            )
        except Exception as e:
            logger.warning(f"无法处理模块 {module_path}: {e}")
            return None

    def generate(self) -> Dict[str, ModuleDoc]:
        """
        生成所有模块文档

        Returns:
            模块文档字典
        """
        modules = self.discover_modules()
        self._modules = {}

        for module_path in modules:
            module_doc = self.process_module(module_path)
            if module_doc:
                self._modules[module_doc.name] = module_doc

        return self._modules

    def generate_markdown(self, output_path: str) -> str:
        """
        生成 Markdown 格式文档

        Args:
            output_path: 输出文件路径

        Returns:
            生成的 Markdown 内容
        """
        if not self._modules:
            self.generate()

        lines = []
        lines.append('# Matha API 参考文档\n')
        lines.append('> 自动生成于 ' + __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        lines.append('> 版本: v4.4.1\n')
        lines.append('---\n')

        # 目录
        lines.append('## 目录\n')
        for name, module in sorted(self._modules.items()):
            lines.append(f'- [{name}]({name.lower().replace(".", "-")})')
            for cls in module.classes:
                lines.append(f'  - [{cls.name}]({name.lower().replace(".", "-")}#{cls.name.lower()})')
            for func in module.functions:
                lines.append(f'  - [{func.name}]({name.lower().replace(".", "-")}#{func.name.lower()})')
        lines.append('\n---\n')

        # 详细文档
        for name, module in sorted(self._modules.items()):
            lines.append(f'\n## {name}\n')
            if module.description:
                lines.append(f'{module.description}\n')

            # 类文档
            for cls in module.classes:
                lines.append(f'\n### class `{cls.name}`\n')
                if cls.description:
                    lines.append(f'{cls.description}\n')

                # 属性
                if cls.attributes:
                    lines.append('**属性：**\n')
                    lines.append('| 名称 | 类型 |')
                    lines.append('|------|------|')
                    for attr in cls.attributes:
                        lines.append(f"| {attr['name']} | {attr.get('type', '-')} |")
                    lines.append('')

                # 方法
                if cls.methods:
                    lines.append('**方法：**\n')
                    for method in cls.methods:
                        lines.append(f'\n#### `{method.name}`\n')
                        if method.description:
                            lines.append(f'{method.description}\n')
                        if method.parameters:
                            lines.append('**参数：**\n')
                            lines.append('| 名称 | 类型 | 默认 | 说明 |')
                            lines.append('|------|------|------|------|')
                            for p in method.parameters:
                                default = p.get('default', '')
                                lines.append(f"| {p['name']} | {p.get('type', '-')} | {default} | {p.get('description', '-')} |")
                            lines.append('')
                        if method.returns:
                            lines.append(f'**返回：** {method.returns}\n')
                        if method.examples:
                            lines.append('**示例：**\n')
                            for ex in method.examples:
                                lines.append(f'```python\n{ex}\n```\n')

            # 函数文档
            for func in module.functions:
                lines.append(f'\n### def `{func.name}`\n')
                if func.description:
                    lines.append(f'{func.description}\n')

                # 参数
                if func.parameters:
                    lines.append('**参数：**\n')
                    lines.append('| 名称 | 类型 | 默认 | 说明 |')
                    lines.append('|------|------|------|------|')
                    for p in func.parameters:
                        default = p.get('default', '')
                        lines.append(f"| {p['name']} | {p.get('type', '-')} | {default} | {p.get('description', '-')} |")
                    lines.append('')

                if func.returns:
                    lines.append(f'**返回：** {func.returns}\n')

                if func.examples:
                    lines.append('**示例：**\n')
                    for ex in func.examples:
                        lines.append(f'```python\n{ex}\n```\n')

                lines.append(f'\n*来源：{func.source_file}:{func.source_line}*\n')

        content = '\n'.join(lines)
        Path(output_path).write_text(content, encoding='utf-8')
        return content

    def generate_html(self, output_path: str) -> str:
        """
        生成 HTML 格式文档

        Args:
            output_path: 输出文件路径

        Returns:
            生成的 HTML 内容
        """
        md_content = self.generate_markdown(output_path.replace('.html', '.md'))

        # 简单的 Markdown 转 HTML
        html_lines = []
        html_lines.append('<!DOCTYPE html>')
        html_lines.append('<html lang="zh-CN">')
        html_lines.append('<head>')
        html_lines.append('  <meta charset="UTF-8">')
        html_lines.append('  <title>Matha API 参考文档</title>')
        html_lines.append('  <style>')
        html_lines.append('    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }')
        html_lines.append('    pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }')
        html_lines.append('    code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }')
        html_lines.append('    table { border-collapse: collapse; width: 100%; }')
        html_lines.append('    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }')
        html_lines.append('    th { background: #f4f4f4; }')
        html_lines.append('    h1, h2, h3 { color: #333; }')
        html_lines.append('    .module { margin-bottom: 40px; }')
        html_lines.append('  </style>')
        html_lines.append('</head>')
        html_lines.append('<body>')
        html_lines.append('<h1>Matha API 参考文档</h1>')
        html_lines.append('<p>自动生成于 ' + __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '</p>')
        html_lines.append('<hr>')

        # 简单转换（实际项目应使用 markdown 库）
        for line in md_content.split('\n'):
            line = line.replace('<', '&lt;').replace('>', '&gt;')
            if line.startswith('## '):
                html_lines.append(f'<h2>{line[3:]}</h2>')
            elif line.startswith('### '):
                html_lines.append(f'<h3>{line[4:]}</h3>')
            elif line.startswith('#### '):
                html_lines.append(f'<h4>{line[5:]}</h4>')
            elif line.startswith('- '):
                html_lines.append(f'<li>{line[2:]}</li>')
            elif line.startswith('|'):
                html_lines.append(f'<p>{line}</p>')
            elif line.startswith('```'):
                html_lines.append(f'<pre>{line}</pre>')
            elif line.strip():
                html_lines.append(f'<p>{line}</p>')

        html_lines.append('</body></html>')

        content = '\n'.join(html_lines)
        Path(output_path).write_text(content, encoding='utf-8')
        return content

    def generate_json(self, output_path: str) -> str:
        """
        生成 JSON 格式文档

        Args:
            output_path: 输出文件路径

        Returns:
            生成的 JSON 内容
        """
        if not self._modules:
            self.generate()

        data = {}
        for name, module in self._modules.items():
            data[name] = {
                'description': module.description,
                'classes': [
                    {
                        'name': cls.name,
                        'description': cls.description,
                        'attributes': cls.attributes,
                        'methods': [
                            {
                                'name': m.name,
                                'description': m.description,
                                'parameters': m.parameters,
                                'returns': m.returns,
                                'examples': m.examples,
                            }
                            for m in cls.methods
                        ]
                    }
                    for cls in module.classes
                ],
                'functions': [
                    {
                        'name': f.name,
                        'description': f.description,
                        'parameters': f.parameters,
                        'returns': f.returns,
                        'examples': f.examples,
                    }
                    for f in module.functions
                ]
            }

        content = json.dumps(data, ensure_ascii=False, indent=2)
        Path(output_path).write_text(content, encoding='utf-8')
        return content


# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 文档生成器演示")
    print("=" * 60)

    # 创建生成器
    generator = MathaDocGenerator([
        'src/stdlib',
        'src/domains',
        'src/optimization',
    ])

    # 生成文档
    print("\n正在扫描源代码...")
    modules = generator.generate()
    print(f"  发现 {len(modules)} 个模块")

    # 生成 Markdown
    print("\n生成 Markdown 文档...")
    md_content = generator.generate_markdown('docs/api_reference.md')
    print(f"  已保存到 docs/api_reference.md ({len(md_content)} 字符)")

    # 生成 HTML
    print("\n生成 HTML 文档...")
    html_content = generator.generate_html('docs/api_reference.html')
    print(f"  已保存到 docs/api_reference.html ({len(html_content)} 字符)")

    # 生成 JSON
    print("\n生成 JSON 文档...")
    json_content = generator.generate_json('docs/api_reference.json')
    print(f"  已保存到 docs/api_reference.json ({len(json_content)} 字符)")

    # 显示部分文档
    print("\n" + "=" * 60)
    print("  文档预览（前 500 字符）")
    print("=" * 60)
    print(md_content[:500])
    print("\n...")
    print("=" * 60)
    print("  文档生成完成")
    print("=" * 60)
