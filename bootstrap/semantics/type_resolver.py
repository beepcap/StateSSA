from ..types import Type, Newtype, BoundedType
from ..ast_nodes import TypeDef, TypeKind
from .bounds_validator import validate_and_extract_bounds

def resolve_single_type(name: str, pending: dict, visited: set, registry) -> Type:
    if name in registry.types:
        return registry.types[name]
    if name not in pending:
        raise TypeError(f"Unknown base type '{name}'")
    if name in visited:
        cycle_str = "' and '".join(sorted(visited))
        raise TypeError(f"Circular type definition detected involving '{cycle_str}'")
    visited.add(name)
    tdef = pending[name]
    base_str = tdef.base_type.lstrip("*")
    try:
        base_t = registry.resolve(tdef.base_type) if base_str in registry.types \
            else resolve_single_type(tdef.base_type, pending, visited, registry)
    except TypeError as e:
        if "Unknown base type" in str(e):
            raise TypeError(f"Unknown base type '{tdef.base_type}' in definition of '{name}'") from e
        raise

    if tdef.kind == TypeKind.BOUNDED:
        min_v, max_v = validate_and_extract_bounds(name, base_t, tdef.bounds)
        res = BoundedType(name, base_t, min_v, max_v)
    else:
        res = Newtype(name, base_t)
    registry.types[name] = res
    return res
