from ..types import Type, PrimitiveType, Newtype, StructType, PointerType, BoundedType

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
    if op == "+" and isinstance(lt, PointerType):
        rt_name = rt.unwrap().to_str() if hasattr(rt, "unwrap") else getattr(rt, "name", str(rt))
        INTEGER_TYPES = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}
        if rt_name not in INTEGER_TYPES:
            raise TypeError(f"Pointer addition requires an integer offset, got '{rt_name}' at line {line}")
        return lt
    if op == "-" and isinstance(lt, PointerType) and isinstance(rt, PointerType):
        lt_base = lt.base_type.to_str()
        rt_base = rt.base_type.to_str()
        if lt_base != rt_base and lt_base not in ("void", "u8") and rt_base not in ("void", "u8"):
            raise TypeError(f"Invalid pointer subtraction between incompatible types '*{lt_base}' and '*{rt_base}' at line {line}")
        return PrimitiveType("i64")
    if op == "-" and isinstance(lt, PointerType) and not isinstance(rt, PointerType):
        rt_name = rt.unwrap().to_str() if hasattr(rt, "unwrap") else getattr(rt, "name", str(rt))
        INTEGER_TYPES = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}
        if rt_name not in INTEGER_TYPES:
            raise TypeError(f"Pointer subtraction requires an integer offset or pointer, got '{rt_name}' at line {line}")
        return lt
    if isinstance(lt, BoundedType):
        return lt
    if isinstance(rt, BoundedType):
        return rt
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

    fn = from_t.unwrap().to_str() if hasattr(from_t, "unwrap") else getattr(from_t, "name", str(from_t))
    tn = to_t.unwrap().to_str() if hasattr(to_t, "unwrap") else getattr(to_t, "name", str(to_t))

    # DEFECT-05: 1. Pointer <-> Floating-point prohibition
    if (fn.startswith("*") and tn in ("f32", "f64")) or (fn in ("f32", "f64") and tn.startswith("*")):
        raise TypeError(f"Illegal direct cast between pointer type '{fn}' and floating-point type '{tn}' at line {line}: intermediary integer cast required")

    # DEFECT-05: 2. Vector <-> Scalar or incompatible vector prohibition
    def is_vec_str(s: str) -> bool:
        import re
        return bool(re.match(r'^(f32|f64|i32|i64|u8|u16|u32|u64)x\d+$', s[1:] if s.startswith("*") else s))

    is_fn_vec = is_vec_str(fn) and not fn.startswith("*")
    is_tn_vec = is_vec_str(tn) and not tn.startswith("*")
    if is_fn_vec != is_tn_vec:
        raise TypeError(f"Cannot cast directly between SIMD vector type '{fn}' and scalar type '{tn}' at line {line}")
    if is_fn_vec and is_tn_vec and fn != tn:
        raise TypeError(f"Cannot cast directly between different SIMD vector types '{fn}' and '{tn}' at line {line}")

    # DEFECT-05: 3. Struct direct cast prohibition
    if (isinstance(from_t, StructType) or isinstance(to_t, StructType)) and fn != tn:
        raise TypeError(f"Illegal direct cast involving struct type ('{fn}' to '{tn}') at line {line}")

    return to_t

def type_to_str(t: Type) -> str:
    if hasattr(t, "name") and t.name:
        return t.name
    if hasattr(t, "to_str"):
        s = t.to_str()
        if s: return s
    return str(t)

def is_assignable(exp_t: Type, act_t: Type) -> bool:
    if exp_t.is_equivalent_to(act_t):
        return True
    if isinstance(exp_t, Newtype) or isinstance(act_t, Newtype):
        return False
    e = exp_t.unwrap()
    a = act_t.unwrap()
    if e.is_equivalent_to(a):
        return True
    is_e_ptr = isinstance(e, PointerType)
    is_a_ptr = isinstance(a, PointerType)
    if is_e_ptr and is_a_ptr:
        e_base_t = e.base_type
        a_base_t = a.base_type
        e_base = type_to_str(e_base_t)
        a_base = type_to_str(a_base_t)
        if e_base in ("void", "u8") or a_base in ("void", "u8"):
            return True
        if e_base == a_base:
            return True
        return False
    INTEGER_TYPES = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}
    e_name = getattr(e, "name", str(e))
    a_name = getattr(a, "name", str(a))
    if e_name in INTEGER_TYPES and a_name in INTEGER_TYPES:
        return True
    if e_name in ("f32", "f64") and a_name in ("f32", "f64"):
        return True
    if e_name == "q64" and (a_name in INTEGER_TYPES or a_name in ("f32", "f64") or a_name == "q64"):
        return True
    if a_name == "q64" and (e_name in INTEGER_TYPES or e_name in ("f32", "f64") or e_name == "q64"):
        return True
    return False

