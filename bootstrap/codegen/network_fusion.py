import re

class NetworkFusion:
    def __init__(self, cg):
        self.cg = cg

    def fuse_node(self, nid: str, m, in_val: str, next_bb: str, phi_inst: str = None) -> tuple[list[str], list[tuple[str, str]]]:
        pname = m.params[0].name if m.params else None
        param_map = {pname: in_val} if pname else {}
        raw_lines = self.cg.gen_machine(m, param_map)[1:-1]

        fused_lines, ret_incomings = [], []
        curr_bb = ""

        for line in raw_lines:
            m_lbl = re.match(r'^([a-zA-Z0-9_]+):', line)
            if m_lbl:
                orig_lbl = m_lbl.group(1)
                curr_bb = f"{nid}_{orig_lbl}"
                fused_lines.append(f"{curr_bb}:")
                if orig_lbl == "entry" and phi_inst:
                    fused_lines.append(f"  {phi_inst}")
                continue

            m_ret = re.match(r'^\s*ret\s+([a-zA-Z0-9_*%]+)\s+(.+)$', line)
            if m_ret and next_bb:
                ret_val = m_ret.group(2).strip().replace("%reg_", f"%reg_{nid}_")
                ret_incomings.append((curr_bb, ret_val))
                fused_lines.append(f"  br label %{next_bb}")
                continue

            mod_line = re.sub(r'label %([a-zA-Z0-9_]+)', lambda ma: f"label %{nid}_{ma.group(1)}", line)
            mod_line = re.sub(r'\[\s*([^,]+),\s*%([a-zA-Z0-9_]+)\s*\]', lambda ma: f"[ {ma.group(1)}, %{nid}_{ma.group(2)} ]", mod_line)
            mod_line = mod_line.replace("%reg_", f"%reg_{nid}_")
            fused_lines.append(mod_line)

        return fused_lines, ret_incomings
