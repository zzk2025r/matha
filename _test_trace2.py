import sys
sys.path.insert(0, '.')
import importlib
import src.parser; importlib.reload(src.parser)
import src.interp; importlib.reload(src.interp)
from src.parser import Parser

src = '@：【计价参数】，单价=10，数量=3'
p = Parser(src)

# Patch to trace
orig_parse_set_up = Parser._parse_set_up
def traced_parse_set_up(self, seg_id=None):
    import logging
    self._log = logging.getLogger('trace')
    self._log.setLevel(logging.DEBUG)
    print(f'[_parse_set_up] START pos={self.pos} tok={self._current().type.name}')
    result = orig_parse_set_up(self, seg_id)
    print(f'[_parse_set_up] END pos={self.pos} tok={self._current().type.name} items={len(result.items)}')
    return result
Parser._parse_set_up = traced_parse_set_up

orig_parse_set_up_item = Parser._parse_set_up_item
def traced_parse_set_up_item(self):
    print(f'[_parse_set_up_item] START pos={self.pos} tok={self._current().type.name} {self._current().value!r}')
    result = orig_parse_set_up_item(self)
    print(f'[_parse_set_up_item] END pos={self.pos} tok={self._current().type.name} {self._current().value!r}')
    print(f'  -> target={result.target} value={type(result.value).__name__ if result.value else None}')
    return result
Parser._parse_set_up_item = traced_parse_set_up_item

ast_tree = p.parse()
print(f'\nResult: {len(ast_tree.decls)} decls')
for d in ast_tree.decls:
    if hasattr(d, 'items'):
        print(f'  SetUp: {len(d.items)} items')
        for j, it in enumerate(d.items):
            print(f'    @{j} target={it.target} value={type(it.value).__name__ if it.value else None}')
