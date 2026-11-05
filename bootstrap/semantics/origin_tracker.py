from typing import Optional, Any
from ..expr_nodes import VarExpr, UnaryExpr, BinaryExpr, CastExpr, FieldExpr

class OriginTracker:
    def __init__(self, alias_map: dict[str, Any]):
        self.alias_map = alias_map

    def resolve(self, expr: Any) -> Optional[str]:
        if isinstance(expr, VarExpr):
            if expr.name in self.alias_map:
                return self.resolve(self.alias_map[expr.name])
            return expr.name
        if isinstance(expr, FieldExpr):
            target_orig = self.resolve(expr.target)
            return f"{target_orig}.{expr.field}" if target_orig else None
        if isinstance(expr, CastExpr):
            return self.resolve(expr.expr)
        if isinstance(expr, BinaryExpr) and expr.op in ("+", "-"):
            return self.resolve(expr.left) or self.resolve(expr.right)
        if isinstance(expr, UnaryExpr) and expr.op in ("&", "*"):
            return self.resolve(expr.operand)
        return None
