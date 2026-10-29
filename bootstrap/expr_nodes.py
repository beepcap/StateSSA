from dataclasses import dataclass
from typing import Any

@dataclass
class BinaryExpr:
    op: str
    left: Any
    right: Any

@dataclass
class UnaryExpr:
    op: str
    operand: Any

@dataclass
class CallExpr:
    func: str
    args: list[Any]

@dataclass
class FieldExpr:
    target: Any
    field: str

@dataclass
class StructLit:
    type_name: str
    fields: list[tuple[str, Any]]

@dataclass
class VarExpr:
    name: str

@dataclass
class NullLit:
    pass

@dataclass
class IntLit:
    val: int

@dataclass
class StringLit:
    val: str

@dataclass
class CastExpr:
    target_type: str
    expr: Any
