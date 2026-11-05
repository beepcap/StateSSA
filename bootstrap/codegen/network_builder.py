from .network_fusion import NetworkFusion

class NetworkBuilder:
    def __init__(self, cg):
        self.cg = cg
        self.fusion = NetworkFusion(cg)

    def build_network(self, net, machines: dict) -> list[str]:
        pipe = net.pipelines[0]
        nodes = [(elem, machines[next(n.machine_name for n in net.nodes if n.node_id == elem)]) for elem in pipe.elements[1:]]
        ret_type = self.cg.map_type(net.ret_type)
        params = ", ".join(f"{self.cg.map_type(p.type_str)} %arg_{p.name}" for p in net.params)
        lines = [f"define {ret_type} @{net.name}({params}) {{", "net_entry:", f"  br label %{nodes[0][0]}_entry\n"]

        curr_in = f"%arg_{pipe.elements[0]}"
        pending_phi = None

        for idx, (nid, m) in enumerate(nodes):
            is_last = (idx == len(nodes) - 1)
            next_bb = f"{nodes[idx+1][0]}_entry" if not is_last else ""
            node_lines, incomings = self.fusion.fuse_node(nid, m, curr_in, next_bb, pending_phi)
            lines.extend(node_lines)

            if not is_last:
                out_type = self.cg.map_type(m.ret_type)
                res_var = f"%{nid}_res"
                phi_args = ", ".join(f"[ {v}, %{b} ]" for b, v in incomings)
                pending_phi = f"{res_var} = phi {out_type} {phi_args}"
                curr_in = res_var

        lines.append("}\n")
        return lines
