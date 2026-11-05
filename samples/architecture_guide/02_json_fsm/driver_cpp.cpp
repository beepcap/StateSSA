// ============================================================================
// StateSSA Architecture Guide - Chapter 2 Sample
// File: driver_cpp.cpp
//
// C++ Direct Link & Multi-Language Verification Test Harness
// Direct linkage to StateSSA object file via `extern "C"` (Zero-Cost C-ABI)
// Demonstrates RFC 8259 Standard Conformance, Security Guards, and Attack Vectors
// ============================================================================

#include <iostream>
#include <iomanip>
#include <vector>
#include <string>
#include <cstring>
#include <cstdint>

// Direct zero-cost linkage to the StateSSA compiled machine symbol
extern "C" {
    int32_t tokenize_json(const uint8_t* buf, int32_t len);
}

// Error codes defined in StateSSA specification
namespace JSONError {
    constexpr int32_t InvalidChar        = -1;
    constexpr int32_t UnterminatedString = -2;
    constexpr int32_t MaxDepthExceeded   = -3;
    constexpr int32_t InvalidEscape      = -4;
    constexpr int32_t UnexpectedClose    = -5;
    constexpr int32_t UnclosedBracket    = -6;
}

struct TestCase {
    std::string name;
    std::string input;
    int32_t expected;
};

static int run_single_test(const std::string& name, const std::string& input, int32_t expected) {
    int32_t result = tokenize_json(reinterpret_cast<const uint8_t*>(input.data()), static_cast<int32_t>(input.size()));
    if (result == expected) {
        std::cout << "  [PASS] " << std::left << std::setw(35) << name
                  << " -> Result: " << std::right << std::setw(4) << result
                  << " (Expected: " << std::right << std::setw(4) << expected << ")\n";
        return 0;
    } else {
        std::cerr << "  [FAIL] " << std::left << std::setw(35) << name
                  << " -> Got: " << std::right << std::setw(4) << result
                  << ", Expected: " << std::right << std::setw(4) << expected << "\n";
        return 1;
    }
}

int main() {
    int failures = 0;
    std::cout << "======================================================================\n";
    std::cout << " StateSSA Chapter 2: RFC 8259 JSON FSM C++ Direct Link Test Harness\n";
    std::cout << "======================================================================\n\n";

    std::cout << "--- [Section 1: Standard Positive Tests] ---\n";
    const std::vector<TestCase> positive_cases = {
        {"Empty Object {}", "{}", 2},
        {"Empty Array []", "[]", 2},
        {"Simple Key-Value", "{\"key\": \"value\"}", 5},
        {"Composite JSON with Literals", "{\"key\": \"value\", \"id\": 123, \"arr\": [true, false, null]}", 19},
        {"Valid Escape Sequences", "{\"str\": \"Hello\\nWorld\\t\\\"quoted\\\"\\\\slash\\/\"}", 5},
        {"Numbers and Exponents", "[-1, 2.5, -3.14e+2, 42e-1]", 9}
    };

    for (const auto& tc : positive_cases) {
        failures += run_single_test(tc.name, tc.input, tc.expected);
    }

    std::cout << "\n--- [Section 2: Security & Negative Attack Vectors] ---\n";

    // Attack 1: Invalid Character Injection
    failures += run_single_test("Invalid Char (@ symbol)", "{\"user\": @admin}", JSONError::InvalidChar);

    // Attack 2: Raw Control Character Injection (< 0x20 in string)
    const std::string raw_ctrl = "{\"text\": \"hello\x01world\"}";
    failures += run_single_test("Raw Control Char in String", raw_ctrl, JSONError::InvalidChar);

    // Attack 3: Unterminated String
    failures += run_single_test("Unterminated String Literal", "{\"key\": \"unterminated", JSONError::UnterminatedString);
    failures += run_single_test("Unterminated Escape at End", "{\"key\": \"escape_end\\", JSONError::UnterminatedString);

    // Attack 4: Nested Depth DoS Attack (> 64 brackets)
    std::string deep_json(65, '[');
    deep_json.append(65, ']');
    failures += run_single_test("Nest DoS Attack (Depth 65)", deep_json, JSONError::MaxDepthExceeded);

    // Border Case: Safe Maximum Depth (64 brackets: must pass)
    std::string safe_deep_json(64, '[');
    safe_deep_json.append(64, ']');
    failures += run_single_test("Safe Boundary Depth (Depth 64)", safe_deep_json, 128);

    // Attack 5: Invalid Escape Sequence Injection
    failures += run_single_test("Invalid Escape \\a", "{\"key\": \"\\a\"}", JSONError::InvalidEscape);
    failures += run_single_test("Invalid Escape \\x", "{\"key\": \"\\x12\"}", JSONError::InvalidEscape);

    // Attack 6: Unexpected Closing Bracket
    failures += run_single_test("Unexpected Extra Bracket", "[1, 2]]", JSONError::UnexpectedClose);
    failures += run_single_test("Closing Bracket on Empty Stack", "}", JSONError::UnexpectedClose);

    // Attack 7: Unclosed Bracket at EOF
    failures += run_single_test("Unclosed Bracket at EOF", "{\"open\": [1, 2}", JSONError::UnclosedBracket);
    failures += run_single_test("Single Open Bracket", "[", JSONError::UnclosedBracket);

    std::cout << "\n--- [Section 3: Buffer Boundary Guards] ---\n";
    // Boundary Guards: NULL buffer and negative length
    int32_t res_null = tokenize_json(nullptr, 10);
    if (res_null == JSONError::InvalidChar) {
        std::cout << "  [PASS] " << std::left << std::setw(35) << "NULL Buffer Guard"
                  << " -> Result: " << std::right << std::setw(4) << res_null
                  << " (Expected: " << std::right << std::setw(4) << JSONError::InvalidChar << ")\n";
    } else {
        std::cerr << "  [FAIL] " << std::left << std::setw(35) << "NULL Buffer Guard"
                  << " -> Got: " << res_null << ", Expected: " << JSONError::InvalidChar << "\n";
        failures++;
    }

    uint8_t dummy = '{';
    int32_t res_neg = tokenize_json(&dummy, -1);
    if (res_neg == JSONError::InvalidChar) {
        std::cout << "  [PASS] " << std::left << std::setw(35) << "Negative Length Guard"
                  << " -> Result: " << std::right << std::setw(4) << res_neg
                  << " (Expected: " << std::right << std::setw(4) << JSONError::InvalidChar << ")\n";
    } else {
        std::cerr << "  [FAIL] " << std::left << std::setw(35) << "Negative Length Guard"
                  << " -> Got: " << res_neg << ", Expected: " << JSONError::InvalidChar << "\n";
        failures++;
    }

    std::cout << "\n======================================================================\n";
    if (failures == 0) {
        std::cout << " >>> ALL 16 C++ DIRECT LINK & SECURITY TESTS PASSED (100%) <<<\n";
        std::cout << "======================================================================\n";
        return 0;
    } else {
        std::cerr << " >>> C++ DIRECT LINK VERIFICATION FAILED: " << failures << " failures detected! <<<\n";
        std::cout << "======================================================================\n";
        return 1;
    }
}
