import sys
sys.path.insert(0, '.')
from src.lexer import Lexer

source = "while x > 0:\n    y = 1\n#[y]"
print("Source repr:", repr(source))

lex = Lexer(source)
count = 0
for t in lex.tokenize():
    print(t)
    count += 1
    if count > 30:
        print("Too many tokens, stopping")
        break
print("Done, count:", count)
