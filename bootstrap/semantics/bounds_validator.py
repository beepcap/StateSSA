from typing import Union
from ..types import Type, PointerType, StructType
from ..ast_nodes import BoundsNode
from ..expr_nodes import FloatLit

INT_RANGES = {
    "u8": (0, 255), "i8": (-128, 127), "u16": (0, 65535), "i16": (-32768, 32767),
    "u32": (0, 4294967295), "i32": (-2147483648, 2147483647),
    "u64": (0, 2**64 - 1), "i64": (-2**63, 2**63 - 1),
}

def _check_val(base_name: str, expr, val: Union[float, int]):
    if base_name in INT_RANGES:
        if isinstance(expr, FloatLit):
            raise TypeError(f"Floating-point bound '{expr.raw_str}' cannot be applied to integer base type '{base_name}'")
        low, high = INT_RANGES[base_name]
        if not (low <= val <= high):
            raise TypeError(f"Bound value {val} exceeds capacity of base type '{base_name}' ({low}..{high})")
    elif base_name == "f32" and abs(val) > 3.4028235e38:
        raise TypeError("Bound value exceeds IEEE 754 single-precision range (-3.4e38..3.4e38)")

def validate_and_extract_bounds(name: str, base_type: Type, bounds: BoundsNode):
    if isinstance(base_type, PointerType):
        raise TypeError(f"Cannot apply range constraint to pointer type '{base_type.to_str()}'")
    if isinstance(base_type, StructType):
        raise TypeError(f"Cannot apply range constraint to struct type '{base_type.to_str()}'")
    bname = base_type.unwrap().to_str()
    if bname == "void": raise TypeError("Cannot apply range constraint to void type")

    min_v, max_v = bounds.min_expr.val, bounds.max_expr.val
    if bname in ("f32", "f64"):
        min_v, max_v = float(min_v), float(max_v)
    _check_val(bname, bounds.min_expr, min_v)
    _check_val(bname, bounds.max_expr, max_v)
    if min_v > max_v:
        raise TypeError(f"Invalid bounded range [{min_v} .. {max_v}] in type '{name}': min must be <= max")
    if bname == "q64":
        return int(round(min_v * (1 << 32))), int(round(max_v * (1 << 32)))
    return min_v, max_v
