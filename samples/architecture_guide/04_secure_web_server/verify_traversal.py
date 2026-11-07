#!/usr/bin/env python3
"""
StateSSA Web Server Path Traversal Resilience & Boundary Robustness Verification Suite
Target: StateSSA io_uring Web Server (127.0.0.1:18080) running in isolated QEMU environment
Docroot: /var/www/html (public)
Secret Target: /var/secret/himitu.txt (Contains FLAG)
"""

import sys
import time
import socket
import threading
from typing import List, Tuple, Dict, Any, Optional

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 18080

# Forbidden secret leak tokens
FORBIDDEN_TOKENS = [
    b"FLAG{",
    b"himitu",
    b"TopSecret",
    b"root:x:",
    b"/bin/bash",
    b"/bin/sh",
    b"TOP_SECRET",
]

def check_liveness(timeout: float = 2.0) -> bool:
    """Verifies that the server is alive and responding normally to standard requests."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((SERVER_HOST, SERVER_PORT))
        s.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        res = s.recv(512)
        s.close()
        return b"200 OK" in res and b"Hello from StateSSA!" in res
    except Exception:
        return False

def send_raw_request(raw_bytes: bytes, timeout: float = 2.0) -> Tuple[int, str, bytes, bytes]:
    """
    Sends raw request bytes to the server.
    Returns: (status_code, status_line, header_bytes, body_bytes)
    status_code:
      > 0: HTTP status code
      -1: Socket closed / terminated by server (Clean TCP close)
      -2: Socket timeout or connection error
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((SERVER_HOST, SERVER_PORT))
        s.sendall(raw_bytes)

        response_bytes = b""
        while b"\r\n\r\n" not in response_bytes:
            chunk = s.recv(4096)
            if not chunk:
                break
            response_bytes += chunk

        if b"\r\n\r\n" in response_bytes:
            header_part, body_part = response_bytes.split(b"\r\n\r\n", 1)
            cl = 0
            for line in header_part.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    try:
                        cl = int(line.split(b":", 1)[1].strip())
                    except ValueError:
                        pass
            # Read remainder of body based on Content-Length
            while len(body_part) < cl:
                chunk = s.recv(min(4096, cl - len(body_part)))
                if not chunk:
                    break
                body_part += chunk
            full_response = header_part + b"\r\n\r\n" + body_part
        else:
            header_part = response_bytes
            body_part = b""
            full_response = response_bytes

        s.close()

        if not full_response:
            return (-1, "CONNECTION_CLOSED", b"", b"")

        lines = header_part.split(b"\r\n")
        status_line = lines[0].decode("latin-1", errors="replace")
        parts = status_line.split(" ")
        status_code = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
        return (status_code, status_line, header_part, body_part)

    except socket.timeout:
        try:
            s.close()
        except Exception:
            pass
        return (-2, "TIMEOUT", b"", b"")
    except Exception as e:
        try:
            s.close()
        except Exception:
            pass
        return (-2, str(e), b"", b"")

def run_test_suite() -> int:
    print("=" * 80)
    print("StateSSA Web Server: Path Traversal Resilience & Boundary Robustness Suite")
    print(f"Target: http://{SERVER_HOST}:{SERVER_PORT}/")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 80)

    # Initial liveness check
    if not check_liveness():
        print("[FATAL] Target server is NOT responding at 127.0.0.1:18080! Aborting.")
        return 1
    print("[INIT] Target server liveness verified: 127.0.0.1:18080 is online.")
    print("-" * 80)

    test_groups: List[Tuple[str, List[Tuple[str, str, bytes, List[int]]]]] = [
        (
            "Group 1: 単純トラバーサル (Simple Path Traversal)",
            [
                ("TRV-SMP-01", "Parent dir traversal to /var/secret/himitu.txt",
                 b"GET /../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-SMP-02", "Multi-level traversal to /etc/passwd",
                 b"GET /../../etc/passwd HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-SMP-03", "Deep traversal to /var/secret/himitu.txt",
                 b"GET /../../../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-SMP-04", "Traversal from public docroot (/public/../...)",
                 b"GET /public/../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-SMP-05", "Double traversal from public (/public/../../...)",
                 b"GET /public/../../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-SMP-06", "Traversal from nested css dir (/public/css/../../...)",
                 b"GET /public/css/../../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-SMP-07", "Windows-style backslash traversal (/..\\var\\secret)",
                 b"GET /..\\var\\secret\\himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-SMP-08", "Mixed backslash traversal (/public/..\\..\\var/secret)",
                 b"GET /public/..\\..\\var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
            ]
        ),
        (
            "Group 2: URL エンコード / 多重エンコード (URL-Encoded & Double-Encoded)",
            [
                ("TRV-ENC-01", "Lowercase URL encoded dots (/%2e%2e/)",
                 b"GET /%2e%2e/var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-ENC-02", "Uppercase URL encoded dots (/%2E%2E/)",
                 b"GET /%2E%2E/var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-ENC-03", "URL encoded dots and slash (/%2e%2e%2f)",
                 b"GET /%2e%2e%2fvar/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-ENC-04", "Full uppercase URL encoding (/%2E%2E%2F...)",
                 b"GET /%2E%2E%2Fvar%2Fsecret%2Fhimitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-ENC-05", "Partial encoding (/..%2f...)",
                 b"GET /..%2fvar/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-ENC-06", "Single encoded dot + raw dot (/%2e./...)",
                 b"GET /%2e./var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-ENC-07", "Raw dot + single encoded dot (/.%2e/...)",
                 b"GET /.%2e/var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-ENC-08", "Double URL encoded dots (/%252e%252e/)",
                 b"GET /%252e%252e/var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400, 404]),
                ("TRV-ENC-09", "Double URL encoded dots and slash (/%252e%252e%252f)",
                 b"GET /%252e%252e%252fvar/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400, 404]),
                ("TRV-ENC-10", "Nested double percent encoding (/%25%32%65...)",
                 b"GET /%25%32%65%25%32%65/var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400, 404]),
            ]
        ),
        (
            "Group 3: ドット・スラッシュ異種混在 (Mixed Dot/Slash & Anomalies)",
            [
                ("TRV-MIX-01", "Quadruple dot slash (/....//var/secret/...)",
                 b"GET /....//var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MIX-02", "Triple dot (/.../var/secret/...)",
                 b"GET /.../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MIX-03", "Single dot repetition (/././var/secret/...)",
                 b"GET /././var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [404]),
                ("TRV-MIX-04", "Double leading slash (//var/secret/...)",
                 b"GET //var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [404]),
                ("TRV-MIX-05", "Quadruple leading slash (////var/secret/...)",
                 b"GET ////var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [404]),
                ("TRV-MIX-06", "Nested multi-dot anomaly (/public/....//....//...)",
                 b"GET /public/....//....//var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MIX-07", "Benign single dot normalization (/public/././index.html)",
                 b"GET /public/././index.html HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [200]),
                ("TRV-MIX-08", "Single dot followed by double dot (/./../../...)",
                 b"GET /./../../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
            ]
        ),
        (
            "Group 4: NULL バイト注入 (NULL Byte Injection)",
            [
                ("TRV-NUL-01", "Encoded NULL byte inside traversal (/index.html%00/../../...)",
                 b"GET /index.html%00/../../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-NUL-02", "Encoded NULL byte extension truncation (/himitu.txt%00.html)",
                 b"GET /var/secret/himitu.txt%00.html HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-NUL-03", "Encoded NULL byte at end of valid file (/public/index.html%00)",
                 b"GET /public/index.html%00 HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-NUL-04", "Raw NULL byte (0x00) inside path (/safe\\x00/../../...)",
                 b"GET /safe\x00/../../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-NUL-05", "Encoded NULL byte before double dots (/%00../...)",
                 b"GET /%00../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-NUL-06", "Raw NULL byte extension bypass (/public/index.html\\x00.css)",
                 b"GET /public/index.html\x00.css HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
            ]
        ),
        (
            "Group 5: 長大パス / バッファ境界値 (Buffer Boundary & Long Paths)",
            [
                ("TRV-BND-01", "URI length 1023 bytes (near 1KB buffer boundary)",
                 b"GET /" + (b"A" * 1023) + b" HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400, 404]),
                ("TRV-BND-02", "URI length exactly 1024 bytes (buffer limit)",
                 b"GET /" + (b"A" * 1024) + b" HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-BND-03", "URI length 1025 bytes (buffer limit + 1)",
                 b"GET /" + (b"A" * 1025) + b" HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-BND-04", "URI length 2048 bytes (medium overflow)",
                 b"GET /" + (b"A" * 2048) + b" HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-BND-05", "URI length 4096 bytes (rx_buf ring limit)",
                 b"GET /" + (b"A" * 4096) + b" HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-BND-06", "URI length 8192 bytes (rx_buf overflow exceed)",
                 b"GET /" + (b"A" * 8192) + b" HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400, -1]),
                ("TRV-BND-07", "Deep directory tree traversal (100 nested sub/ & ../)",
                 b"GET /" + (b"sub/" * 100) + (b"../" * 100) + b"var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-BND-08", "Extreme slash flood (500 continuous slashes)",
                 b"GET /" + (b"/" * 500) + b"public/index.html HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
            ]
        ),
        (
            "Group 6: 不正 URI / プロトコル異常 (Malformed URI & Protocol Abuse)",
            [
                ("TRV-MAL-01", "Missing leading slash (GET var/secret/...)",
                 b"GET var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-02", "Missing leading slash traversal (GET ../var/secret/...)",
                 b"GET ../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-03", "Empty URI path (GET  HTTP/1.1)",
                 b"GET  HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400, -1]),
                ("TRV-MAL-04", "Control character SOH (0x01) injection",
                 b"GET /var/\x01secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-05", "Control character US (0x1F) injection",
                 b"GET /var/\x1fsecret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-06", "DEL character (0x7F) injection",
                 b"GET /var/\x7fsecret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-07", "Overlong UTF-8 Slash (0xC0 0xAF)",
                 b"GET /\xc0\xaf../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-08", "Invalid UTF-8 Lead byte (0xC1 0x81)",
                 b"GET /\xc1\x81/var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-09", "Truncated percent sequence (/%2)",
                 b"GET /%2 HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-10", "Invalid hex character in percent sequence (/%2g/)",
                 b"GET /%2g/test HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400]),
                ("TRV-MAL-11", "Unsupported HTTP method (FOO /public/index.html)",
                 b"FOO /public/index.html HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [400, 405, -1]),
            ]
        ),
        (
            "Group 7: ベースライン機能回帰 & 正常系確認 (Baseline Regression & Normal Files)",
            [
                ("BASE-01", "Root greeting baseline (GET / -> 200 OK)",
                 b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [200]),
                ("BASE-02", "Echo POST baseline (POST /echo -> 200 OK)",
                 b"POST /echo HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 9\r\nConnection: close\r\n\r\nStateSSA!", [200]),
                ("BASE-03", "Baseline query calculation (GET /baseline11?a=42&b=58 -> 100)",
                 b"GET /baseline11?a=42&b=58 HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [200]),
                ("BASE-04", "Normal static HTML file (/public/index.html -> 200 OK)",
                 b"GET /public/index.html HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [200]),
                ("BASE-05", "Normal static CSS file (/public/css/style.css -> 200 OK)",
                 b"GET /public/css/style.css HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [200]),
                ("BASE-06", "Non-existent legitimate file (/public/non_existent.html -> 404)",
                 b"GET /public/non_existent.html HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", [404]),
            ]
        )
    ]

    total_tests = 0
    passed_tests = 0
    leaked_tests = 0
    failed_tests = []

    for group_name, cases in test_groups:
        print(f"\n>>> {group_name}")
        for test_id, desc, req_bytes, expected_codes in cases:
            total_tests += 1
            code, line, hdr, body = send_raw_request(req_bytes)

            # Leak detection invariant
            leaked = False
            for tok in FORBIDDEN_TOKENS:
                if tok in hdr or tok in body:
                    leaked = True
                    break

            status_ok = code in expected_codes
            is_pass = status_ok and (not leaked)

            if is_pass:
                passed_tests += 1
                status_str = "PASS"
            else:
                status_str = "FAIL"
                failed_tests.append((test_id, desc, code, expected_codes, leaked, line))

            if leaked:
                leaked_tests += 1

            leak_str = "YES (LEAKED!)" if leaked else "NO (SAFE)"
            print(f"[{test_id}] {desc:56s} -> Status: {code:3d} (Exp: {str(expected_codes):10s}) | Leak: {leak_str} => {status_str}")

        # Post-group liveness confirmation
        alive = check_liveness()
        if not alive:
            print(f"[ERROR] Server died or hung after {group_name}! Immediate failure.")
            return 1

    # Concurrency and High-Stress Resiliency Test
    print("\n>>> Group 8: 並行負荷 & コネクション枯渇耐性 (Concurrency & Pool Resilience)")
    concurrency_target = 25
    print(f"[*] Spawning {concurrency_target} concurrent malicious path traversal workers...")

    results = []
    def worker_thread(w_id: int):
        payload = b"GET /../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
        c, l, h, b = send_raw_request(payload)
        lk = any(tok in b for tok in FORBIDDEN_TOKENS)
        results.append((w_id, c, lk))

    threads = [threading.Thread(target=worker_thread, args=(i,)) for i in range(concurrency_target)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    concurrent_ok = all(r[1] == 400 and not r[2] for r in results)
    total_tests += 1
    if concurrent_ok and len(results) == concurrency_target:
        passed_tests += 1
        print(f"[TRV-CON-01] {concurrency_target} Concurrent Traversal Attacks Handled -> All 400 Bad Request, Leak: NO => PASS")
    else:
        print(f"[TRV-CON-01] {concurrency_target} Concurrent Traversal Attacks Handled -> FAILED (Results: {results}) => FAIL")
        failed_tests.append(("TRV-CON-01", f"{concurrency_target} Concurrent Traversal Attacks", -1, [400], False, "Concurrency failure"))

    # Final Liveness & Integrity Check
    print("\n" + "=" * 80)
    print("Final Integrity & Liveness Check")
    final_alive = check_liveness()
    print(f"[*] Post-Verification Server Liveness Check: {'ALIVE & HEALTHY' if final_alive else 'DEAD/HUNG'}")

    # Summary Report
    print("=" * 80)
    print("VERIFICATION SUMMARY REPORT")
    print(f"Total Test Cases:    {total_tests}")
    print(f"Passed:              {passed_tests}")
    print(f"Failed:              {len(failed_tests)}")
    print(f"Secret Leaks Detected: {leaked_tests}")
    print(f"Pass Rate:           {(passed_tests / total_tests) * 100:.2f}%")

    if failed_tests:
        print("\nFailed Tests Breakdown:")
        for fid, fdesc, fcode, fexp, fleak, fline in failed_tests:
            print(f"  - [{fid}] {fdesc}: Got status {fcode}, Expected {fexp}, Leak={fleak}, Line: {fline}")

    print("=" * 80)

    if passed_tests == total_tests and final_alive and leaked_tests == 0:
        print(">>> OVERALL ASSESSMENT: PASS (100% Robust, Zero Leakage, Zero Crash) <<<")
        return 0
    else:
        print(">>> OVERALL ASSESSMENT: FAIL (Defects Detected) <<<")
        return 1

if __name__ == "__main__":
    sys.exit(run_test_suite())
