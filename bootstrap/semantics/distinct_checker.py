from typing import Any
from ..types import PointerType
from .origin_tracker import OriginTracker

class DistinctChecker:
    def __init__(self, machines: dict):
        self.machines = machines

    def check_machine(self, m, registry):
        for p in m.params:
            if p.is_distinct and not isinstance(registry.resolve(p.type_str).unwrap(), PointerType):
                raise TypeError(f"Invalid 'distinct' modifier on non-pointer type '{p.name}: {p.type_str}' in machine '{m.name}'. 'distinct' can only be applied to pointer types.")

        alias_map: dict[str, Any] = {w.name: w.expr for w in m.flow.wires}
        for s in m.states:
            s_alias = dict(alias_map)
            for act in s.actions:
                if act.kind == "let" and act.target:
                    s_alias[act.target] = act.expr
                elif act.kind == "call" and hasattr(act.expr, "func"):
                    self.check_call(act.expr, m, s_alias, registry)

    def check_call(self, call, caller_m, alias_map: dict[str, Any], registry):
        callee = self.machines.get(call.func)
        if not callee: return
        tracker = OriginTracker(alias_map)
        distinct_origs, all_ptr_origs = {}, {}
        for arg, param in zip(call.args, callee.params):
            is_ptr = param.is_distinct or isinstance(registry.resolve(param.type_str).unwrap(), PointerType)
            if not is_ptr: continue
            origin = tracker.resolve(arg)
            if not origin: continue
            if param.is_distinct:
                if origin in all_ptr_origs:
                    prev = all_ptr_origs[origin]
                    raise TypeError(f"Distinct memory violation in '{caller_m.name}': variable '{origin}' is passed to distinct parameter '{param.name}' and parameter '{prev}' in call to '{callee.name}'")
                distinct_origs[origin] = param.name
            else:
                if origin in distinct_origs:
                    prev = distinct_origs[origin]
                    raise TypeError(f"Distinct memory violation in '{caller_m.name}': variable '{origin}' cannot be passed to both distinct '{prev}' and normal '{param.name}' in call to '{callee.name}'")
            all_ptr_origs[origin] = param.name
