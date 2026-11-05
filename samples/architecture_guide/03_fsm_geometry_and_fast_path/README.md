# StateSSA Architecture Guide - Chapter 3 Sample
## RFC 8259 JSON Tokenizer with 16-Byte SWAR Fast-Path

This sample directory provides the companion source code for **Chapter 3: The Geometry of Machines, Flow, and States (プログラムの骨格 —— machine, flow, states の幾何学)**.

It demonstrates **High-Performance FSM Topology Optimization via Minimal-Diff Fast-Path Edges**, showing how a safe, strictly RFC 8259-compliant finite state machine can be accelerated to achieve state-of-the-art throughput (over 715 MB/s on large telemetry workloads) without sacrificing memory safety, without requesting buffer padding, and without modifying a single line of existing core parsing logic.

---

### Key Architectural Concepts Demonstrated

1. **Self-Loop Bypass (Avoiding State Explosion)**:
   - Rather than attempting to parse combinations of structural characters across 16-byte blocks (which causes an exponential explosion in state space), the architecture preserves the fine-grained 1-byte state machine and adds a 16-byte bypass edge exclusively on the unadorned string body self-loop (`InStringFast`).
2. **Deterministic Zero-Padding Boundary Defense**:
   - Computes `safe_len = len - 16` at entry.
   - 16-byte SIMD/SWAR loads are only permitted while `cursor < safe_len`.
   - Remaining trailing bytes (< 16 bytes) automatically fall back to the safe, byte-by-byte scalar state machine. No user padding, no dynamic re-allocation, and zero buffer over-reads.
3. **Locality of Change (Minimal Diff)**:
   - Exactly one state node (`InStringFast`) and a single entry edge condition are added.
   - All existing RFC 8259 validation, escape decoding, and recursion depth limits remain 100% untouched.

---

### Files in this Sample

- `json_tokenizer_fast.ssa`: StateSSA machine implementing the 16-byte SWAR fast-path string scanner.
- `standalone_main.ssa`: Self-contained StateSSA execution test harness.
- `driver.c`: C test harness verifying 17 RFC 8259 compliance, attack vector, boundary, and long-string SWAR tests.
- `driver_cpp.cpp`: C++ direct linkage harness verifying zero-cost C-ABI integration with C++.
- `run.sh`: Automated compilation, structural LLVM IR verification, and AddressSanitizer/UBSan validation script.

---

### Verification

Run the full verification suite:
```bash
./run.sh
```
All standalone, C, C++, and Sanitizer tests must report `100% PASS`.
