from dataclasses import dataclass
from typing import Dict, Union

@dataclass(frozen=True)
class Type:
    def is_equivalent_to(self, other: "Type") -> bool: return self == other
    def unwrap(self) -> "Type": return self
    def to_str(self) -> str: return getattr(self, "name", "")
@dataclass(frozen=True)
class PrimitiveType(Type): name: str

@dataclass(frozen=True)
class Newtype(Type):
    name: str
    base_type: Type
    def is_equivalent_to(self, other: "Type") -> bool:
        return isinstance(other, Newtype) and self.name == other.name
    def unwrap(self) -> Type: return self.base_type.unwrap()
    def to_str(self) -> str: return self.unwrap().to_str()

@dataclass(frozen=True)
class BoundedType(Type):
    name: str
    base_type: Type
    min_val: Union[float, int]
    max_val: Union[float, int]
    def is_equivalent_to(self, other: "Type") -> bool:
        return isinstance(other, BoundedType) and self.name == other.name
    def unwrap(self) -> Type: return self.base_type.unwrap()
    def to_str(self) -> str: return self.unwrap().to_str()

@dataclass(frozen=True)
class StructType(Type):
    name: str
    fields: Dict[str, Type]

@dataclass(frozen=True)
class PointerType(Type):
    base_type: Type
    def unwrap(self) -> Type: return PointerType(self.base_type.unwrap())
    def to_str(self) -> str: return f"*{self.base_type.to_str()}"

@dataclass(frozen=True)
class DistinctPointerType(PointerType): pass
@dataclass(frozen=True)
class VectorType(Type):
    elem_type: Type
    lanes: int
    def to_str(self) -> str: return f"{self.elem_type.to_str()}x{self.lanes}"
