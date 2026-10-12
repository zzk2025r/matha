# -*- coding: utf-8 -*-
"""Fix virtual_code.py indentation."""
import re

with open('D:/trae/src/virtual_code.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace continuation lines with correct indentation (28 spaces -> 28 spaces)
# The problem: def lines have 4 spaces, continuation lines should have 28 spaces
# But Python sees 28 spaces as invalid for a continuation after a 4-space def
# Solution: Change continuation to 8 spaces (aligned with def body)

# Pattern: 4-space def + 28-space continuation -> 4-space def + 8-space continuation
# Actually, the issue is simpler: the continuation line should be indented to match the opening paren

# Find and fix all generate_ methods
replacements = [
    ('    def generate_game_module(self, game_type: str = "2d",\n                            features:',
     '    def generate_game_module(self, game_type: str = "2d",\n                            features:'),
    ('    def generate_office_module(self, doc_type: str = "document",\n                            features:',
     '    def generate_office_module(self, doc_type: str = "document",\n                            features:'),
    ('    def generate_os_module(self, os_type: str = "process",\n                            features:',
     '    def generate_os_module(self, os_type: str = "process",\n                            features:'),
    ('    def generate_graphics_module(self, render_type: str = "2d",\n                            features:',
     '    def generate_graphics_module(self, render_type: str = "2d",\n                            features:'),
    ('    def generate_networking_module(self, net_type: str = "http",\n                            features:',
     '    def generate_networking_module(self, net_type: str = "http",\n                            features:'),
]

# Actually the simplest fix: just change all 28-space continuation lines to 28 spaces
# Wait, they already have 28 spaces. The problem is they need to be different.
# Let me just change all occurrences of the pattern.

# The real fix: use a single-line approach
content = re.sub(
    r'    def (generate_\w+_module)\(self, (\w+: str = "[^"]+"),\n                            (features:',
    r'    def \1(self, \2,\n                            \3',
    content
)

with open('D:/trae/src/virtual_code.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
try:
    import ast
    ast.parse(open('D:/trae/src/virtual_code.py', encoding='utf-8').read())
    print("Syntax OK!")
except SyntaxError as e:
    print(f"Syntax Error at line {e.lineno}: {e.msg}")
