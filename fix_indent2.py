with open('src/unified_growth.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the specific problematic section
old = '''    "FormulaGrowthEngine", "DomainFormulaRegistry", "FormulaCompiler",
]
 \n# ── 远程升级通道 ──────────────────────────────────────────────────────
# Remote Upgrade Channel
# ─────────────────────────────────────────────────────────────────────
 
    def check_remote_upgrades(self, server_url: str, current_version: str) -> dict:'''

new = '''    "FormulaGrowthEngine", "DomainFormulaRegistry", "FormulaCompiler",
]

# ── 远程升级通道 ──────────────────────────────────────────────────────
# Remote Upgrade Channel
# ─────────────────────────────────────────────────────────────────────

    def check_remote_upgrades(self, server_url: str, current_version: str) -> dict:'''

with open('src/unified_growth.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(old, new)

with open('src/unified_growth.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed')