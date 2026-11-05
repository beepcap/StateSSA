from ..ast_nodes import Program
from .type_registry import TypeRegistry
from .annotations import TypeAnnotations
from .machine_checker import MachineChecker
from .distinct_checker import DistinctChecker
from .node_sealer import NodeSealer
from .network_checker import NetworkChecker

class SemanticAnalyzer:
    def __init__(self, prog: Program):
        self.prog = prog
        self.registry = TypeRegistry()

    def analyze(self) -> TypeAnnotations:
        self.registry.register_all(self.prog.types)
        annotations = TypeAnnotations(type_registry=self.registry.types)
        funcs = {ext.name: (("q64" if ext.ret_type in ("f32", "f64") else ext.ret_type), [pt for _, pt in ext.params]) for ext in self.prog.externs}
        funcs.update({m.name: (m.ret_type, [pt for _, pt in m.params]) for m in self.prog.machines})
        funcs.update({net.name: (net.ret_type, [p.type_str for p in net.params]) for net in self.prog.networks})
        sealer = NodeSealer(self.prog.networks)
        sealer.verify_program(self.prog)
        net_checker = NetworkChecker({m.name: m for m in self.prog.machines})
        for net in self.prog.networks:
            net_checker.check_network(net)
        checker = MachineChecker(self.registry, annotations, funcs)
        d_checker = DistinctChecker({m.name: m for m in self.prog.machines})
        for m in self.prog.machines:
            checker.check_machine(m)
            d_checker.check_machine(m, self.registry)
        return annotations
