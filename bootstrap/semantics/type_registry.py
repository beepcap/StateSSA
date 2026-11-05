from ..types import Type, PrimitiveType, StructType, PointerType
from ..ast_nodes import TypeDef, TypeKind
from .type_resolver import resolve_single_type

PRIMITIVES = {"i8", "u8", "i16", "u16", "i32", "u32", "i64", "u64",
              "f32", "f64", "q64", "i1", "void", "f32x4", "f32x8",
              "f32x16", "f64x2", "f64x4", "f64x8", "i32x4", "i32x8",
              "i32x16", "u8x16", "u8x32", "u8x64"}

class TypeRegistry:
    def __init__(self):
        self.types: dict[str, Type] = {p: PrimitiveType(p) for p in PRIMITIVES}

    def resolve(self, tname: str) -> Type:
        if tname.startswith("*"):
            return PointerType(self.resolve(tname[1:]))
        if tname in self.types:
            return self.types[tname]
        raise TypeError(f"Unknown base type '{tname}'")

    def register_all(self, type_defs: list[TypeDef]):
        pending = {t.name: t for t in type_defs}
        for n, td in pending.items():
            if td.kind == TypeKind.STRUCT: self.types[n] = StructType(n, {})
        for n, td in pending.items():
            if td.kind in (TypeKind.NEWTYPE, TypeKind.BOUNDED):
                resolve_single_type(n, pending, set(), self)
        for n, td in pending.items():
            if td.kind == TypeKind.STRUCT:
                self.types[n].fields.update({fn: self.resolve(ft) for fn, ft in td.fields})
