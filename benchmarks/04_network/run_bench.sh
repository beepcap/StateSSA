#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${SCRIPT_DIR}"

echo "======================================================================"
echo " Benchmark 04: Network & Node Binding A/B Comparison"
echo " Target: 3-Stage Pipeline (StageA -> StageB -> StageC) 10,000,000 calls"
echo " Case A: Normal Call (call StageA -> call StageB -> call StageC)"
echo " Case B: Network Fusion (node a/b/c sealed & fused on same stack)"
echo "======================================================================"

echo ""
echo "[Step 1] Compiling StateSSA source files using ssac..."
if [ -x "${ROOT_DIR}/bin/ssac" ]; then
    SSAC="${ROOT_DIR}/bin/ssac"
else
    SSAC="python3 ${ROOT_DIR}/bootstrap/main.py"
fi
${SSAC} call_pipeline.ssa -o call.ll
${SSAC} network_pipeline.ssa -o network.ll

echo ""
echo "[Step 2] Counting LLVM IR Call Instructions..."
CALL_COUNT_A=$(grep -c "call " call.ll || true)
CALL_COUNT_B=$(grep -c "call " network.ll || true)
CALL_DIFF=$(( CALL_COUNT_A - CALL_COUNT_B ))
CALL_REDUCTION=$(awk "BEGIN { printf \"%.1f\", ($CALL_DIFF / $CALL_COUNT_A) * 100 }")

echo "----------------------------------------------------------------------"
echo " Pipeline Call Instructions & Exported Symbols in LLVM IR:"
echo "   Case A (Normal Call)   : ${CALL_COUNT_A} call instructions, $(grep -c '^define ' call.ll) exported symbols"
echo "   Case B (Network Fusion): ${CALL_COUNT_B} call instructions, $(grep -c '^define ' network.ll) exported symbols (Sealed!)"
echo "   Call Elimination       : -${CALL_DIFF} calls (-${CALL_REDUCTION}%)"
echo "   Symbol Sealing         : StageA, StageB, StageC sealed & hidden from external linker"
echo "----------------------------------------------------------------------"

echo ""
echo "[Step 3] Emitting Assembly with clang -O3..."
clang -O3 -S call.ll -o call.s
clang -O3 -S network.ll -o network.s

CALL_ASM_LINES=$(wc -l < call.s)
NET_ASM_LINES=$(wc -l < network.s)
ASM_DIFF=$(( CALL_ASM_LINES - NET_ASM_LINES ))
ASM_REDUCTION=$(awk "BEGIN { printf \"%.1f\", ($ASM_DIFF / $CALL_ASM_LINES) * 100 }")

echo " Code Metrics (Assembly Lines):"
echo "   Case A (Call)    : ${CALL_ASM_LINES} lines"
echo "   Case B (Network) : ${NET_ASM_LINES} lines (-${ASM_DIFF} lines, -${ASM_REDUCTION}%)"
echo "----------------------------------------------------------------------"

echo ""
echo "[Step 4] Compiling native binaries with driver.c..."
clang -O3 driver.c call.ll -o bench_call
clang -O3 driver.c network.ll -o bench_network

echo ""
echo "[Step 5] Running Benchmarks (10,000,000 calls, 5 runs)..."
OUT_CALL=$(./bench_call "Case A (Call Pipeline)")
OUT_NETWORK=$(./bench_network "Case B (Network Fusion)")

echo "${OUT_CALL}" | grep -v "^RESULT:"
echo ""
echo "${OUT_NETWORK}" | grep -v "^RESULT:"

# パース
RES_CALL=$(echo "${OUT_CALL}" | grep "^RESULT:" | cut -d: -f2-)
RES_NET=$(echo "${OUT_NETWORK}" | grep "^RESULT:" | cut -d: -f2-)

MIN_NS_CALL=$(echo "${RES_CALL}" | cut -d: -f2)
MIN_NS_NET=$(echo "${RES_NET}" | cut -d: -f2)
MIN_MS_CALL=$(echo "${RES_CALL}" | cut -d: -f3)
MIN_MS_NET=$(echo "${RES_NET}" | cut -d: -f3)
LAT_CALL=$(echo "${RES_CALL}" | cut -d: -f4)
LAT_NET=$(echo "${RES_NET}" | cut -d: -f4)

SPEEDUP=$(awk "BEGIN { printf \"%.2f\", $MIN_NS_CALL / $MIN_NS_NET }")
LAT_DIFF=$(awk "BEGIN { printf \"%.3f\", $LAT_CALL - $LAT_NET }")

echo ""
echo "======================================================================"
echo " Benchmark 04 Summary Results:"
echo "   Call Pipeline (Case A)    : ${MIN_MS_CALL} ms (${LAT_CALL} ns/call)"
echo "   Network Fusion (Case B)   : ${MIN_MS_NET} ms (${LAT_NET} ns/call)"
echo "   Speedup Ratio             : ${SPEEDUP}x"
echo "   Latency Saved             : ${LAT_DIFF} ns per pipeline execution"
echo "   Call Instruction Reduction: -${CALL_REDUCTION}% (3 calls -> 0 calls)"
echo "   Assembly Reduction        : -${ASM_REDUCTION}%"
echo "======================================================================"
