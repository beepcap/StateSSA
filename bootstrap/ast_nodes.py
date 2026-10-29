from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class ASTNode:
    pass

@dataclass
class TypeDef(ASTNode):
    name: str
    fields: list[tuple[str, str]]

@dataclass
class ExternFn(ASTNode):
    name: str
    params: list[tuple[str, str]]
    ret_type: str

@dataclass
class Reg(ASTNode):
    name: str
    type_str: str
    init_expr: Optional[Any]

@dataclass
class Wire(ASTNode):
    name: str
    expr: Any

@dataclass
class Flow(ASTNode):
    regs: list[Reg]
    wires: list[Wire]

@dataclass
class Action(ASTNode):
    kind: str # 'let', 'call', 'store'
    target: Optional[str]
    expr: Any

@dataclass
class Rule(ASTNode):
    guard: Optional[Any] # None if '_'
    target: Optional[str] # State name
    latches: list[tuple[str, Any]] # (reg, expr)
    is_return: bool = False
    is_panic: bool = False
    ret_expr: Optional[Any] = None

@dataclass
class State(ASTNode):
    name: str
    actions: list[Action]
    rules: list[Rule]

@dataclass
class Machine(ASTNode):
    name: str
    params: list[tuple[str, str]]
    ret_type: str
    flow: Flow
    states: list[State]

@dataclass
class Program(ASTNode):
    includes: list[str]
    types: list[TypeDef]
    externs: list[ExternFn]
    machines: list[Machine]
