#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${SCRIPT_DIR}/../../.."
SSAC_BIN="${WORK_DIR}/bin/ssac"
BUILD_DIR="${SCRIPT_DIR}/build"

mkdir -p "${BUILD_DIR}"

echo "======================================================================"
echo " StateSSA Architecture Guide - Chapter 2: JSON FSM Module Verification"
echo " Compiler: ${SSAC_BIN}"
echo "======================================================================"

# 1. Compile json_tokenizer.ssa to LLVM IR
echo "[1/5] Compiling json_tokenizer.ssa to LLVM IR..."
"${SSAC_BIN}" "${SCRIPT_DIR}/json_tokenizer.ssa" -o "${BUILD_DIR}/json_tokenizer.ll"
echo "  -> json_tokenizer.ll successfully generated."

# 2. Structural Inspection of Lowered LLVM IR
echo "[2/5] Verifying structural 1:1 mapping in LLVM IR..."

REQUIRED_BLOCKS=("WaitToken:" "InString:" "InEscape:" "InNumber:" "CheckFinalDepth:" "ExitSuccess:" "ExitError:")
for bb in "${REQUIRED_BLOCKS[@]}"; do
    if ! grep -q "^${bb}" "${BUILD_DIR}/json_tokenizer.ll"; then
        echo "  [ERROR] Expected basic block '${bb}' not found in LLVM IR!"
        exit 1
    fi
    echo "  -> Verified Basic Block: ${bb}"
done

# Verify phi node instantiation for registers at block ingress
PHI_COUNT=$(grep -c " = phi i32 " "${BUILD_DIR}/json_tokenizer.ll" || true)
if [ "${PHI_COUNT}" -lt 4 ]; then
    echo "  [ERROR] Expected at least 4 phi node instantiations, found ${PHI_COUNT}!"
    exit 1
fi
echo "  -> Verified Phi Ingress Nodes: ${PHI_COUNT} phi nodes instantiated."

# 3. Standalone Verification (Standalone StateSSA Program)
echo "[3/5] Building and executing standalone StateSSA test harness..."
"${SSAC_BIN}" "${SCRIPT_DIR}/standalone_main.ssa" -o "${BUILD_DIR}/standalone_main.ll"
clang "${BUILD_DIR}/standalone_main.ll" -o "${BUILD_DIR}/standalone_main"
"${BUILD_DIR}/standalone_main"

# 4. C-ABI Integration Verification (driver.c + json_tokenizer.o)
echo "[4/5] Building and executing C-ABI driver integration (C: driver.c)..."
clang -c "${BUILD_DIR}/json_tokenizer.ll" -o "${BUILD_DIR}/json_tokenizer.o"
clang "${SCRIPT_DIR}/driver.c" "${BUILD_DIR}/json_tokenizer.o" -o "${BUILD_DIR}/test_driver"
"${BUILD_DIR}/test_driver"

# 5. C++ Direct Link Integration Verification (driver_cpp.cpp + json_tokenizer.o)
echo "[5/5] Building and executing C++ direct link integration (C++: driver_cpp.cpp)..."
clang++ -std=c++17 "${SCRIPT_DIR}/driver_cpp.cpp" "${BUILD_DIR}/json_tokenizer.o" -o "${BUILD_DIR}/test_driver_cpp"
"${BUILD_DIR}/test_driver_cpp"

echo ""
echo "======================================================================"
echo " >>> ALL ARCHITECTURAL VERIFICATION CHECKS PASSED (100%) <<<"
echo "======================================================================"
