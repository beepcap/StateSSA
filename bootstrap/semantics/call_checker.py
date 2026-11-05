from ..expr_nodes import CallExpr
from ..types import Type, Newtype

def check_call(expr: CallExpr, funcs: dict, registry, check_fn, scope) -> Type:
    ret_str, param_types = funcs.get(expr.func, ("void", []))
    for i, a in enumerate(expr.args):
        act_t = check_fn(a, scope)
        if i < len(param_types):
            exp_t = registry.resolve(param_types[i])
            if not exp_t.is_equivalent_to(act_t):
                if isinstance(exp_t, Newtype) or isinstance(act_t, Newtype):
                    e_name = getattr(exp_t, "name", str(exp_t))
                    a_name = getattr(act_t, "name", str(act_t))
                    raise TypeError(f"Argument {i+1} type mismatch in call to '{expr.func}': expected '{e_name}', got '{a_name}'")
    return registry.resolve(ret_str)
