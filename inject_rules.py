with open('src/symbolic.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find insertion point - after logger line, before AST section
marker = '# ═══════════════════════════════════════════════════════════════════════════════\n#  AST 节点体系'
insert_pos = content.find(marker)
if insert_pos == -1:
    print("Marker not found!")
    exit(1)

rule_engine_code = '''
# ═══════════════════════════════════════════════════════════════════════════════
#  规则引擎基础设施
# ═══════════════════════════════════════════════════════════════════════════════

class RulePriority:
    """规则优先级常量，数值越大优先级越高"""
    CORE = 1000      # 核心恒等式 (x+0=x, x*1=x, x^0=1)
    ALGEBRAIC = 800  # 代数化简 (合并同类项, 乘零, 除一)
    TRIG = 600       # 三角恒等式 (sin^2+cos^2=1)
    CALCULUS = 500   # 微积分规则 (链式法则, 乘积法则)
    EXPANSION = 300  # 展开规则
    DEFAULT = 100    # 兜底规则


@dataclass(frozen=True)
class Rule:
    """单条重写规则"""
    name: str
    pattern: Type['Expr'] | Callable[['Expr'], bool]  # 匹配类型或谓词
    handler: Callable[['Expr'], Optional['Expr']]     # 处理函数，返回新表达式或 None
    priority: int = RulePriority.DEFAULT
    enabled: bool = True

    def matches(self, expr: 'Expr') -> bool:
        if isinstance(self.pattern, type):
            return isinstance(expr, self.pattern)
        return self.pattern(expr)


class RuleSet:
    """有序规则集，按优先级自动排序"""
    def __init__(self, name: str):
        self.name = name
        self._rules: List[Rule] = []

    def add(self, rule: Rule) -> 'RuleSet':
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        return self

    def add_rule(self, name: str, pattern, handler, priority=RulePriority.DEFAULT) -> 'RuleSet':
        return self.add(Rule(name, pattern, handler, priority))

    def remove(self, name: str) -> 'RuleSet':
        self._rules = [r for r in self._rules if r.name != name]
        return self

    def enable(self, name: str, enabled: bool = True) -> 'RuleSet':
        for r in self._rules:
            if r.name == name:
                r.enabled = enabled
                break
        return self

    def get_enabled(self) -> List[Rule]:
        return [r for r in self._rules if r.enabled]

    def __iter__(self):
        return iter(self.get_enabled())


class RuleEngine:
    """规则引擎：管理多个规则集，支持简化/求导/积分/求值"""
    
    def __init__(self):
        self.rulesets: Dict[str, RuleSet] = {}
    
    def register(self, ruleset: RuleSet) -> 'RuleEngine':
        self.rulesets[ruleset.name] = ruleset
        return self
    
    def get(self, name: str) -> Optional[RuleSet]:
        return self.rulesets.get(name)
    
    def apply(self, ruleset_name: str, expr: 'Expr', max_iterations: int = 100) -> 'Expr':
        """应用规则集直到不动点或达到最大迭代次数"""
        ruleset = self.rulesets.get(ruleset_name)
        if not ruleset:
            return expr
        
        current = expr
        for _ in range(max_iterations):
            changed = False
            for rule in ruleset:
                if rule.matches(current):
                    result = rule.handler(current)
                    if result is not None and result is not current:
                        current = result
                        changed = True
                        break  # 重新开始匹配（优先级高的规则优先）
            if not changed:
                break
        return current
    
    def apply_once(self, ruleset_name: str, expr: 'Expr') -> 'Expr':
        """单次应用规则集（不迭代到不动点）"""
        ruleset = self.rulesets.get(ruleset_name)
        if not ruleset:
            return expr
        for rule in ruleset:
            if rule.matches(expr):
                result = rule.handler(expr)
                if result is not None and result is not expr:
                    return result
        return expr


# 全局规则引擎实例
_global_engine = RuleEngine()


def get_engine() -> RuleEngine:
    return _global_engine


'''

new_content = content[:insert_pos] + rule_engine_code + '\n' + content[insert_pos:]

with open('src/symbolic.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Rule engine injected successfully!")