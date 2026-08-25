# -*- coding: utf-8 -*-
"""Quick type system test."""
import sys; sys.path.insert(0, r'd:\trae')

# Direct test without importing the module
from src.typesystem_v2 import Type, TypeKind

# Test basic types
t_int = Type(TypeKind.PRIMITIVE, "Int")
print(f"Type: {t_int}, kind={t_int.kind}, name={t_int.name}")

# Test static method
t_constrained = Type.with_constraints(t_int, "Numeric")
print(f"Constrained: {t_constrained}, constraints={t_constrained.constraints}")

# Test class-level constants
from src.typesystem_v2 import T_INT, T_NUMERIC
print(f"T_INT: {T_INT}")
print(f"T_NUMERIC: {T_NUMERIC}")
print("OK")
