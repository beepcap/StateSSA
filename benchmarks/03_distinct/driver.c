#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include <math.h>

#define N 1000000
#define WARMUP_RUNS 3
#define BENCH_RUNS 10

// 外部 StateSSA マシンのプロトタイプ宣言
extern void ProcessArray(float *in, float *out, int32_t len);

static double get_time_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

int main(int argc, char **argv) {
    const char *label = (argc > 1) ? argv[1] : "Benchmark";

    // 64バイト境界アラインメントでメモリ確保
    float *in_arr = NULL;
    float *out_arr = NULL;
    if (posix_memalign((void **)&in_arr, 64, N * sizeof(float)) != 0 ||
        posix_memalign((void **)&out_arr, 64, N * sizeof(float)) != 0) {
        fprintf(stderr, "Failed to allocate aligned memory\n");
        return 1;
    }

    // 初期化
    for (int i = 0; i < N; i++) {
        in_arr[i] = (float)(i % 100) * 0.1f;
        out_arr[i] = 0.0f;
    }

    // ウォームアップ
    for (int w = 0; w < WARMUP_RUNS; w++) {
        ProcessArray(in_arr, out_arr, N);
    }

    // 正当性検証
    float expected_0 = in_arr[0] * 2.5f + 1.0f;
    float expected_last = in_arr[N - 1] * 2.5f + 1.0f;
    if (fabsf(out_arr[0] - expected_0) > 1e-4f || fabsf(out_arr[N - 1] - expected_last) > 1e-4f) {
        fprintf(stderr, "Verification FAILED: out[0]=%f (expected %f), out[last]=%f (expected %f)\n",
                out_arr[0], expected_0, out_arr[N - 1], expected_last);
        free(in_arr);
        free(out_arr);
        return 1;
    }

    // 本番計測
    double total_ns = 0.0;
    double min_ns = 1e18;
    double max_ns = 0.0;

    for (int r = 0; r < BENCH_RUNS; r++) {
        double t0 = get_time_ns();
        ProcessArray(in_arr, out_arr, N);
        double t1 = get_time_ns();
        double elapsed_ns = t1 - t0;

        total_ns += elapsed_ns;
        if (elapsed_ns < min_ns) min_ns = elapsed_ns;
        if (elapsed_ns > max_ns) max_ns = elapsed_ns;
    }

    double avg_ns = total_ns / BENCH_RUNS;
    double min_ms = min_ns / 1e6;
    double avg_ms = avg_ns / 1e6;

    // スループット (2 FLOPs per element: mul + add)
    double gflops = (2.0 * N) / min_ns; // GFLOP/s based on min_ns

    printf("[%s] N=%d elements (%d runs)\n", label, N, BENCH_RUNS);
    printf("  Min Time : %.4f ms (%.0f ns)\n", min_ms, min_ns);
    printf("  Avg Time : %.4f ms (%.0f ns)\n", avg_ms, avg_ns);
    printf("  Throughput: %.2f GFLOPS\n", gflops);

    // 機械可読出力（run_bench.sh 用）
    printf("RESULT:%s:%.0f:%.4f:%.2f\n", label, min_ns, min_ms, gflops);

    free(in_arr);
    free(out_arr);
    return 0;
}
