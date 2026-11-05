def verify_pipeline(net, pipe, machines: dict):
    for n in net.nodes:
        if n.machine_name not in machines:
            raise TypeError(f"Unknown machine '{n.machine_name}' in node declaration '{n.node_id}' of network '{net.name}'")

    node_map = {n.node_id: machines[n.machine_name] for n in net.nodes}
    param_map = {p.name: p.type_str for p in net.params}
    src_name = pipe.elements[0]
    if src_name not in param_map:
        raise TypeError(f"Unknown pipeline source '{src_name}' in network '{net.name}'")
    curr_type = param_map[src_name]
    visited_nodes: set[str] = set()

    for elem in pipe.elements[1:]:
        if elem not in node_map:
            raise TypeError(f"Unknown node identifier '{elem}' in pipeline of network '{net.name}'")
        if elem in visited_nodes:
            raise TypeError(f"Cycle or duplicate node '{elem}' detected in pipeline of network '{net.name}'")
        visited_nodes.add(elem)

        target_m = node_map[elem]
        if len(target_m.params) != 1:
            raise TypeError(f"Node '{elem}' ({target_m.name}) must have exactly 1 parameter for serial pipeline, got {len(target_m.params)}")
        expected_type = target_m.params[0].type_str
        if curr_type != expected_type:
            raise TypeError(f"Pipeline type mismatch in network '{net.name}': incoming wire has type '{curr_type}', but node '{elem}' ({target_m.name}) expects '{expected_type}'")
        curr_type = target_m.ret_type

    if curr_type != net.ret_type:
        raise TypeError(f"Network return type mismatch: pipeline outputs '{curr_type}', but network '{net.name}' declares return type '{net.ret_type}'")
    unconnected = set(node_map.keys()) - visited_nodes
    if unconnected:
        raise TypeError(f"Node(s) {unconnected} declared but never connected in pipeline of network '{net.name}'")

class NetworkChecker:
    def __init__(self, machines: dict):
        self.machines = machines

    def check_network(self, net):
        for pipe in net.pipelines:
            verify_pipeline(net, pipe, self.machines)
