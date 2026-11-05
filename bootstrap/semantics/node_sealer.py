from ..expr_nodes import CallExpr, VarExpr, UnaryExpr, BinaryExpr, CastExpr, FieldExpr

def _check_expr(expr, sealed: dict[str, str]):
    if isinstance(expr, CallExpr):
        if expr.func in sealed:
            raise TypeError(f"Exclusive node violation: machine '{expr.func}' is sealed as a dedicated network component in '{sealed[expr.func]}' and cannot be called directly")
        for a in expr.args: _check_expr(a, sealed)
    elif isinstance(expr, VarExpr):
        if expr.name in sealed:
            raise TypeError(f"Exclusive node violation: machine '{expr.name}' is sealed as a dedicated network component in '{sealed[expr.name]}' and cannot be referenced directly")
    elif isinstance(expr, (UnaryExpr, CastExpr)):
        op = getattr(expr, "operand", getattr(expr, "expr", None))
        if op: _check_expr(op, sealed)
    elif isinstance(expr, BinaryExpr):
        _check_expr(expr.left, sealed)
        _check_expr(expr.right, sealed)
    elif isinstance(expr, FieldExpr): _check_expr(expr.target, sealed)

class NodeSealer:
    def __init__(self, networks: list):
        self.sealed: dict[str, str] = {}
        for net in networks:
            for node in net.nodes:
                if node.machine_name in self.sealed:
                    prev_net = self.sealed[node.machine_name]
                    raise TypeError(f"Machine '{node.machine_name}' is already exclusively bound to network '{prev_net}' and cannot be rebound in '{net.name}'")
                self.sealed[node.machine_name] = net.name

    def verify_program(self, prog):
        if not self.sealed: return
        for m in prog.machines:
            for w in m.flow.wires: _check_expr(w.expr, self.sealed)
            for s in m.states:
                for act in s.actions: _check_expr(act.expr, self.sealed)
                for r in s.rules:
                    if r.guard: _check_expr(r.guard, self.sealed)
                    if r.ret_expr: _check_expr(r.ret_expr, self.sealed)
                    for _, le in r.latches: _check_expr(le, self.sealed)
