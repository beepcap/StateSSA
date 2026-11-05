from ..types import PrimitiveType, Newtype

class RuleChecker:
    def __init__(self, expr_checker):
        self.expr_checker = expr_checker

    def check_rule(self, rule, scope, m_ret_t, m_name: str):
        if rule.guard:
            gt = self.expr_checker.check(rule.guard, scope)
            if not (isinstance(gt, PrimitiveType) and gt.name == "i1"):
                g_name = getattr(gt, "name", str(gt))
                raise TypeError(f"Guard condition in machine '{m_name}' must be of type 'i1', got '{g_name}'")
        if rule.is_return:
            act_t = self.expr_checker.check(rule.ret_expr, scope) if rule.ret_expr else PrimitiveType("void")
            if not m_ret_t.is_equivalent_to(act_t):
                if isinstance(m_ret_t, Newtype) or isinstance(act_t, Newtype):
                    e_name = getattr(m_ret_t, "name", str(m_ret_t))
                    a_name = getattr(act_t, "name", str(act_t))
                    raise TypeError(f"Return type mismatch in machine '{m_name}': expected '{e_name}', got '{a_name}'")
        for reg_name, val_expr in rule.latches:
            reg_t = scope.lookup(reg_name)
            val_t = self.expr_checker.check(val_expr, scope)
            if reg_t and not reg_t.is_equivalent_to(val_t):
                if isinstance(reg_t, Newtype) or isinstance(val_t, Newtype):
                    v_repr = getattr(val_expr, "name", "expr")
                    raise TypeError(f"Type mismatch in latch update '{reg_name} <= {v_repr}': cannot assign '{val_t.name}' to register '{reg_name}' of type '{reg_t.name}'")
