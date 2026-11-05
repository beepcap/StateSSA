// ============================================================================
// StateSSA Architecture Guide - Chapter 1 Sample
// File: driver.c
//
// C-ABI Integration Test Harness for protocol_decoder
// ============================================================================

#include <stdio.h>
#include <stdint.h>
#include <assert.h>

// External function compiled from StateSSA machine decode_stream
extern int32_t decode_stream(const uint8_t* buf, int32_t len);

int main(void) {
    printf("[driver.c] Starting C-ABI integration verification...\n");

    // Static test stream containing 22 bytes:
    // - Packet 1: Valid (Len 3, payload: {10, 20, 30}, xor sum: 3 ^ 10 ^ 20 ^ 30 = 3)
    // - Noise: 3 bytes ({0x12, 0xFF, 0x00})
    // - Packet 2: Valid (Len 2, payload: {5, 9}, xor sum: 2 ^ 5 ^ 9 = 14)
    // - Packet 3: Corrupted Checksum (Len 1, payload: {7}, expected: 6, actual: 99)
    // - Packet 4: Valid (Len 1, payload: {42}, xor sum: 1 ^ 42 = 43)
    const uint8_t stream[22] = {
        0xAA, 3, 10, 20, 30, 3,
        0x12, 0xFF, 0x00,
        0xAA, 2, 5, 9, 14,
        0xAA, 1, 7, 99,
        0xAA, 1, 42, 43
    };

    int32_t valid_count = decode_stream(stream, (int32_t)sizeof(stream));
    printf("[driver.c] Valid packets recognized: %d (Expected: 3)\n", valid_count);

    if (valid_count != 3) {
        fprintf(stderr, "[driver.c] ERROR: Expected 3 valid packets, got %d\n", valid_count);
        return 1;
    }

    printf("[PASS: driver.c] C-ABI integration verified successfully.\n");
    return 0;
}
