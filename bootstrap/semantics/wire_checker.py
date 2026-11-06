from ..expr_nodes import VarExpr

def check_wires_and_sort(wires: list) -> list:
    wire_names = {w.name for w in wires}
    wire_deps = {}
    for w in wires:
        deps = set()
        def collect_deps(e):
            if isinstance(e, VarExpr) and e.name in wire_names:
                deps.add(e.name)
            elif hasattr(e, "__dict__"):
                for v in e.__dict__.values():
                    if isinstance(v, list):
                        for item in v: collect_deps(item)
                    else:
                        collect_deps(v)
        collect_deps(w.expr)
        wire_deps[w.name] = deps

    visited = {}
    def check_cycle(name, path):
        visited[name] = 1
        for dep in sorted(wire_deps.get(name, [])):
            if visited.get(dep, 0) == 1:
                cycle_path = " -> ".join(path + [dep])
                raise TypeError(f"Cyclic wire dependency detected: {cycle_path}")
            if visited.get(dep, 0) == 0:
                check_cycle(dep, path + [dep])
        visited[name] = 2

    for w in wires:
        if visited.get(w.name, 0) == 0:
            check_cycle(w.name, [w.name])

    post_order, visited_topo = [], set()
    def dfs_topo(name):
        visited_topo.add(name)
        for dep in sorted(wire_deps.get(name, [])):
            if dep not in visited_topo:
                dfs_topo(dep)
        post_order.append(name)

    for w in wires:
        if w.name not in visited_topo:
            dfs_topo(w.name)

    wire_by_name = {w.name: w for w in wires}
    return [wire_by_name[name] for name in post_order]
