from ..types import PrimitiveType, Newtype
from ..expr_nodes import NullLit
from .expr_ops import is_assignable, type_to_str

def _expr_to_str(expr) -> str:
    if hasattr(expr, "name"):
        return str(expr.name)
    if hasattr(expr, "val"):
        return str(expr.val)
    if isinstance(expr, NullLit):
        return "null"
    return "expr"

class RuleChecker:
    def __init__(self, expr_checker):
        self.expr_checker = expr_checker

    def check_state_exhaustiveness(self, state, m_name: str):
        if not state.rules:
            raise TypeError(f"State '{state.name}' in machine '{m_name}' has no transition rules (FAIL-FAST: at least one default transition '_ => ...' required)")
        last_rule = state.rules[-1]
        if last_rule.guard is not None:
            raise TypeError(
                f"Missing default transition in state '{state.name}' of machine '{m_name}': "
                f"every state must terminate with an unconditional transition ('_ => ...', 'return', or 'panic')"
            )

    def check_rule(self, rule, scope, m_ret_t, m_name: str):
        if rule.guard:
            gt = self.expr_checker.check(rule.guard, scope)
            if not (isinstance(gt, PrimitiveType) and gt.name == "i1"):
                g_name = getattr(gt, "name", str(gt))
                raise TypeError(f"Guard condition in machine '{m_name}' must be of type 'i1', got '{g_name}'")
        if rule.is_return:
            act_t = self.expr_checker.check(rule.ret_expr, scope) if rule.ret_expr else PrimitiveType("void")
            if not is_assignable(m_ret_t, act_t):
                e_name = type_to_str(m_ret_t)
                a_name = type_to_str(act_t)
                raise TypeError(f"Return type mismatch in machine '{m_name}': expected '{e_name}', got '{a_name}'")
        for reg_name, val_expr in rule.latches:
            reg_t = scope.lookup(reg_name)
            val_t = self.expr_checker.check(val_expr, scope)
            if reg_t and not is_assignable(reg_t, val_t):
                v_repr = _expr_to_str(val_expr)
                r_name = type_to_str(reg_t)
                val_name = type_to_str(val_t)
                raise TypeError(f"Type mismatch in latch update '{reg_name} <= {v_repr}': cannot assign '{val_name}' to register '{reg_name}' of type '{r_name}'")
