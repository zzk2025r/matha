with open('src/unified_growth.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复第458行（索引457）和第462行（索引461）的缩进问题
old_text = '''    "FormulaGrowthEngine", "DomainFormulaRegistry", "FormulaCompiler",
]
 \n# ── 远程升级通道 ──────────────────────────────────────────────────────
# Remote Upgrade Channel
# ─────────────────────────────────────────────────────────────────────
 
    def check_remote_upgrades(self, server_url: str, current_version: str) -> dict:'''

new_text = '''    "FormulaGrowthEngine", "DomainFormulaRegistry", "FormulaCompiler",
]

# ── 远程升级通道 ──────────────────────────────────────────────────────
# Remote Upgrade Channel
# ─────────────────────────────────────────────────────────────────────

    def check_remote_upgrades(self, server_url: str, current_version: str) -> dict:'''

with open('src/unified_growth.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(old_text, new_text)

with open('src/unified_growth.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed')