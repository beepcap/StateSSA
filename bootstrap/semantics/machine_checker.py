from ..ast_nodes import Machine
from ..types import Newtype
from .scope import Scope
from .expr_checker import ExprChecker
from .rule_checker import RuleChecker

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
                if not rt.is_equivalent_to(it) and (isinstance(rt, Newtype) or isinstance(it, Newtype)):
                    raise TypeError(f"Type mismatch in reg '{r.name}' initialization: cannot assign '{it.name}' to '{rt.name}'")
        for w in m.flow.wires: scope.define(w.name, self.expr_checker.check(w.expr, scope))
        m_ret_t = self.registry.resolve(m.ret_type)
        for s in m.states:
            for act in s.actions:
                if act.kind == "let" and act.target:
                    scope.define(act.target, self.expr_checker.check(act.expr, scope))
                elif act.kind == "store":
                    tgt_t = self.expr_checker.check(act.target, scope)
                    val_t = self.expr_checker.check(act.expr, scope)
                    if not tgt_t.is_equivalent_to(val_t) and (isinstance(tgt_t, Newtype) or isinstance(val_t, Newtype)):
                        t_name = getattr(tgt_t, "name", str(tgt_t))
                        v_name = getattr(val_t, "name", str(val_t))
                        raise TypeError(f"Type mismatch in store: cannot assign '{v_name}' to target of type '{t_name}'")
            for rule in s.rules:
                self.rule_checker.check_rule(rule, scope, m_ret_t, m.name)
