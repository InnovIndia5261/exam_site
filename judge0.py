# judge0.py
import json
import requests

# Use Judge0 CE directly; no secrets.toml needed
ENDPOINT = "https://ce.judge0.com"
HEADERS = {"Content-Type": "application/json"}

def run_single(code: str, language_id: int, stdin: str = None, expected: str = None, timeout=20):
    payload = {
        "source_code": code,
        "language_id": language_id,
        "stdin": stdin or "",
        "expected_output": expected if expected is not None else None
    }
    params = {"base64_encoded": "false", "wait": "true"}
    r = requests.post(f"{ENDPOINT}/submissions", params=params, headers=HEADERS, data=json.dumps(payload), timeout=timeout)
    r.raise_for_status()
    return r.json()

def run_tests(code: str, language_id: int, tests: list):
    passed = 0
    results = []
    for t in tests:
        res = run_single(code, language_id, stdin=t.get("stdin",""), expected=t.get("expected"))
        ok = (res.get("status", {}).get("id") == 3)  # 3 = Accepted
        if ok: passed += 1
        results.append({
            "stdin": t.get("stdin",""),
            "expected": t.get("expected"),
            "status": res.get("status", {}),
            "stdout": res.get("stdout"),
            "stderr": res.get("stderr")
        })
    return {"passed": passed, "total": len(tests), "details": results}
