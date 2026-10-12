with open('src/unified_growth.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复第458行：']\n \n' -> ']\n\n'
# 修复第462行：' \n' -> '\n'
# 第463行缩进应该是4（类方法），目前是4，正确

content = content.replace(']\n \n# ── 远程升级通道', ']\n\n# ── 远程升级通道')
content = content.replace('\n \n    def check_remote_upgrades', '\n\n    def check_remote_upgrades')

with open('src/unified_growth.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed')