#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${SCRIPT_DIR}/../../.."
SSAC_BIN="${WORK_DIR}/bin/ssac"
BUILD_DIR="${SCRIPT_DIR}/build"

mkdir -p "${BUILD_DIR}"

echo "======================================================================"
echo " StateSSA Architecture Guide - Chapter 3: SWAR Fast-Path FSM Verification"
echo " Compiler: ${SSAC_BIN}"
echo "======================================================================"

# 1. Compile json_tokenizer_fast.ssa to LLVM IR
echo "[1/6] Compiling json_tokenizer_fast.ssa to LLVM IR..."
"${SSAC_BIN}" "${SCRIPT_DIR}/json_tokenizer_fast.ssa" -o "${BUILD_DIR}/json_tokenizer_fast.ll"
echo "  -> json_tokenizer_fast.ll successfully generated."

# 2. Structural Inspection of Lowered LLVM IR
echo "[2/6] Verifying structural 1:1 mapping and InStringFast node in LLVM IR..."

REQUIRED_BLOCKS=("WaitToken:" "InStringFast:" "InString:" "InEscape:" "InNumber:" "CheckFinalDepth:" "ExitSuccess:" "ExitError:")
for bb in "${REQUIRED_BLOCKS[@]}"; do
    if ! grep -q "^${bb}" "${BUILD_DIR}/json_tokenizer_fast.ll"; then
        echo "  [ERROR] Expected basic block '${bb}' not found in LLVM IR!"
        exit 1
    fi
    echo "  -> Verified Basic Block: ${bb}"
done

# Verify phi node instantiation for registers at block ingress
PHI_COUNT=$(grep -c " = phi i32 " "${BUILD_DIR}/json_tokenizer_fast.ll" || true)
if [ "${PHI_COUNT}" -lt 4 ]; then
    echo "  [ERROR] Expected at least 4 phi node instantiations, found ${PHI_COUNT}!"
    exit 1
fi
echo "  -> Verified Phi Ingress Nodes: ${PHI_COUNT} phi nodes instantiated."

# 3. Standalone Verification (Standalone StateSSA Program)
echo "[3/6] Building and executing standalone StateSSA test harness..."
(cd "${SCRIPT_DIR}" && "${SSAC_BIN}" "standalone_main.ssa" -o "${BUILD_DIR}/standalone_main.ll")
clang "${BUILD_DIR}/standalone_main.ll" -o "${BUILD_DIR}/standalone_main"
"${BUILD_DIR}/standalone_main"

# 4. C-ABI Integration Verification (driver.c + json_tokenizer_fast.o)
echo "[4/6] Building and executing C-ABI driver integration (C: driver.c)..."
clang -O3 -c "${BUILD_DIR}/json_tokenizer_fast.ll" -o "${BUILD_DIR}/json_tokenizer_fast.o"
clang -O3 "${SCRIPT_DIR}/driver.c" "${BUILD_DIR}/json_tokenizer_fast.o" -o "${BUILD_DIR}/test_driver"
"${BUILD_DIR}/test_driver"

# 5. C++ Direct Link Integration Verification (driver_cpp.cpp + json_tokenizer_fast.o)
echo "[5/6] Building and executing C++ direct link integration (C++: driver_cpp.cpp)..."
clang++ -O3 -std=c++17 "${SCRIPT_DIR}/driver_cpp.cpp" "${BUILD_DIR}/json_tokenizer_fast.o" -o "${BUILD_DIR}/test_driver_cpp"
"${BUILD_DIR}/test_driver_cpp"

# 6. Memory Safety Verification (AddressSanitizer + UndefinedBehaviorSanitizer)
echo "[6/6] Verifying dynamic memory safety via AddressSanitizer & UBSan..."
clang -fsanitize=address,undefined -g "${SCRIPT_DIR}/driver.c" "${BUILD_DIR}/json_tokenizer_fast.o" -o "${BUILD_DIR}/test_driver_asan"
"${BUILD_DIR}/test_driver_asan"

echo ""
echo "======================================================================"
echo " >>> ALL ARCHITECTURAL & SWAR VERIFICATION CHECKS PASSED (100%) <<<"
echo "======================================================================"
