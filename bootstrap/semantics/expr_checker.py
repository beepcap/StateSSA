from ..expr_nodes import BinaryExpr, UnaryExpr, CastExpr, VarExpr, IntLit, FloatLit, NullLit, StringLit, CallExpr, FieldExpr, StructLit
from ..types import Type, PrimitiveType, PointerType, StructType
from .expr_ops import check_binary_op, check_unary_op, check_cast
from .call_checker import check_call
from .scope import Scope

class ExprChecker:
    def __init__(self, registry, annotations, funcs: dict[str, str] = None):
        self.registry = registry
        self.annotations = annotations
        self.funcs = funcs or {}

    def check(self, expr, scope: Scope) -> Type:
        if isinstance(expr, BinaryExpr):
            lt = self.check(expr.left, scope)
            rt = self.check(expr.right, scope)
            # DEFECT-06: Check for integer division by zero and shift width overflow
            if expr.op in ("/", "%") and isinstance(expr.right, IntLit) and expr.right.val == 0:
                raise TypeError("Constant division by zero is prohibited")
            if expr.op in ("<<", ">>") and isinstance(expr.right, IntLit):
                lt_name = lt.unwrap().to_str() if hasattr(lt, "unwrap") else getattr(lt, "name", str(lt))
                bit_width = 64 if lt_name in ("i64", "u64") else 32
                if expr.right.val >= bit_width or expr.right.val < 0:
                    raise TypeError(f"Bit shift count {expr.right.val} exceeds or is invalid for type '{lt_name}' (width: {bit_width})")
            t = check_binary_op(expr.op, lt, rt)
        elif isinstance(expr, UnaryExpr):
            opnd_t = self.check(expr.operand, scope)
            if expr.op == "*": t = opnd_t.base_type if isinstance(opnd_t, PointerType) else opnd_t
            elif expr.op == "&": t = PointerType(opnd_t)
            else: t = check_unary_op(expr.op, opnd_t)
        elif isinstance(expr, CastExpr):
            inner_t = self.check(expr.expr, scope)
            target_t = self.registry.resolve(expr.target_type)
            t = check_cast(inner_t, target_t)
        elif isinstance(expr, VarExpr):
            t = scope.lookup(expr.name) or PrimitiveType("i32")
        elif isinstance(expr, StructLit):
            for _, fe in expr.fields: self.check(fe, scope)
            t = self.registry.resolve(expr.type_name)
        elif isinstance(expr, IntLit):
            t = PrimitiveType("i32")
        elif isinstance(expr, FloatLit):
            t = PrimitiveType("f32")
        elif isinstance(expr, NullLit):
            t = PointerType(PrimitiveType("void"))
        elif isinstance(expr, StringLit):
            t = PointerType(PrimitiveType("i8"))
        elif isinstance(expr, CallExpr):
            t = check_call(expr, self.funcs, self.registry, self.check, scope)
        elif isinstance(expr, FieldExpr):
            tgt_t = self.check(expr.target, scope)
            st = tgt_t.base_type if isinstance(tgt_t, PointerType) else tgt_t
            t = st.fields.get(expr.field, PrimitiveType("i32")) if isinstance(st, StructType) else PrimitiveType("i32")
        else:
            t = PrimitiveType("i32")
        self.annotations.expr_types[id(expr)] = t
        return t
