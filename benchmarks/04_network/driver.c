#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define ITERATIONS 10000000
#define WARMUP_RUNS 2
#define BENCH_RUNS 5

// 外部 StateSSA パイプライン
extern int32_t RunPipeline(int32_t x);

static double get_time_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

int main(int argc, char **argv) {
    const char *label = (argc > 1) ? argv[1] : "Benchmark";

    // ウォームアップ
    int32_t warmup_acc = 0;
    for (int w = 0; w < WARMUP_RUNS; w++) {
        for (int i = 0; i < 100000; i++) {
            warmup_acc ^= RunPipeline(i & 0xFF);
        }
    }

    // 正当性チェック（単発実行の値検証）
    // x = 10 -> StageA: 10 * 3 + 1 = 31
    //        -> StageB: 31 * 2 - 5 = 57
    //        -> StageC: 57 ^ 23130 = 23187
    int32_t test_val = RunPipeline(10);
    int32_t expected = ((10 * 3 + 1) * 2 - 5) ^ 23130;
    if (test_val != expected) {
        fprintf(stderr, "Verification FAILED: RunPipeline(10) = %d (expected %d)\n", test_val, expected);
        return 1;
    }

    // 本番計測 (10,000,000回反復)
    double total_ns = 0.0;
    double min_ns = 1e18;
    double max_ns = 0.0;
    volatile int32_t checksum = 0;

    for (int r = 0; r < BENCH_RUNS; r++) {
        int32_t acc = 0;
        double t0 = get_time_ns();
        for (int i = 0; i < ITERATIONS; i++) {
            acc += RunPipeline(i & 0xFFFF);
        }
        double t1 = get_time_ns();
        double elapsed_ns = t1 - t0;

        checksum = acc; // 最適化防止
        total_ns += elapsed_ns;
        if (elapsed_ns < min_ns) min_ns = elapsed_ns;
        if (elapsed_ns > max_ns) max_ns = elapsed_ns;
    }

    double avg_ns = total_ns / BENCH_RUNS;
    double min_ms = min_ns / 1e6;
    double avg_ms = avg_ns / 1e6;
    double latency_ns_per_call = min_ns / ITERATIONS;
    double throughput_mops = ((double)ITERATIONS / (min_ns / 1e9)) / 1e6;

    printf("[%s] %d calls (%d runs, checksum=%d)\n", label, ITERATIONS, BENCH_RUNS, checksum);
    printf("  Total Time : %.2f ms (min), %.2f ms (avg)\n", min_ms, avg_ms);
    printf("  Latency    : %.3f ns / call\n", latency_ns_per_call);
    printf("  Throughput : %.2f M calls/sec\n", throughput_mops);

    // 機械可読出力（run_bench.sh 用）
    printf("RESULT:%s:%.0f:%.2f:%.3f:%.2f\n", label, min_ns, min_ms, latency_ns_per_call, throughput_mops);

    return 0;
}
