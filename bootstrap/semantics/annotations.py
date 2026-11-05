from dataclasses import dataclass, field
from ..types import Type

@dataclass
class TypeAnnotations:
    expr_types: dict[int, Type] = field(default_factory=dict)
    type_registry: dict[str, Type] = field(default_factory=dict)
    symbol_scopes: dict[str, dict[str, Type]] = field(default_factory=dict)
