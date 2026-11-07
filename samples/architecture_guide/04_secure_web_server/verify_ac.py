#!/usr/bin/env python3
"""
StateSSA 04_secure_web_server Acceptance Criteria (AC-01 ~ AC-17) Verification Suite
"""

import os
import sys
import time
import socket
import subprocess
import shutil

SERVER_PORT = 18080
SERVER_HOST = "127.0.0.1"
SECRET_CONTENT = "TOP_SECRET_HIMITU_DO_NOT_LEAK_TOKEN_9999"

def setup_test_environment(work_dir):
    pub_dir = os.path.join(work_dir, "public")
    css_dir = os.path.join(pub_dir, "css")
    os.makedirs(css_dir, exist_ok=True)

    # 1. Normal files
    with open(os.path.join(pub_dir, "index.html"), "w") as f:
        f.write("<!DOCTYPE html><html><body><h1>StateSSA Secure Server</h1></body></html>\n")

    with open(os.path.join(css_dir, "style.css"), "w") as f:
        f.write("body { margin: 0; background: #fafafa; color: #111; }\n")

    # 2. Secret file outside docroot
    secret_path = "/tmp/himitu.txt"
    with open(secret_path, "w") as f:
        f.write(SECRET_CONTENT + "\n")

    # Also place himitu.txt in work_dir for traversal tests (../../himitu.txt)
    with open(os.path.join(work_dir, "himitu.txt"), "w") as f:
        f.write(SECRET_CONTENT + "\n")

    # 3. Symlink inside docroot pointing to secret file (AC-17)
    symlink_path = os.path.join(pub_dir, "secret_link.txt")
    if os.path.lexists(symlink_path):
        os.remove(symlink_path)
    os.symlink(secret_path, symlink_path)

def send_raw_request(raw_data: bytes, timeout: float = 3.0) -> (int, str, bytes):
    """
    Sends raw request bytes to the server, returns (status_code, status_line, body).
    If connection is closed without HTTP response, returns (-1, 'CLOSED', b'').
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((SERVER_HOST, SERVER_PORT))
        s.sendall(raw_data)
        
        response_bytes = b""
        while True:
            try:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response_bytes += chunk
                if b"\r\n\r\n" in response_bytes:
                    # For GET requests without huge body, short read is sufficient
                    break
            except socket.timeout:
                break
        s.close()

        if not response_bytes:
            return (-1, "CONNECTION_CLOSED", b"")

        header_part = response_bytes.split(b"\r\n\r\n")[0]
        body_part = response_bytes[len(header_part) + 4:] if b"\r\n\r\n" in response_bytes else b""
        
        lines = header_part.split(b"\r\n")
        first_line = lines[0].decode("latin-1", errors="replace")
        parts = first_line.split(" ")
        if len(parts) >= 2 and parts[1].isdigit():
            status_code = int(parts[1])
        else:
            status_code = 0
        return (status_code, first_line, body_part)
    except Exception as e:
        return (-2, str(e), b"")

def run_all_tests():
    work_dir = os.path.abspath("/home/beep/work_llm/work_StateSSA/samples/architecture_guide/04_secure_web_server")
    setup_test_environment(work_dir)

    print("================================================================================")
    print("StateSSA Secure Web Server: Acceptance Criteria (AC-01 ~ AC-17) Test Suite")
    print("================================================================================")

    test_cases = [
        ("AC-01", "Simple Traversal", b"GET /../himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400, 404]),
        ("AC-02", "Multi Traversal", b"GET /foo/../../var/secret/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400, 404]),
        ("AC-03", "Backslash Injection", b"GET /..\\himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400]),
        ("AC-04", "URL-Encoded Traversal", b"GET /%2e%2e%2fhimitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400, 404]),
        ("AC-05", "Partial Encoded Traversal", b"GET /..%2fhimitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400, 404]),
        ("AC-06", "Double Encoded Traversal", b"GET /%252e%252e%252fhimitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400, 404]),
        ("AC-07", "NULL Byte Injection (%00)", b"GET /himitu.txt%00.html HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400]),
        ("AC-08", "Raw NULL Byte (\\0)", b"GET /safe\x00/himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400]),
        ("AC-09", "Dot-Slash Anomaly (....//)", b"GET /....//himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400]),
        ("AC-10", "Overlong Path Buffer Overflow", b"GET /" + (b"A" * 2000) + b" HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400, 414]),
        ("AC-11", "Missing Leading Slash", b"GET himitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400]),
        ("AC-12", "Overlong UTF-8 Slash", b"GET /\xc0\xafhimitu.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400]),
        ("AC-13", "Control Character (0x01)", b"GET /foo\x01bar.html HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [400]),
        ("AC-14", "Non-Existent File", b"GET /not_exist.html HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [404]),
        ("AC-15", "Normal File (index.html)", b"GET /index.html HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [200]),
        ("AC-16", "Normal Subdirectory (css/style.css)", b"GET /css/style.css HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [200]),
        ("AC-17", "Symlink Traversal (secret_link.txt)", b"GET /secret_link.txt HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [403, 404]),
    ]

    all_passed = True
    for test_id, desc, req_bytes, expected_codes in test_cases:
        code, line, body = send_raw_request(req_bytes)
        
        # Invariant: Secret content must NEVER leak
        leaked = SECRET_CONTENT.encode("utf-8") in body
        
        status_ok = code in expected_codes
        passed = status_ok and not leaked
        if not passed:
            all_passed = False

        status_str = "PASS" if passed else "FAIL"
        print(f"[{test_id}] {desc:36s} -> Status: {code:3d} (Expected: {expected_codes}) | Secret Leaked: {leaked} => {status_str}")
        if not passed:
            print(f"     Line: {line}")
            print(f"     Body: {body[:100]}")

    # Baseline tests: GET /, POST /echo, GET /baseline11
    print("--------------------------------------------------------------------------------")
    print("Baseline Regression Tests:")
    base_cases = [
        ("BASE-ROOT", "GET / -> 200 OK", b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [200], b"Hello from StateSSA!"),
        ("BASE-ECHO", "POST /echo -> 200 OK", b"POST /echo HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 9\r\n\r\nStateSSA!", [200], b"StateSSA!"),
        ("BASE-SUM",  "GET /baseline11?a=42&b=58 -> 100", b"GET /baseline11?a=42&b=58 HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n", [200], b"100"),
    ]
    for b_id, b_desc, b_req, b_codes, b_substr in base_cases:
        b_code, b_line, b_body = send_raw_request(b_req)
        b_passed = (b_code in b_codes) and (b_substr in b_body)
        if not b_passed:
            all_passed = False
        print(f"[{b_id:9s}] {b_desc:32s} -> Status: {b_code:3d} | Body Matched: {b_substr in b_body} => {'PASS' if b_passed else 'FAIL'}")

    print("================================================================================")
    
    # Cleanup temporary secrets
    try:
        if os.path.exists(os.path.join(work_dir, "himitu.txt")):
            os.remove(os.path.join(work_dir, "himitu.txt"))
        if os.path.exists("/tmp/himitu.txt"):
            os.remove("/tmp/himitu.txt")
        symlink_path = os.path.join(work_dir, "public", "secret_link.txt")
        if os.path.lexists(symlink_path):
            os.remove(symlink_path)
    except Exception as e:
        print(f"Warning during cleanup: {e}")

    if all_passed:
        print(">>> ALL ACCEPTANCE CRITERIA (AC-01 ~ AC-17) AND BASELINE TESTS PASSED 100%! <<<")
        return 0
    else:
        print(">>> SOME VERIFICATION TESTS FAILED! <<<")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
