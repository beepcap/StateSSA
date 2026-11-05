#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${SCRIPT_DIR}/../../.."
SSAC_BIN="${WORK_DIR}/bin/ssac"
BUILD_DIR="${SCRIPT_DIR}/build"

mkdir -p "${BUILD_DIR}"

echo "======================================================================"
echo " StateSSA Architecture Guide - Chapter 1: Protocol FSM Verification"
echo " Compiler: ${SSAC_BIN}"
echo "======================================================================"

# 1. Compile protocol_decoder.ssa to LLVM IR
echo "[1/4] Compiling protocol_decoder.ssa to LLVM IR..."
"${SSAC_BIN}" "${SCRIPT_DIR}/protocol_decoder.ssa" -o "${BUILD_DIR}/protocol_decoder.ll"
echo "  -> protocol_decoder.ll successfully generated."

# 2. Structural Inspection of Lowered LLVM IR
echo "[2/4] Verifying structural 1:1 mapping in LLVM IR..."

REQUIRED_BLOCKS=("WaitSync:" "ReadLength:" "ReadPayload:" "ReadChecksum:" "Exit:")
for bb in "${REQUIRED_BLOCKS[@]}"; do
    if ! grep -q "^${bb}" "${BUILD_DIR}/protocol_decoder.ll"; then
        echo "  [ERROR] Expected basic block '${bb}' not found in LLVM IR!"
        exit 1
    fi
    echo "  -> Verified Basic Block: ${bb}"
done

# Verify phi node instantiation for registers at block ingress
PHI_COUNT=$(grep -c " = phi i32 " "${BUILD_DIR}/protocol_decoder.ll" || true)
if [ "${PHI_COUNT}" -lt 5 ]; then
    echo "  [ERROR] Expected at least 5 phi node instantiations, found ${PHI_COUNT}!"
    exit 1
fi
echo "  -> Verified Phi Ingress Nodes: ${PHI_COUNT} phi nodes instantiated."

# 3. Standalone Verification (Standalone StateSSA Program)
echo "[3/4] Building and executing standalone StateSSA test harness..."
"${SSAC_BIN}" "${SCRIPT_DIR}/standalone_main.ssa" -o "${BUILD_DIR}/standalone_main.ll"
clang "${BUILD_DIR}/standalone_main.ll" -o "${BUILD_DIR}/standalone_main"
"${BUILD_DIR}/standalone_main"

# 4. C-ABI Integration Verification (driver.c + protocol_decoder.o)
echo "[4/4] Building and executing C-ABI driver integration..."
clang -c "${BUILD_DIR}/protocol_decoder.ll" -o "${BUILD_DIR}/protocol_decoder.o"
clang "${SCRIPT_DIR}/driver.c" "${BUILD_DIR}/protocol_decoder.o" -o "${BUILD_DIR}/test_driver"
"${BUILD_DIR}/test_driver"

echo ""
echo "======================================================================"
echo " >>> ALL ARCHITECTURAL VERIFICATION CHECKS PASSED (100%) <<<"
echo "======================================================================"
