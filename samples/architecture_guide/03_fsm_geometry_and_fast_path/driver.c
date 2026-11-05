// ============================================================================
// StateSSA Architecture Guide - Chapter 3 Sample
// File: driver.c
//
// C-ABI Integration and Security Verification Test Harness
// Covers RFC 8259 Standard Conformance, Security Guards, and Attack Vectors
// ============================================================================

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

// External machine symbol lowered from StateSSA
extern int32_t tokenize_json(const uint8_t* buf, int32_t len);

// Error code definitions matching StateSSA specification
#define ERR_INVALID_CHAR        -1
#define ERR_UNTERMINATED_STRING -2
#define ERR_MAX_DEPTH           -3
#define ERR_INVALID_ESCAPE      -4
#define ERR_UNEXPECTED_CLOSE    -5
#define ERR_UNCLOSED_BRACKET    -6

static int run_test(const char* test_name, const char* json_str, int32_t expected_tokens_or_err) {
    int32_t len = (int32_t)strlen(json_str);
    int32_t result = tokenize_json((const uint8_t*)json_str, len);

    if (result == expected_tokens_or_err) {
        printf("  [PASS] %-35s -> Result: %4d (Expected: %4d)\n", test_name, result, expected_tokens_or_err);
        return 0;
    } else {
        fprintf(stderr, "  [FAIL] %-35s -> Got: %4d, Expected: %4d\n", test_name, result, expected_tokens_or_err);
        return 1;
    }
}

int main(void) {
    int failures = 0;
    printf("======================================================================\n");
    printf(" StateSSA Chapter 2: RFC 8259 JSON FSM C-ABI Test Harness\n");
    printf("======================================================================\n\n");

    printf("--- [Section 1: Standard Positive Tests] ---\n");
    failures += run_test("Empty Object {}", "{}", 2);
    failures += run_test("Empty Array []", "[]", 2);
    failures += run_test("Simple Key-Value", "{\"key\": \"value\"}", 5);
    failures += run_test("Composite JSON with Literals",
                         "{\"key\": \"value\", \"id\": 123, \"arr\": [true, false, null]}", 19);
    failures += run_test("Valid Escape Sequences",
                         "{\"str\": \"Hello\\nWorld\\t\\\"quoted\\\"\\\\slash\\/\"}", 5);
    failures += run_test("Numbers and Exponents",
                         "[-1, 2.5, -3.14e+2, 42e-1]", 9);

    printf("\n--- [Section 2: Security & Negative Attack Vectors] ---\n");

    // Attack 1: Invalid Character Injection
    failures += run_test("Invalid Char (@ symbol)", "{\"user\": @admin}", ERR_INVALID_CHAR);

    // Attack 2: Raw Control Character Injection (< 0x20 in string)
    const char raw_ctrl[] = "{\"text\": \"hello\x01world\"}";
    int32_t res_ctrl = tokenize_json((const uint8_t*)raw_ctrl, (int32_t)sizeof(raw_ctrl) - 1);
    if (res_ctrl == ERR_INVALID_CHAR) {
        printf("  [PASS] %-35s -> Result: %4d (Expected: %4d)\n", "Raw Control Char in String", res_ctrl, ERR_INVALID_CHAR);
    } else {
        fprintf(stderr, "  [FAIL] %-35s -> Got: %4d, Expected: %4d\n", "Raw Control Char in String", res_ctrl, ERR_INVALID_CHAR);
        failures++;
    }

    // Attack 3: Unterminated String
    failures += run_test("Unterminated String Literal", "{\"key\": \"unterminated", ERR_UNTERMINATED_STRING);
    failures += run_test("Unterminated Escape at End", "{\"key\": \"escape_end\\", ERR_UNTERMINATED_STRING);

    // Attack 4: Nested Depth DoS Attack (> 64 brackets)
    char deep_json[200];
    memset(deep_json, '[', 65);
    memset(deep_json + 65, ']', 65);
    deep_json[130] = '\0';
    failures += run_test("Nest DoS Attack (Depth 65)", deep_json, ERR_MAX_DEPTH);

    // Border Case: Safe Maximum Depth (64 brackets: must pass)
    char safe_deep_json[200];
    memset(safe_deep_json, '[', 64);
    memset(safe_deep_json + 64, ']', 64);
    safe_deep_json[128] = '\0';
    failures += run_test("Safe Boundary Depth (Depth 64)", safe_deep_json, 128);

    // Attack 5: Invalid Escape Sequence Injection
    failures += run_test("Invalid Escape \\a", "{\"key\": \"\\a\"}", ERR_INVALID_ESCAPE);
    failures += run_test("Invalid Escape \\x", "{\"key\": \"\\x12\"}", ERR_INVALID_ESCAPE);

    // Attack 6: Unexpected Closing Bracket
    failures += run_test("Unexpected Extra Bracket", "[1, 2]]", ERR_UNEXPECTED_CLOSE);
    failures += run_test("Closing Bracket on Empty Stack", "}", ERR_UNEXPECTED_CLOSE);

    // Attack 7: Unclosed Bracket at EOF
    failures += run_test("Unclosed Bracket at EOF", "{\"open\": [1, 2}", ERR_UNCLOSED_BRACKET);
    failures += run_test("Single Open Bracket", "[", ERR_UNCLOSED_BRACKET);

    printf("\n--- [Section 3: Buffer Boundary Guards] ---\n");
    // Boundary Guards: NULL buffer and negative length
    int32_t res_null = tokenize_json(NULL, 10);
    if (res_null == ERR_INVALID_CHAR) {
        printf("  [PASS] %-35s -> Result: %4d (Expected: %4d)\n", "NULL Buffer Guard", res_null, ERR_INVALID_CHAR);
    } else {
        fprintf(stderr, "  [FAIL] %-35s -> Got: %4d, Expected: %4d\n", "NULL Buffer Guard", res_null, ERR_INVALID_CHAR);
        failures++;
    }

    uint8_t dummy = '{';
    int32_t res_neg = tokenize_json(&dummy, -1);
    if (res_neg == ERR_INVALID_CHAR) {
        printf("  [PASS] %-35s -> Result: %4d (Expected: %4d)\n", "Negative Length Guard", res_neg, ERR_INVALID_CHAR);
    } else {
        fprintf(stderr, "  [FAIL] %-35s -> Got: %4d, Expected: %4d\n", "Negative Length Guard", res_neg, ERR_INVALID_CHAR);
        failures++;
    }

    printf("\n--- [Section 4: 16-Byte SWAR Fast-Path String Traversal] ---\n");
    // Long string verification (> 16 bytes, triggering InStringFast loop multiple times)
    // Tokens: 1: '{', 2: "telemetry_log", 3: ':', 4: "<long string>", 5: '}' -> Total 5 tokens
    const char *long_str_json = "{\"telemetry_log\": \"abcdefghijklmnopqrstuvwxyz_0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ_EXTRA_PADDING_TO_TRIGGER_SWAR_MULTIPLE_TIMES\"}";
    failures += run_test("Long String (>100B SWAR Skip)", long_str_json, 5);

    printf("\n======================================================================\n");
    if (failures == 0) {
        printf(" >>> ALL 17 C-ABI INTEGRATION & SWAR VERIFICATION TESTS PASSED (100%%) <<<\n");
        printf("======================================================================\n");
        return 0;
    } else {
        fprintf(stderr, " >>> C-ABI VERIFICATION FAILED: %d failures detected! <<<\n", failures);
        printf("======================================================================\n");
        return 1;
    }
}
