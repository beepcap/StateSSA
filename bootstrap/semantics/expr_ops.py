from ..types import Type, PrimitiveType, Newtype, StructType, PointerType

UNSIGNED = {"u8", "u16", "u32", "u64"}

def check_binary_op(op: str, lt: Type, rt: Type, line: int = 0) -> Type:
    l_nt, r_nt = isinstance(lt, Newtype), isinstance(rt, Newtype)
    if op in ("+", "-"):
        if l_nt and r_nt:
            if lt.name == rt.name: return lt
            raise TypeError(f"Invalid binary operation '{op}' between nominal types '{lt.name}' and '{rt.name}' at line {line}")
        if l_nt or r_nt:
            ln = lt.name if l_nt else getattr(lt, "name", str(lt))
            rn = rt.name if r_nt else getattr(rt, "name", str(rt))
            raise TypeError(f"Invalid binary operation '{op}' between '{ln}' and '{rn}' at line {line}: implicit coercion prohibited; use explicit cast")
    elif op in ("*", "/"):
        if l_nt and r_nt:
            raise TypeError(f"Binary operator '{op}' not supported directly for Newtype '{lt.name}' at line {line}: unwrap via cast({lt.unwrap().name}) before multiplication")
        if l_nt and not r_nt: return lt
        if r_nt and not l_nt:
            if op == "*": return rt
            raise TypeError(f"Binary operator '/' with scalar numerator and Newtype denominator not supported at line {line}")
    elif op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||") or (op in ("&", "|", "^") and getattr(lt, "name", "") == "i1"):
        if l_nt and r_nt:
            if lt.name == rt.name: return PrimitiveType("i1")
            raise TypeError(f"Cannot compare different nominal types '{lt.name}' and '{rt.name}' with operator '{op}' at line {line}")
        if l_nt or r_nt:
            raise TypeError(f"Cannot compare nominal and primitive types with operator '{op}' at line {line}")
        return PrimitiveType("i1")
    elif op in ("&", "|", "^", "<<", ">>") and (l_nt or r_nt):
        nt = lt if l_nt else rt
        raise TypeError(f"Bitwise operation '{op}' not supported for Newtype '{nt.name}' at line {line}: cast to base type '{nt.unwrap().name}' required")
    if op == "+" and isinstance(lt, PointerType): return lt
    ln, rn = getattr(lt, "name", ""), getattr(rt, "name", "")
    for t in ("f64", "f32", "q64"):
        if t in (ln, rn): return PrimitiveType(t)
    if "u64" in (ln, rn): return PrimitiveType("u64")
    return PrimitiveType("i64" if "i64" in (ln, rn) else ("u32" if any(x in ("u32", "u16", "u8") for x in (ln, rn)) else "i32"))

def check_unary_op(op: str, val_t: Type, line: int = 0) -> Type:
    if op == "-" and isinstance(val_t, Newtype) and getattr(val_t.unwrap(), "name", "") in UNSIGNED:
        raise TypeError(f"Unary '-' operator cannot be applied to unsigned type '{val_t.name}' (base: '{val_t.unwrap().name}') at line {line}")
    return val_t

def check_cast(from_t: Type, to_t: Type, line: int = 0) -> Type:
    if isinstance(from_t, Newtype) and isinstance(to_t, StructType):
        raise TypeError(f"Illegal cast from '{from_t.name}' to struct type '{to_t.name}' at line {line}")
    if isinstance(from_t, Newtype) and not isinstance(from_t.unwrap(), PointerType) and isinstance(to_t, PointerType):
        raise TypeError(f"Illegal cast from non-pointer Newtype '{from_t.name}' to pointer type at line {line}")
    return to_t
