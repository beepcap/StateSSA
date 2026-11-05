from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

@dataclass
class ASTNode:
    pass

class TypeKind(Enum):
    STRUCT = "struct"
    NEWTYPE = "newtype"
    BOUNDED = "bounded"

@dataclass
class BoundsNode(ASTNode):
    min_expr: Any
    max_expr: Any

@dataclass
class TypeDef(ASTNode):
    name: str
    kind: TypeKind = TypeKind.STRUCT
    base_type: Optional[str] = None
    fields: list[tuple[str, str]] = field(default_factory=list)
    bounds: Optional[BoundsNode] = None

TypeDecl = TypeDef

@dataclass
class ParamDecl(ASTNode):
    name: str
    type_str: str
    is_distinct: bool = False

    def __iter__(self):
        yield self.name
        yield self.type_str

    def __getitem__(self, idx: int):
        return (self.name, self.type_str)[idx]

@dataclass
class ExternFn(ASTNode):
    name: str
    params: list[ParamDecl]
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
    params: list[ParamDecl]
    ret_type: str
    flow: Flow
    states: list[State]

@dataclass
class NodeDecl(ASTNode):
    node_id: str
    machine_name: str

@dataclass
class ConnectPipeline(ASTNode):
    elements: list[str]

@dataclass
class NetworkDecl(ASTNode):
    name: str
    params: list[ParamDecl]
    ret_type: str
    nodes: list[NodeDecl]
    pipelines: list[ConnectPipeline]

@dataclass
class Program(ASTNode):
    includes: list[str]
    types: list[TypeDef]
    externs: list[ExternFn]
    machines: list[Machine]
    networks: list[NetworkDecl] = field(default_factory=list)
