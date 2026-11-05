import codecs
import os
from typing import Optional, Any
from .ast_nodes import Program, Machine, State, Rule, Action, TypeDef, ExternFn, TypeKind, Reg
from .expr_nodes import BinaryExpr, UnaryExpr, CallExpr, FieldExpr, StructLit, VarExpr, IntLit, StringLit, NullLit, CastExpr, Q64Lit, FloatLit
from .types import BoundedType

__path__ = [os.path.join(os.path.dirname(__file__), "codegen")]
from .codegen.network_builder import NetworkBuilder

class CodeGen:
    def __init__(self, prog: Program, annotations: Optional[Any] = None):
        self.prog = prog
        self.annotations = annotations
        self.tmp_id = 0
        self.str_id = 0
        self.string_constants: list[tuple[str, str, int]] = [] # (sym_name, str_val, byte_len)
        self.type_map = {
            "i32": "i32",
            "*i32": "i32*",
            "u32": "i32",
            "*u32": "i32*",
            "i64": "i64",
            "*i64": "i64*",
            "u64": "i64",
            "*u64": "i64*",
            "u16": "i16",
            "*u16": "i16*",
            "i16": "i16",
            "*i16": "i16*",
            "u8": "i8",
            "*u8": "i8*",
            "i8": "i8",
            "*i8": "i8*",
            "*void": "i8*",
            "void": "void",
            "q64": "i64",
            "*q64": "i64*",
            "f32": "float",
            "*f32": "float*",
            "f64": "double",
            "*f64": "double*",
            # SIMD Vector Types
            "f32x4": "<4 x float>",
            "*f32x4": "<4 x float>*",
            "f32x8": "<8 x float>",
            "*f32x8": "<8 x float>*",
            "f32x16": "<16 x float>",
            "*f32x16": "<16 x float>*",
            "f64x2": "<2 x double>",
            "*f64x2": "<2 x double>*",
            "f64x4": "<4 x double>",
            "*f64x4": "<4 x double>*",
            "f64x8": "<8 x double>",
            "*f64x8": "<8 x double>*",
            "i32x4": "<4 x i32>",
            "*i32x4": "<4 x i32>*",
            "i32x8": "<8 x i32>",
            "*i32x8": "<8 x i32>*",
            "i32x16": "<16 x i32>",
            "*i32x16": "<16 x i32>*",
            "u8x16": "<16 x i8>",
            "*u8x16": "<16 x i8>*",
            "u8x32": "<32 x i8>",
            "*u8x32": "<32 x i8>*",
            "u8x64": "<64 x i8>",
            "*u8x64": "<64 x i8>*",
        }
        self.struct_def: dict[str, list[tuple[str, str]]] = {}
        self.newtype_base_map: dict[str, str] = {}
        self.bounded_types: dict[str, BoundedType] = {}
        if annotations and hasattr(annotations, "type_registry") and annotations.type_registry:
            for tname, tobj in annotations.type_registry.items():
                if isinstance(tobj, BoundedType):
                    self.bounded_types[tname] = tobj
                    self.newtype_base_map[tname] = tobj.unwrap().to_str()

        for t in prog.types:
            if hasattr(t, "kind") and t.kind in (TypeKind.NEWTYPE, TypeKind.BOUNDED):
                self.newtype_base_map[t.name] = t.base_type
            elif t.fields and t.fields[0][0] == "__ptr__":
                self.newtype_base_map[t.name] = t.fields[0][1]
            else:
                self.type_map[t.name] = f"%struct.{t.name}"
                self.type_map[f"*{t.name}"] = f"%struct.{t.name}*"
                self.struct_def[t.name] = t.fields

    def resolve_base_primitive_name(self, tname: str) -> str:
        curr = tname
        visited = set()
        while curr in self.newtype_base_map and curr not in visited:
            visited.add(curr)
            curr = self.newtype_base_map[curr]
        return curr

    def emit_reg_default_val(self, reg: Reg) -> str:
        if reg.type_str in self.bounded_types:
            btype = self.bounded_types[reg.type_str]
            base = btype.unwrap().to_str()
            min_v, max_v = btype.min_val, btype.max_val
            if min_v <= 0 <= max_v:
                return "0.0" if base in ("f32", "f64") else "0"
            elif min_v > 0:
                return str(float(min_v)) if base in ("f32", "f64") else str(int(min_v))
            else:
                return str(float(max_v)) if base in ("f32", "f64") else str(int(max_v))
        base = self.resolve_base_primitive_name(reg.type_str)
        if base.startswith("*"):
            return "null"
        elif base in ("f32", "f64"):
            return "0.0"
        elif base == "q64":
            return "0"
        else:
            return "0"

    def emit_clamp(self, val: str, btype: BoundedType, insts: list[str]) -> str:
        base = btype.unwrap().to_str()
        llvm_type = self.map_type(base)

        if base in ("f32", "f64"):
            intrin_max = f"@llvm.maxnum.{base}"
            intrin_min = f"@llvm.minnum.{base}"
            if base == "f32":
                min_c = self.fresh_tmp("c_min")
                max_c = self.fresh_tmp("c_max")
                insts.append(f"{min_c} = fptrunc double {float(btype.min_val)} to float")
                insts.append(f"{max_c} = fptrunc double {float(btype.max_val)} to float")
                min_op, max_op = min_c, max_c
                if not val.startswith("%"):
                    c_val = self.fresh_tmp("c_val")
                    insts.append(f"{c_val} = fptrunc double {float(val)} to float")
                    val = c_val
            else:
                min_op = str(float(btype.min_val))
                max_op = str(float(btype.max_val))

            t1 = self.fresh_tmp("clamp_max")
            insts.append(f"{t1} = call {llvm_type} {intrin_max}({llvm_type} {val}, {llvm_type} {min_op})")
            t2 = self.fresh_tmp("clamped")
            insts.append(f"{t2} = call {llvm_type} {intrin_min}({llvm_type} {t1}, {llvm_type} {max_op})")
            return t2
        else:
            is_unsigned = base.startswith("u")
            cmp_lt = "ult" if is_unsigned else "slt"
            cmp_gt = "ugt" if is_unsigned else "sgt"
            min_lit = str(int(btype.min_val))
            max_lit = str(int(btype.max_val))

            c1 = self.fresh_tmp("cmp_min")
            insts.append(f"{c1} = icmp {cmp_lt} {llvm_type} {val}, {min_lit}")
            s1 = self.fresh_tmp("val_min")
            insts.append(f"{s1} = select i1 {c1}, {llvm_type} {min_lit}, {llvm_type} {val}")
            c2 = self.fresh_tmp("cmp_max")
            insts.append(f"{c2} = icmp {cmp_gt} {llvm_type} {s1}, {max_lit}")
            s2 = self.fresh_tmp("clamped")
            insts.append(f"{s2} = select i1 {c2}, {llvm_type} {max_lit}, {llvm_type} {s1}")
            return s2

    def fresh_tmp(self, prefix: str = "t") -> str:
        self.tmp_id += 1
        return f"%{prefix}_{self.tmp_id}"

    def map_type(self, t: str) -> str:
        if t in self.type_map:
            return self.type_map[t]
        if t.startswith("*"):
            return self.map_type(t[1:]) + "*"
        base = self.resolve_base_primitive_name(t)
        if base != t:
            return self.map_type(base)
        return self.type_map.get(t, t)

    def get_type_align(self, t: str) -> int:
        mapped = self.map_type(t)
        if "double" in mapped or "f64" in t or "i64" in t or "u64" in t:
            return 8
        elif "float" in mapped or "f32" in t or "i32" in t or "u32" in t:
            return 4
        elif "i16" in t or "u16" in t:
            return 2
        elif "i8" in t or "u8" in t:
            return 1
        return 4

    def generate(self) -> str:
        # First generate machines so string constants and types are collected
        sealed_machines = {node.machine_name for net in self.prog.networks for node in net.nodes}
        machine_lines = []
        for m in self.prog.machines:
            if m.name not in sealed_machines:
                machine_lines.extend(self.gen_machine(m))

        builder = NetworkBuilder(self)
        machine_dict = {m.name: m for m in self.prog.machines}
        for net in self.prog.networks:
            machine_lines.extend(builder.build_network(net, machine_dict))

        lines = []
        lines.append("; Generated by StateSSA Compiler (ssac)")
        lines.append('target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"')
        lines.append('target triple = "x86_64-pc-linux-gnu"\n')

        # String constants
        for sym, sval, slen in self.string_constants:
            # Escape for LLVM IR string literal
            escaped = sval.replace("\\n", "\\0A").replace('"', '\\22')
            lines.append(f'@{sym} = private unnamed_addr constant [{slen} x i8] c"{escaped}\\00", align 1')
        if self.string_constants: lines.append("")

        # 1. Type Definitions
        for t in self.prog.types:
            if t.name in self.struct_def:
                field_types = ", ".join(self.map_type(ft) for _, ft in t.fields)
                lines.append(f"%struct.{t.name} = type {{ {field_types} }}")
        if self.struct_def: lines.append("")

        # 2. Extern Declarations
        for ext in self.prog.externs:
            ret = self.map_type(ext.ret_type)
            params = ", ".join(
                f"{self.map_type(p.type_str)} noalias" if getattr(p, "is_distinct", False) else self.map_type(p.type_str if hasattr(p, "type_str") else p[1])
                for p in ext.params
            )
            lines.append(f"declare {ret} @{ext.name}({params})")
        if self.prog.externs: lines.append("")

        lines.append("declare void @llvm.trap() cold noreturn nounwind")
        lines.append("declare float @llvm.maxnum.f32(float, float)")
        lines.append("declare float @llvm.minnum.f32(float, float)")
        lines.append("declare double @llvm.maxnum.f64(double, double)")
        lines.append("declare double @llvm.minnum.f64(double, double)\n")

        # 3. Machines
        lines.extend(machine_lines)

        return "\n".join(lines)

    def gen_machine(self, m: Machine, param_map: Optional[dict[str, str]] = None) -> list[str]:
        # Spec V0.8 Verification:
        # 1. First state must be named 'Entry'
        if not m.states or m.states[0].name != "Entry":
            first_name = m.states[0].name if m.states else "None"
            raise SyntaxError(f"Machine '{m.name}' first state must be named 'Entry', got '{first_name}' (SPEC_V0_8)")

        # 2. No transitions to 'Entry' allowed
        for s in m.states:
            for r in s.rules:
                if r.target == "Entry":
                    raise SyntaxError(f"Machine '{m.name}' has illegal transition to 'Entry' in state '{s.name}' (Entry block cannot have incoming edges)")

        lines = []
        ret_type = self.map_type(m.ret_type)
        param_strs = []
        for p in m.params:
            pn, pt = p[0], p[1]
            attr = " noalias" if getattr(p, "is_distinct", False) else ""
            param_strs.append(f"{self.map_type(pt)}{attr} %arg_{pn}")
        params = ", ".join(param_strs)
        lines.append(f"define {ret_type} @{m.name}({params}) {{")

        phi_incoming: dict[str, dict[str, list[tuple[str, str]]]] = {
            s.name: {r.name: [] for r in m.flow.regs} for s in m.states
        }
        bb_insts: dict[str, list[str]] = {}
        bb_order: list[str] = []
        bb_env: dict[str, dict[str, str]] = {}
        self.var_allocas: dict[str, tuple[str, str]] = {} # var_name -> (alloca_ptr, struct_type)
        self.local_types: dict[str, str] = {}
        for s in m.states:
            for act in s.actions:
                if act.kind == "let" and act.target:
                    self.local_types[act.target] = self.get_expr_type(act.expr, m)

        # Entry Block
        entry_s = m.states[0]
        entry_bb = entry_s.name.lower()
        bb_order.append(entry_bb)
        bb_insts[entry_bb] = []
        bb_env[entry_bb] = {}

        self.param_bindings: dict[str, str] = {}
        for pn, pt in m.params:
            arg_src = param_map.get(pn, f"%arg_{pn}") if param_map else f"%arg_{pn}"
            if pt in self.bounded_types:
                clamped = self.emit_clamp(arg_src, self.bounded_types[pt], bb_insts[entry_bb])
                self.param_bindings[pn] = clamped
            else:
                self.param_bindings[pn] = arg_src

        for reg in m.flow.regs:
            if reg.init_expr is not None:
                if reg.type_str == "q64" and isinstance(reg.init_expr, FloatLit):
                    val = str(int(reg.init_expr.val * 4294967296))
                else:
                    val = self.emit_expr(reg.init_expr, m, bb_env[entry_bb], bb_insts[entry_bb])
                if reg.type_str in self.bounded_types:
                    val = self.emit_clamp(val, self.bounded_types[reg.type_str], bb_insts[entry_bb])
            else:
                val = self.emit_reg_default_val(reg)
            bb_env[entry_bb][reg.name] = val

        for s in m.states[1:]:
            s_bb = s.name.lower()
            bb_env[s_bb] = {}
            for reg in m.flow.regs:
                bb_env[s_bb][reg.name] = f"%reg_{reg.name}_{s_bb}"

        for s in m.states:
            curr_bb = s.name.lower()
            if curr_bb not in bb_insts:
                bb_order.append(curr_bb)
                bb_insts[curr_bb] = []

            for act in s.actions:
                if act.kind == "let":
                    res = self.emit_expr(act.expr, m, bb_env[curr_bb], bb_insts[curr_bb])
                    if act.target:
                        bb_env[curr_bb][act.target] = res
                elif act.kind == "call":
                    self.emit_expr(act.expr, m, bb_env[curr_bb], bb_insts[curr_bb])
                    # If call wrote to an alloca buffer, reload the value
                    for vname, (aptr, stype) in list(self.var_allocas.items()):
                        reloaded = self.fresh_tmp("reload")
                        bb_insts[curr_bb].append(f"{reloaded} = load {stype}, {stype}* {aptr}")
                        bb_env[curr_bb][vname] = reloaded
                elif act.kind == "store":
                    self.emit_store(act.target, act.expr, m, bb_env[curr_bb], bb_insts[curr_bb])

            for r_idx, r in enumerate(s.rules):
                if r.is_return:
                    if r.ret_expr is None or self.map_type(m.ret_type) == "void":
                        bb_insts[curr_bb].append("ret void")
                    else:
                        ret_val = self.emit_expr(r.ret_expr, m, bb_env[curr_bb], bb_insts[curr_bb])
                        expected_ret = self.map_type(m.ret_type)
                        actual_ret_ssa = self.get_expr_type(r.ret_expr, m)
                        actual_ret_llvm = self.map_type(actual_ret_ssa)
                        if expected_ret != actual_ret_llvm:
                            if expected_ret in ("i32", "i16", "i8") and actual_ret_llvm == "i64":
                                tr_val = self.fresh_tmp("trunc")
                                bb_insts[curr_bb].append(f"{tr_val} = trunc i64 {ret_val} to {expected_ret}")
                                ret_val = tr_val
                            elif expected_ret == "i64" and actual_ret_llvm in ("i32", "i16", "i8"):
                                ext_val = self.fresh_tmp("zext")
                                bb_insts[curr_bb].append(f"{ext_val} = zext {actual_ret_llvm} {ret_val} to i64")
                                ret_val = ext_val
                            elif expected_ret.endswith("*") and actual_ret_llvm.endswith("*"):
                                bc_val = self.fresh_tmp("bitcast")
                                bb_insts[curr_bb].append(f"{bc_val} = bitcast {actual_ret_llvm} {ret_val} to {expected_ret}")
                                ret_val = bc_val
                        if m.ret_type in self.bounded_types:
                            ret_val = self.emit_clamp(ret_val, self.bounded_types[m.ret_type], bb_insts[curr_bb])
                        bb_insts[curr_bb].append(f"ret {expected_ret} {ret_val}")
                    break
                elif r.is_panic:
                    bb_insts[curr_bb].append("call void @llvm.trap()")
                    bb_insts[curr_bb].append("unreachable")
                    break

                target_bb = r.target.lower()
                if r.guard is not None:
                    guard_type = self.get_expr_type(r.guard, m)
                    if guard_type.startswith("<") and "x i1>" in guard_type:
                        raise TypeError(f"Vector comparison ({guard_type}) cannot be used directly as a state transition guard (SPEC_V0_14)")
                    cond_val = self.emit_expr(r.guard, m, bb_env[curr_bb], bb_insts[curr_bb])
                    then_bb = f"{curr_bb}_then_{r_idx}"
                    else_bb = f"{curr_bb}_else_{r_idx}"
                    bb_insts[curr_bb].append(f"br i1 {cond_val}, label %{then_bb}, label %{else_bb}")

                    bb_order.append(then_bb)
                    bb_insts[then_bb] = []
                    bb_env[then_bb] = dict(bb_env[curr_bb])
                    self.record_latches(r, m, then_bb, target_bb, bb_env, bb_insts, phi_incoming)
                    bb_insts[then_bb].append(f"br label %{target_bb}")

                    bb_order.append(else_bb)
                    bb_insts[else_bb] = []
                    bb_env[else_bb] = dict(bb_env[curr_bb])
                    curr_bb = else_bb
                else:
                    self.record_latches(r, m, curr_bb, target_bb, bb_env, bb_insts, phi_incoming)
                    bb_insts[curr_bb].append(f"br label %{target_bb}")
                    break

        for bb in bb_order:
            lines.append(f"{bb}:")
            matching_state = next((s for s in m.states[1:] if s.name.lower() == bb), None)
            if matching_state:
                for reg in m.flow.regs:
                    incomings = phi_incoming[matching_state.name][reg.name]
                    if incomings:
                        rtype = self.map_type(reg.type_str)
                        phi_name = f"%reg_{reg.name}_{bb}"
                        in_str = ", ".join(f"[ {v}, %{from_b} ]" for from_b, v in incomings)
                        lines.append(f"  {phi_name} = phi {rtype} {in_str}")

            for inst in bb_insts[bb]:
                lines.append(f"  {inst}")

        lines.append("}\n")
        return lines

    def record_latches(self, r: Rule, m: Machine, from_bb: str, target_bb: str,
                       bb_env: dict, bb_insts: dict, phi_incoming: dict):
        target_s = next((s for s in m.states if s.name.lower() == target_bb), None)
        if not target_s: return

        latch_map = {rname: lexpr for rname, lexpr in r.latches}
        for reg in m.flow.regs:
            if reg.type_str.startswith("*"):
                default_val = "null"
            elif reg.type_str in ("f32", "f64"):
                default_val = "0.0"
            elif "x" in reg.type_str:
                default_val = "zeroinitializer"
            else:
                default_val = "0"
            if reg.name in latch_map:
                lexpr = latch_map[reg.name]
                if self.resolve_base_primitive_name(reg.type_str) == "q64" and isinstance(lexpr, FloatLit):
                    val = str(int(lexpr.val * 4294967296))
                else:
                    val = self.emit_expr(lexpr, m, bb_env[from_bb], bb_insts[from_bb])
                rtype = self.map_type(reg.type_str)
                ltype = self.map_type(self.get_expr_type(lexpr, m))
                if rtype != ltype:
                    if rtype in ("i32", "i16", "i8") and ltype == "i64":
                        tr_val = self.fresh_tmp("trunc")
                        bb_insts[from_bb].append(f"{tr_val} = trunc i64 {val} to {rtype}")
                        val = tr_val
                    elif rtype == "i64" and ltype in ("i32", "i16", "i8"):
                        ext_val = self.fresh_tmp("zext")
                        bb_insts[from_bb].append(f"{ext_val} = zext {ltype} {val} to i64")
                        val = ext_val
                    elif rtype.endswith("*") and ltype.endswith("*"):
                        bc_val = self.fresh_tmp("bitcast")
                        bb_insts[from_bb].append(f"{bc_val} = bitcast {ltype} {val} to {rtype}")
                        val = bc_val
                if reg.type_str in self.bounded_types:
                    val = self.emit_clamp(val, self.bounded_types[reg.type_str], bb_insts[from_bb])
            else:
                val = bb_env[from_bb].get(reg.name, default_val)
            phi_incoming[target_s.name][reg.name].append((from_bb, val))

    def is_unsigned_type(self, type_str: str) -> bool:
        if type_str in ("u8", "u16", "u32", "u64") or type_str.startswith("*"):
            return True
        return False

    def is_vector_type(self, type_str: str) -> bool:
        import re
        t = type_str[1:] if type_str.startswith("*") else type_str
        return bool(re.match(r'^(f32|f64|i32|i64|u8|u16|u32|u64)x\d+$', t))

    def emit_store(self, target, expr, m: Machine, env: dict[str, str], insts: list[str]):
        val = self.emit_expr(expr, m, env, insts)
        val_type = self.get_expr_type(expr, m)
        val_llvm = self.map_type(val_type)

        if isinstance(target, UnaryExpr) and target.op == "*":
            ptr = self.emit_expr(target.operand, m, env, insts)
            ptr_type = self.get_expr_type(target.operand, m)
            elem_type = ptr_type[1:] if ptr_type.startswith("*") else "i32"
            mapped_elem = self.map_type(elem_type)

            final_val = val
            if mapped_elem != val_llvm:
                if mapped_elem in ("i8", "i16", "i32") and val_llvm in ("i64", "i32", "i16"):
                    trunc_val = self.fresh_tmp("trunc")
                    insts.append(f"{trunc_val} = trunc {val_llvm} {val} to {mapped_elem}")
                    final_val = trunc_val
                elif mapped_elem == "i64" and val_type.startswith("*"):
                    cast_val = self.fresh_tmp("ptrtoint")
                    insts.append(f"{cast_val} = ptrtoint {val_llvm} {val} to i64")
                    final_val = cast_val
                elif mapped_elem == "i64" and val_llvm in ("i32", "i16", "i8"):
                    ext_val = self.fresh_tmp("zext")
                    insts.append(f"{ext_val} = zext {val_llvm} {val} to i64")
                    final_val = ext_val
                elif mapped_elem.endswith("*") and val_llvm.endswith("*"):
                    bc_val = self.fresh_tmp("bitcast")
                    insts.append(f"{bc_val} = bitcast {val_llvm} {val} to {mapped_elem}")
                    final_val = bc_val

            align = self.get_type_align(elem_type)
            insts.append(f"store {mapped_elem} {final_val}, {mapped_elem}* {ptr}, align {align}")
        elif isinstance(target, FieldExpr):
            fld_ptr, fld_ssa, fld_llvm = self.resolve_field_ptr(target, m, env, insts)

            final_val = val
            if fld_llvm != val_llvm:
                if fld_llvm in ("i8", "i16", "i32") and val_llvm in ("i64", "i32", "i16"):
                    trunc_val = self.fresh_tmp("trunc")
                    insts.append(f"{trunc_val} = trunc {val_llvm} {val} to {fld_llvm}")
                    final_val = trunc_val
                elif fld_llvm == "i64" and val_type.startswith("*"):
                    cast_val = self.fresh_tmp("ptrtoint")
                    insts.append(f"{cast_val} = ptrtoint {val_llvm} {val} to i64")
                    final_val = cast_val
                elif fld_llvm == "i64" and val_llvm in ("i32", "i16", "i8"):
                    ext_val = self.fresh_tmp("zext")
                    insts.append(f"{ext_val} = zext {val_llvm} {val} to i64")
                    final_val = ext_val
                elif fld_llvm.endswith("*") and val_llvm.endswith("*"):
                    bc_val = self.fresh_tmp("bitcast")
                    insts.append(f"{bc_val} = bitcast {val_llvm} {val} to {fld_llvm}")
                    final_val = bc_val

            insts.append(f"store {fld_llvm} {final_val}, {fld_llvm}* {fld_ptr}")

    def resolve_field_ptr(self, expr: FieldExpr, m: Machine, env: dict[str, str], insts: list[str]) -> tuple[str, str, str]:
        if isinstance(expr.target, FieldExpr):
            base_ptr, base_ssa, base_llvm = self.resolve_field_ptr(expr.target, m, env, insts)
            struct_name = base_ssa[1:] if base_ssa.startswith("*") else base_ssa
        else:
            base_ssa = self.get_expr_type(expr.target, m)
            struct_name = base_ssa[1:] if base_ssa.startswith("*") else base_ssa
            base_ptr = self.emit_expr(expr.target, m, env, insts)

        if struct_name not in self.struct_def:
            raise RuntimeError(f"Type '{struct_name}' is not a declared struct in field access '{expr.field}'")

        fields = self.struct_def[struct_name]
        field_idx = -1
        field_ssa_type = None
        for i, (fn, ft) in enumerate(fields):
            if fn == expr.field:
                field_idx = i
                field_ssa_type = ft
                break

        if field_idx == -1:
            raise RuntimeError(f"Struct '{struct_name}' has no field '{expr.field}'")

        gep_res = self.fresh_tmp("fld_ptr")
        insts.append(f"{gep_res} = getelementptr inbounds %struct.{struct_name}, %struct.{struct_name}* {base_ptr}, i32 0, i32 {field_idx}")
        field_llvm_type = self.map_type(field_ssa_type)
        return gep_res, field_ssa_type, field_llvm_type

    def get_expr_type(self, expr, m: Machine) -> str:
        if self.annotations and id(expr) in self.annotations.expr_types:
            resolved_t = self.annotations.expr_types[id(expr)]
            return resolved_t.unwrap().to_str()
        if isinstance(expr, VarExpr):
            if expr.name == "null":
                return "*void"
            if hasattr(self, 'local_types') and expr.name in self.local_types:
                return self.local_types[expr.name]
            for pn, pt in m.params:
                if pn == expr.name: return pt
            for r in m.flow.regs:
                if r.name == expr.name: return r.type_str
            for w in m.flow.wires:
                if w.name == expr.name: return self.get_expr_type(w.expr, m)
            for tm in self.prog.machines:
                if tm.name == expr.name: return "*void"
            for ext in self.prog.externs:
                if ext.name == expr.name: return "*void"
            raise RuntimeError(f"Undefined variable '{expr.name}' in machine '{m.name}'")
        if isinstance(expr, CallExpr):
            for target_m in self.prog.machines:
                if target_m.name == expr.func:
                    return target_m.ret_type
            for net in self.prog.networks:
                if net.name == expr.func:
                    return net.ret_type
            for ext in self.prog.externs:
                if ext.name == expr.func:
                    if ext.ret_type in ("f32", "f64"):
                        return "q64"
                    return ext.ret_type
        if isinstance(expr, FieldExpr):
            # Lookup struct
            stype = self.get_expr_type(expr.target, m)
            sname = stype[1:] if stype.startswith("*") else stype
            if sname not in self.struct_def:
                raise RuntimeError(f"Cannot resolve struct type '{sname}' for field access '{expr.field}'")
            for fn, ft in self.struct_def[sname]:
                if fn == expr.field: return ft
            raise RuntimeError(f"Struct '{sname}' has no field '{expr.field}'")
        if isinstance(expr, UnaryExpr):
            if expr.op == "-": return self.get_expr_type(expr.operand, m)
            if expr.op == "&": return f"*{self.get_expr_type(expr.operand, m)}"
            if expr.op == "*":
                sub = self.get_expr_type(expr.operand, m)
                return sub[1:] if sub.startswith("*") else "i32"

        if isinstance(expr, StructLit):
            return expr.type_name
        if isinstance(expr, CastExpr):
            return expr.target_type
        if isinstance(expr, Q64Lit):
            return "q64"
        if isinstance(expr, FloatLit):
            return "f32"
        if isinstance(expr, IntLit):
            if expr.val > 4294967295 or expr.val < -2147483648:
                return "i64"
            return "i32"
        if isinstance(expr, StringLit):
            return "*u8"
        if isinstance(expr, NullLit):
            return "*void"
        if isinstance(expr, BinaryExpr):
            lt = self.get_expr_type(expr.left, m)
            rt = self.get_expr_type(expr.right, m)
            base_lt = self.resolve_base_primitive_name(lt)
            base_rt = self.resolve_base_primitive_name(rt)
            if expr.op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                if self.is_vector_type(base_lt):
                    num = base_lt.split('x')[1]
                    return f"<{num} x i1>"
                return "i1"
            if expr.op in ("&", "|", "^") and base_lt == "i1" and base_rt == "i1":
                return "i1"
            if expr.op == "+":
                if base_lt.startswith("*"): return lt
            if self.is_vector_type(base_lt): return base_lt
            if self.is_vector_type(base_rt): return base_rt
            if base_lt == "f64" or base_rt == "f64": return "f64"
            if base_lt == "f32" or base_rt == "f32": return "f32"
            if base_lt == "q64" or base_rt == "q64": return "q64"
            if base_lt in ("i64", "u64") or base_rt in ("i64", "u64"):
                return "u64" if (base_lt == "u64" or base_rt == "u64") else "i64"
            if base_lt in ("u32", "u16", "u8") or base_rt in ("u32", "u16", "u8"):
                return "u32"
            return "i32"

    def emit_expr(self, expr, m: Machine, env: dict[str, str], insts: list[str]) -> str:
        if isinstance(expr, VarExpr):
            if expr.name == "null":
                return "null"
            if hasattr(self, "param_bindings") and expr.name in self.param_bindings:
                return self.param_bindings[expr.name]
            for pn, _ in m.params:
                if pn == expr.name:
                    return f"%arg_{pn}"
            if expr.name in env:
                return env[expr.name]
            for w in m.flow.wires:
                if w.name == expr.name:
                    res = self.emit_expr(w.expr, m, env, insts)
                    env[w.name] = res
                    return res
            for tm in self.prog.machines:
                if tm.name == expr.name:
                    return f"@{expr.name}"
            for ext in self.prog.externs:
                if ext.name == expr.name:
                    return f"@{expr.name}"
            raise RuntimeError(f"Undefined operand variable '{expr.name}' in machine '{m.name}'")

        if isinstance(expr, NullLit):
            return "null"

        if isinstance(expr, IntLit):
            return str(expr.val)

        if isinstance(expr, Q64Lit):
            return str(expr.val)

        if isinstance(expr, FloatLit):
            val_str = str(expr.val)
            if "." not in val_str and "e" not in val_str:
                val_str += ".0"
            return val_str

        if isinstance(expr, StringLit):
            self.str_id += 1
            sym = f".str_{self.str_id}"
            raw_bytes, _ = codecs.escape_decode(expr.val.encode('utf-8'))
            byte_len = len(raw_bytes) + 1
            self.string_constants.append((sym, expr.val, byte_len))
            res = self.fresh_tmp("str")
            insts.append(f"{res} = getelementptr inbounds [{byte_len} x i8], [{byte_len} x i8]* @{sym}, i64 0, i64 0")
            return res

        if isinstance(expr, BinaryExpr):
            left = self.emit_expr(expr.left, m, env, insts)
            right = self.emit_expr(expr.right, m, env, insts)
            
            left_type = self.get_expr_type(expr.left, m)
            right_type = self.get_expr_type(expr.right, m)
            if left_type.startswith("*") and expr.op == "+":
                elem_type = self.map_type(left_type[1:])
                res = self.fresh_tmp("gep")
                insts.append(f"{res} = getelementptr inbounds {elem_type}, {elem_type}* {left}, i32 {right}")
                return res
            if left_type.startswith("*") and right_type.startswith("*") and expr.op == "-":
                t1 = self.fresh_tmp("p2i")
                t2 = self.fresh_tmp("p2i")
                insts.append(f"{t1} = ptrtoint {self.map_type(left_type)} {left} to i32")
                insts.append(f"{t2} = ptrtoint {self.map_type(right_type)} {right} to i32")
                res = self.fresh_tmp("diff")
                insts.append(f"{res} = sub i32 {t1}, {t2}")
                return res

            if (left_type.startswith("*") or right_type.startswith("*")) and expr.op in ("==", "!="):
                cmp_op = "eq" if expr.op == "==" else "ne"
                res = self.fresh_tmp("pcmp")
                insts.append(f"{res} = icmp {cmp_op} ptr {left}, {right}")
                return res

            # Floating-point and SIMD vector operations
            base_left = self.resolve_base_primitive_name(left_type)
            base_right = self.resolve_base_primitive_name(right_type)
            is_fp = base_left in ("f32", "f64") or base_right in ("f32", "f64")
            is_vec = self.is_vector_type(base_left) or self.is_vector_type(base_right)
            if is_fp or is_vec:
                target_type = left_type if (self.is_vector_type(base_left) or base_left in ("f32", "f64")) else right_type
                llvm_t = self.map_type(target_type)
                res = self.fresh_tmp("fop" if is_fp else "vop")
                is_fp_elem = "float" in llvm_t or "double" in llvm_t
                if is_fp_elem:
                    fp_op_map = {
                        "+": f"fadd {llvm_t}", "-": f"fsub {llvm_t}",
                        "*": f"fmul {llvm_t}", "/": f"fdiv {llvm_t}",
                        "==": f"fcmp oeq {llvm_t}", "!=": f"fcmp one {llvm_t}",
                        "<": f"fcmp olt {llvm_t}", "<=": f"fcmp ole {llvm_t}",
                        ">": f"fcmp ogt {llvm_t}", ">=": f"fcmp oge {llvm_t}",
                    }
                    instr = fp_op_map.get(expr.op)
                    if instr:
                        insts.append(f"{res} = {instr} {left}, {right}")
                        return res
                else:
                    int_vec_map = {
                        "+": f"add {llvm_t}", "-": f"sub {llvm_t}",
                        "*": f"mul {llvm_t}", "/": f"sdiv {llvm_t}",
                        "&": f"and {llvm_t}", "|": f"or {llvm_t}", "^": f"xor {llvm_t}",
                        "<<": f"shl {llvm_t}", ">>": f"ashr {llvm_t}",
                        "==": f"icmp eq {llvm_t}", "!=": f"icmp ne {llvm_t}",
                        "<": f"icmp slt {llvm_t}", "<=": f"icmp sle {llvm_t}",
                        ">": f"icmp sgt {llvm_t}", ">=": f"icmp sge {llvm_t}",
                    }
                    instr = int_vec_map.get(expr.op)
                    if instr:
                        insts.append(f"{res} = {instr} {left}, {right}")
                        return res

            if left_type in ("i64", "u64", "q64") or right_type in ("i64", "u64", "q64"):
                bin_type = "i64"
                if left_type == "q64" or right_type == "q64":
                    if isinstance(expr.left, FloatLit):
                        left = str(int(expr.left.val * 4294967296))
                    if isinstance(expr.right, FloatLit):
                        right = str(int(expr.right.val * 4294967296))
            elif left_type == "i1" or right_type == "i1":
                bin_type = "i1"
            else:
                bin_type = "i32"
            left_llvm = self.map_type(left_type)
            right_llvm = self.map_type(right_type)
            if left_llvm != bin_type and not isinstance(expr.left, (IntLit, Q64Lit)):
                ext_left = self.fresh_tmp("ext")
                op_ext = "sext" if left_type in ("i8", "i16", "i32") else "zext"
                insts.append(f"{ext_left} = {op_ext} {left_llvm} {left} to {bin_type}")
                left = ext_left
            if right_llvm != bin_type and not isinstance(expr.right, (IntLit, Q64Lit)):
                ext_right = self.fresh_tmp("ext")
                op_ext = "sext" if right_type in ("i8", "i16", "i32") else "zext"
                insts.append(f"{ext_right} = {op_ext} {right_llvm} {right} to {bin_type}")
                right = ext_right

            # q64 special 128-bit multiplication and division
            if (left_type == "q64" or right_type == "q64") and expr.op in ("*", "/"):
                if expr.op == "*":
                    sext_l = self.fresh_tmp("qmul_l")
                    sext_r = self.fresh_tmp("qmul_r")
                    mul128 = self.fresh_tmp("qmul128")
                    shr128 = self.fresh_tmp("qmul_shr")
                    res = self.fresh_tmp("qmul_res")
                    insts.append(f"{sext_l} = sext i64 {left} to i128")
                    insts.append(f"{sext_r} = sext i64 {right} to i128")
                    insts.append(f"{mul128} = mul i128 {sext_l}, {sext_r}")
                    insts.append(f"{shr128} = ashr i128 {mul128}, 32")
                    insts.append(f"{res} = trunc i128 {shr128} to i64")
                    return res
                elif expr.op == "/":
                    sext_l = self.fresh_tmp("qdiv_l")
                    shl128 = self.fresh_tmp("qdiv_shl")
                    sext_r = self.fresh_tmp("qdiv_r")
                    div128 = self.fresh_tmp("qdiv128")
                    res = self.fresh_tmp("qdiv_res")
                    insts.append(f"{sext_l} = sext i64 {left} to i128")
                    insts.append(f"{shl128} = shl i128 {sext_l}, 32")
                    insts.append(f"{sext_r} = sext i64 {right} to i128")
                    insts.append(f"{div128} = sdiv i128 {shl128}, {sext_r}")
                    insts.append(f"{res} = trunc i128 {div128} to i64")
                    return res

            is_unsigned = self.is_unsigned_type(self.get_expr_type(expr.left, m)) or self.is_unsigned_type(self.get_expr_type(expr.right, m))
            res = self.fresh_tmp()
            if is_unsigned:
                op_map = {
                    "+": f"add {bin_type}", "-": f"sub {bin_type}", "*": f"mul {bin_type}", "/": f"udiv {bin_type}",
                    "<<": f"shl {bin_type}", ">>": f"lshr {bin_type}",
                    "&": f"and {bin_type}", "|": f"or {bin_type}", "^": f"xor {bin_type}",
                    "==": f"icmp eq {bin_type}", "!=": f"icmp ne {bin_type}",
                    "<": f"icmp ult {bin_type}", "<=": f"icmp ule {bin_type}",
                    ">": f"icmp ugt {bin_type}", ">=": f"icmp uge {bin_type}",
                    "||": "or i1", "&&": "and i1"
                }
            else:
                op_map = {
                    "+": f"add {bin_type}", "-": f"sub {bin_type}", "*": f"mul {bin_type}", "/": f"sdiv {bin_type}",
                    "<<": f"shl {bin_type}", ">>": f"ashr {bin_type}",
                    "&": f"and {bin_type}", "|": f"or {bin_type}", "^": f"xor {bin_type}",
                    "==": f"icmp eq {bin_type}", "!=": f"icmp ne {bin_type}",
                    "<": f"icmp slt {bin_type}", "<=": f"icmp sle {bin_type}",
                    ">": f"icmp sgt {bin_type}", ">=": f"icmp sge {bin_type}",
                    "||": "or i1", "&&": "and i1"
                }
            instr = op_map.get(expr.op, "add i32")
            insts.append(f"{res} = {instr} {left}, {right}")
            return res

        if isinstance(expr, UnaryExpr):
            if expr.op == "-":
                sub = self.emit_expr(expr.operand, m, env, insts)
                sub_type = self.get_expr_type(expr.operand, m)
                base = self.resolve_base_primitive_name(sub_type)
                llvm_t = self.map_type(sub_type)
                if base in ("f32", "f64") or "float" in llvm_t or "double" in llvm_t:
                    res = self.fresh_tmp("fneg")
                    insts.append(f"{res} = fneg {llvm_t} {sub}")
                    return res
                else:
                    res = self.fresh_tmp("neg")
                    insts.append(f"{res} = sub {llvm_t} 0, {sub}")
                    return res
            if expr.op == "*":
                sub = self.emit_expr(expr.operand, m, env, insts)
                ptr_type = self.get_expr_type(expr.operand, m)
                elem_type = ptr_type[1:] if ptr_type.startswith("*") else "i32"
                mapped_elem = self.map_type(elem_type)
                
                raw_load = self.fresh_tmp("load")
                align = self.get_type_align(elem_type)
                insts.append(f"{raw_load} = load {mapped_elem}, {mapped_elem}* {sub}, align {align}")
                return raw_load
            elif expr.op == "&":
                if isinstance(expr.operand, FieldExpr):
                    fld_ptr, fld_ssa, fld_llvm = self.resolve_field_ptr(expr.operand, m, env, insts)
                    return fld_ptr

                var_name = getattr(expr.operand, 'name', None)
                for target_m in self.prog.machines:
                    if target_m.name == var_name:
                        res = self.fresh_tmp("fn_ptr")
                        insts.append(f"{res} = bitcast {self.map_type(target_m.ret_type)} ({', '.join(self.map_type(pt) for _, pt in target_m.params)})* @{target_m.name} to i8*")
                        return res
                
                var_type = self.get_expr_type(expr.operand, m)
                struct_type = self.map_type(var_type)
                val = self.emit_expr(expr.operand, m, env, insts)
                alloca_res = self.fresh_tmp("alloca")
                cast_res = self.fresh_tmp("cast")
                insts.append(f"{alloca_res} = alloca {struct_type}, align 8")
                insts.append(f"store {struct_type} {val}, {struct_type}* {alloca_res}")
                insts.append(f"{cast_res} = bitcast {struct_type}* {alloca_res} to i8*")
                self.var_allocas[var_name] = (alloca_res, struct_type)
                return cast_res

        if isinstance(expr, StructLit):
            struct_type = f"%struct.{expr.type_name}"
            fields = self.struct_def.get(expr.type_name, [])
            curr = "undef"
            for idx, (fname, fexpr) in enumerate(expr.fields):
                fval = self.emit_expr(fexpr, m, env, insts)
                ftype = "i32"
                for df_name, df_type in fields:
                    if df_name == fname:
                        ftype = self.map_type(df_type)
                        break
                next_val = self.fresh_tmp("ins")
                insts.append(f"{next_val} = insertvalue {struct_type} {curr}, {ftype} {fval}, {idx}")
                curr = next_val
            return curr

        if isinstance(expr, FieldExpr):
            fld_ptr, fld_ssa, fld_llvm = self.resolve_field_ptr(expr, m, env, insts)
            if fld_ssa in self.struct_def:
                load_res = self.fresh_tmp("struct_val")
                insts.append(f"{load_res} = load {fld_llvm}, {fld_llvm}* {fld_ptr}")
                return load_res
            else:
                load_res = self.fresh_tmp("fld_val")
                insts.append(f"{load_res} = load {fld_llvm}, {fld_llvm}* {fld_ptr}")
                return load_res

        if isinstance(expr, CallExpr):
            ret_type = "void"
            param_types = []
            raw_param_types = []
            for ext in self.prog.externs:
                if ext.name == expr.func:
                    ret_type = self.map_type(ext.ret_type)
                    raw_param_types = [pt for _, pt in ext.params]
                    param_types = [self.map_type(pt) for pt in raw_param_types]
                    break
            for mach in self.prog.machines:
                if mach.name == expr.func:
                    ret_type = self.map_type(mach.ret_type)
                    raw_param_types = [pt for _, pt in mach.params]
                    param_types = [self.map_type(pt) for pt in raw_param_types]
                    break
            for net in self.prog.networks:
                if net.name == expr.func:
                    ret_type = self.map_type(net.ret_type)
                    raw_param_types = [p.type_str for p in net.params]
                    param_types = [self.map_type(pt) for pt in raw_param_types]
                    break

            arg_vals = []
            for i, a in enumerate(expr.args):
                av = self.emit_expr(a, m, env, insts)
                if i < len(raw_param_types) and raw_param_types[i] in self.bounded_types:
                    av = self.emit_clamp(av, self.bounded_types[raw_param_types[i]], insts)
                if i < len(param_types):
                    expected_pt = param_types[i]
                    actual_ssa = self.get_expr_type(a, m)
                    actual_llvm = self.map_type(actual_ssa)
                    if expected_pt != actual_llvm:
                        if expected_pt == "double" and actual_ssa == "q64":
                            fp_raw = self.fresh_tmp("q2fp")
                            insts.append(f"{fp_raw} = sitofp i64 {av} to double")
                            fp_div = self.fresh_tmp("q2fp_div")
                            insts.append(f"{fp_div} = fdiv double {fp_raw}, 4294967296.0")
                            av = fp_div
                        elif expected_pt == "float" and actual_ssa == "q64":
                            fp_raw = self.fresh_tmp("q2fp")
                            insts.append(f"{fp_raw} = sitofp i64 {av} to float")
                            fp_div = self.fresh_tmp("q2fp_div")
                            insts.append(f"{fp_div} = fdiv float {fp_raw}, 4294967296.0")
                            av = fp_div
                        elif expected_pt == "i64" and actual_llvm in ("i32", "i16", "i8"):
                            ext_val = self.fresh_tmp("zext")
                            insts.append(f"{ext_val} = zext {actual_llvm} {av} to i64")
                            av = ext_val
                        elif expected_pt == "i64" and actual_ssa.startswith("*"):
                            cast_val = self.fresh_tmp("ptrtoint")
                            insts.append(f"{cast_val} = ptrtoint {actual_llvm} {av} to i64")
                            av = cast_val
                        elif expected_pt.endswith("*") and actual_llvm.endswith("*") and expected_pt != actual_llvm:
                            bc_val = self.fresh_tmp("bitcast")
                            insts.append(f"{bc_val} = bitcast {actual_llvm} {av} to {expected_pt}")
                            av = bc_val
                        elif expected_pt in ("i8", "i16") and actual_llvm == "i32":
                            tr_val = self.fresh_tmp("trunc")
                            insts.append(f"{tr_val} = trunc i32 {av} to {expected_pt}")
                            av = tr_val
                        elif expected_pt in ("i32", "u32") and actual_llvm in ("i8", "i16"):
                            ext_val = self.fresh_tmp("zext")
                            insts.append(f"{ext_val} = zext {actual_llvm} {av} to i32")
                            av = ext_val
                        elif expected_pt in ("i32", "i16", "i8") and actual_llvm == "i64":
                            tr_val = self.fresh_tmp("trunc")
                            insts.append(f"{tr_val} = trunc i64 {av} to {expected_pt}")
                            av = tr_val
                arg_vals.append(av)

            args_str = ", ".join(f"{pt} {av}" for pt, av in zip(param_types, arg_vals)) if param_types else ""
            if ret_type == "void":
                insts.append(f"call void @{expr.func}({args_str})")
                return "void"
            else:
                res = self.fresh_tmp()
                insts.append(f"{res} = call {ret_type} @{expr.func}({args_str})")
                if ret_type == "double":
                    mul_res = self.fresh_tmp("fp2q_mul")
                    insts.append(f"{mul_res} = fmul double {res}, 4294967296.0")
                    q_res = self.fresh_tmp("fp2q")
                    insts.append(f"{q_res} = fptosi double {mul_res} to i64")
                    return q_res
                elif ret_type == "float":
                    mul_res = self.fresh_tmp("fp2q_mul")
                    insts.append(f"{mul_res} = fmul float {res}, 4294967296.0")
                    q_res = self.fresh_tmp("fp2q")
                    insts.append(f"{q_res} = fptosi float {mul_res} to i64")
                    return q_res
                return res

        if isinstance(expr, CastExpr):
            raw_res = self._emit_cast_raw(expr, m, env, insts)
            if expr.target_type in self.bounded_types:
                return self.emit_clamp(raw_res, self.bounded_types[expr.target_type], insts)
            return raw_res

        return "0"

    def _emit_cast_raw(self, expr: CastExpr, m: Machine, env: dict[str, str], insts: list[str]) -> str:
        # 定数リテラルのゼロコスト文脈直接展開
        target_llvm = self.map_type(expr.target_type)
        if isinstance(expr.expr, FloatLit):
            if target_llvm == "float":
                tmp_f = self.fresh_tmp("lit_f32")
                insts.append(f"{tmp_f} = fptrunc double {expr.expr.val} to float")
                return tmp_f
            elif target_llvm == "double":
                return str(expr.expr.val)
            elif target_llvm == "i64" and self.resolve_base_primitive_name(expr.target_type) == "q64":
                return str(int(expr.expr.val * 4294967296))

        val = self.emit_expr(expr.expr, m, env, insts)
        from_type = self.get_expr_type(expr.expr, m)
        to_type = expr.target_type
        if from_type == to_type:
            return val

        from_llvm = self.map_type(from_type)
        to_llvm = self.map_type(to_type)
        if from_llvm == to_llvm:
            return val

        from_base = self.resolve_base_primitive_name(from_type)
        to_base = self.resolve_base_primitive_name(to_type)

        if to_base == "q64":
            if from_base in ("f32", "f64"):
                fval = val
                if from_base == "f32":
                    fpext = self.fresh_tmp("fpext")
                    insts.append(f"{fpext} = fpext float {val} to double")
                    fval = fpext
                fmul = self.fresh_tmp("fmul_q")
                insts.append(f"{fmul} = fmul double {fval}, 4294967296.0")
                q_res = self.fresh_tmp("fptosi_q")
                insts.append(f"{q_res} = fptosi double {fmul} to i64")
                return q_res
            if from_llvm != "i64":
                ext = self.fresh_tmp("ext_q")
                op = "sext" if from_base in ("i8", "i16", "i32") else "zext"
                insts.append(f"{ext} = {op} {from_llvm} {val} to i64")
                val = ext
            res = self.fresh_tmp("shl_q")
            insts.append(f"{res} = shl i64 {val}, 32")
            return res

        if from_base == "q64":
            if to_base in ("f32", "f64"):
                sitofp = self.fresh_tmp("q2fp")
                insts.append(f"{sitofp} = sitofp i64 {val} to double")
                q_div = self.fresh_tmp("q_div")
                insts.append(f"{q_div} = fdiv double {sitofp}, 4294967296.0")
                if to_base == "f32":
                    res = self.fresh_tmp("fptrunc")
                    insts.append(f"{res} = fptrunc double {q_div} to float")
                    return res
                return q_div
            shr = self.fresh_tmp("shr_q")
            insts.append(f"{shr} = ashr i64 {val}, 32")
            if to_llvm != "i64":
                res = self.fresh_tmp("trunc_q")
                insts.append(f"{res} = trunc i64 {shr} to {to_llvm}")
                return res
            return shr

        is_from_ptr = from_base.startswith("*")
        is_to_ptr = to_base.startswith("*")

        # Float <-> Float
        if from_base in ("f32", "f64") and to_base in ("f32", "f64"):
            if from_base == "f32" and to_base == "f64":
                res = self.fresh_tmp("fpext")
                insts.append(f"{res} = fpext float {val} to double")
                return res
            elif from_base == "f64" and to_base == "f32":
                res = self.fresh_tmp("fptrunc")
                insts.append(f"{res} = fptrunc double {val} to float")
                return res

        # Int -> Float
        if from_base not in ("f32", "f64") and to_base in ("f32", "f64"):
            op = "uitofp" if self.is_unsigned_type(from_base) else "sitofp"
            res = self.fresh_tmp(op)
            insts.append(f"{res} = {op} {from_llvm} {val} to {to_llvm}")
            return res

        # Float -> Int
        if from_base in ("f32", "f64") and to_base not in ("f32", "f64") and not is_to_ptr:
            op = "fptoui" if self.is_unsigned_type(to_base) else "fptosi"
            res = self.fresh_tmp(op)
            insts.append(f"{res} = {op} {from_llvm} {val} to {to_llvm}")
            return res

        if is_from_ptr and is_to_ptr:
            res = self.fresh_tmp("bitcast")
            insts.append(f"{res} = bitcast {from_llvm} {val} to {to_llvm}")
            return res
        if is_from_ptr and not is_to_ptr:
            res = self.fresh_tmp("p2i")
            insts.append(f"{res} = ptrtoint {from_llvm} {val} to {to_llvm}")
            return res
        if not is_from_ptr and is_to_ptr:
            res = self.fresh_tmp("i2p")
            insts.append(f"{res} = inttoptr {from_llvm} {val} to {to_llvm}")
            return res

        # Int <-> Int
        size_map = {"i1": 1, "u8": 8, "i8": 8, "u16": 16, "i16": 16, "u32": 32, "i32": 32, "u64": 64, "i64": 64}
        s_from = size_map.get(from_base, 32)
        s_to = size_map.get(to_base, 32)

        if s_from > s_to:
            res = self.fresh_tmp("trunc")
            insts.append(f"{res} = trunc {from_llvm} {val} to {to_llvm}")
            return res
        elif s_from < s_to:
            is_signed = from_base in ("i8", "i16", "i32", "i64")
            op = "sext" if is_signed else "zext"
            res = self.fresh_tmp(op)
            insts.append(f"{res} = {op} {from_llvm} {val} to {to_llvm}")
            return res
        else:
            return val

        return "0"
