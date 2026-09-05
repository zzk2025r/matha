from src.parser import Parser
from src.tokens import Token, TokenType

src = "v = 加(10, 20)"
print("Source:", repr(src))

# Manual tokenization
from src.lexer import Lexer
lex = Lexer(src)
tokens = list(lex.tokenize())
for i, t in enumerate(tokens):
    print(f"  {i}: {t.type.name:25s} {repr(t.value):20s} line={t.line} col={t.col}")

# Now parse with detailed tracing
print("\n--- Parsing ---")
try:
    from src.parser import parse
    prog = parse(src)
    print("OK:", prog.decls)
except Exception as e:
    print("FAIL:", e)
    import traceback
    traceback.print_exc()
