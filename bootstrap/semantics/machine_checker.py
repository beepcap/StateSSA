from ..ast_nodes import Machine
from ..expr_nodes import UnaryExpr, FieldExpr
from ..types import Newtype, PointerType
from .scope import Scope
from .expr_checker import ExprChecker
from .rule_checker import RuleChecker
from .expr_ops import is_assignable, type_to_str
from .wire_checker import check_wires_and_sort

class MachineChecker:
    def __init__(self, registry, annotations, funcs: dict = None):
        self.registry = registry
        self.annotations = annotations
        self.expr_checker = ExprChecker(registry, annotations, funcs)
        self.rule_checker = RuleChecker(self.expr_checker)

    def check_machine(self, m: Machine):
        scope = Scope()
        self.annotations.symbol_scopes[m.name] = scope.symbols
        for pn, pt in m.params: scope.define(pn, self.registry.resolve(pt))
        for r in m.flow.regs:
            rt = self.registry.resolve(r.type_str)
            scope.define(r.name, rt)
            if r.init_expr:
                it = self.expr_checker.check(r.init_expr, scope)
                if not is_assignable(rt, it):
                    r_name = type_to_str(rt)
                    i_name = type_to_str(it)
                    raise TypeError(f"Type mismatch in reg '{r.name}' initialization: cannot assign '{i_name}' to '{r_name}'")
        for w in check_wires_and_sort(m.flow.wires):
            scope.define(w.name, self.expr_checker.check(w.expr, scope))
        m_ret_t = self.registry.resolve(m.ret_type)
        for s in m.states:
            for act in s.actions:
                if act.kind == "let" and act.target:
                    scope.define(act.target, self.expr_checker.check(act.expr, scope))
                elif act.kind == "call":
                    self.expr_checker.check(act.expr, scope)
                elif act.kind == "store":
                    is_deref = isinstance(act.target, UnaryExpr) and act.target.op == "*"
                    is_field = isinstance(act.target, FieldExpr)
                    if not (is_deref or is_field):
                        target_repr = getattr(act.target, "name", str(act.target))
                        raise TypeError(f"Invalid store target '{target_repr}': memory store ('<-') target must be a dereference ('*ptr') or pointer field access ('ptr.field')")
                    if is_field:
                        base_t = self.expr_checker.check(act.target.target, scope)
                        if not isinstance(base_t, PointerType):
                            f_name = act.target.field
                            t_name = base_t.unwrap().to_str() if hasattr(base_t, "unwrap") else getattr(base_t, "name", str(base_t))
                            raise TypeError(f"Cannot store into field '{f_name}' of non-pointer value of type '{t_name}': memory store ('<-') requires a pointer to struct ('*{t_name}')")
                    tgt_t = self.expr_checker.check(act.target, scope)
                    val_t = self.expr_checker.check(act.expr, scope)
                    if not is_assignable(tgt_t, val_t):
                        t_name = type_to_str(tgt_t)
                        v_name = type_to_str(val_t)
                        raise TypeError(f"Type mismatch in store: cannot assign '{v_name}' to target of type '{t_name}'")
            self.rule_checker.check_state_exhaustiveness(s, m.name)
            for rule in s.rules:
                self.rule_checker.check_rule(rule, scope, m_ret_t, m.name)
