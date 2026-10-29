import sys
import argparse
from pathlib import Path
from . import __version__
from .lexer import Lexer
from .parser import Parser
from .codegen import CodeGen
from .ast_nodes import Program

def load_and_merge(input_files: list[str]) -> Program:
    loaded_files = set()
    queue = [Path(f).resolve() for f in input_files]

    all_types = {}
    all_externs = {}
    all_machines = {}

    while queue:
        curr_file = queue.pop(0)
        if curr_file in loaded_files:
            continue
        if not curr_file.exists():
            print(f"Error: file '{curr_file}' not found", file=sys.stderr)
            sys.exit(1)
        loaded_files.add(curr_file)

        source = curr_file.read_text(encoding="utf-8")
        tokens = Lexer(source).tokenize()
        prog = Parser(tokens).parse_program()

        # Handle includes relative to current file
        for inc in prog.includes:
            inc_path = (curr_file.parent / inc).resolve()
            if inc_path not in loaded_files:
                queue.append(inc_path)

        # Merge types (deduplicate identical definitions)
        for t in prog.types:
            if t.name in all_types:
                if all_types[t.name].fields != t.fields:
                    raise SyntaxError(f"Conflicting type definition for '{t.name}' in {curr_file}")
            else:
                all_types[t.name] = t

        # Merge externs
        for ext in prog.externs:
            if ext.name not in all_externs:
                all_externs[ext.name] = ext

        # Merge machines
        for m in prog.machines:
            if m.name in all_machines:
                raise SyntaxError(f"Duplicate machine definition '{m.name}' in {curr_file}")
            all_machines[m.name] = m

    return Program(
        includes=[],
        types=list(all_types.values()),
        externs=list(all_externs.values()),
        machines=list(all_machines.values())
    )

def main():
    parser = argparse.ArgumentParser(description="StateSSA Compiler (ssac)")
    parser.add_argument("--version", action="version", version=f"ssac version {__version__}")
    parser.add_argument("input", nargs="*", help="Input .ssa files")
    parser.add_argument("-o", "--output", help="Output .ll file")
    args = parser.parse_args()

    if not args.input:
        parser.print_help()
        sys.exit(1)

    merged_ast = load_and_merge(args.input)
    llvm_ir = CodeGen(merged_ast).generate()

    if args.output:
        Path(args.output).write_text(llvm_ir, encoding="utf-8")
        input_summary = ", ".join(args.input)
        print(f"Compiled [{input_summary}] -> {args.output}")
    else:
        print(llvm_ir)

if __name__ == "__main__":
    main()
