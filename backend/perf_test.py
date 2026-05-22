"""
Performance test script for the doss backend. This is very much ai generated. 
Usage: python perf_test.py [--url http://localhost:5000]
"""
import argparse
import os
import statistics
import time
import threading
from collections import defaultdict

import requests

BASE_URL = "http://localhost:5000"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=BASE_URL)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--workers", type=int, default=50)
    p.add_argument("--duration", type=int, default=10)
    p.add_argument(
        "--token",
        default=None,
        help="Bearer token used to call /login before hitting protected endpoints",
    )
    p.add_argument(
        "--token-env",
        default="DOSS_BEARER_TOKEN",
        help="Environment variable name to read bearer token from if --token is not set",
    )
    p.add_argument(
        "--skip-login",
        action="store_true",
        help="Skip /login even if token is present (useful for debugging 401s)",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Print endpoint response snippets for non-200 responses and login details",
    )
    return p.parse_args()


def fmt(ms_list):
    if not ms_list:
        return "no data"
    s = sorted(ms_list)
    return (
        f"avg={statistics.mean(s):.1f}ms  "
        f"p50={s[len(s)//2]:.1f}ms  "
        f"p95={s[int(len(s)*0.95)]:.1f}ms  "
        f"p99={s[int(len(s)*0.99)]:.1f}ms  "
        f"min={s[0]:.1f}ms  max={s[-1]:.1f}ms"
    )


def extract_error_text(response, limit=300):
    body = response.text.strip().replace("\n", " ")
    if len(body) > limit:
        body = f"{body[:limit]}..."
    return f"status={response.status_code}, body={body or '<empty>'}"


def discover_payload(base_url, session, debug=False):
    """Build a real /question_post payload from live /cat_request data."""
    r = session.get(f"{base_url}/cat_request", timeout=5)
    if debug and r.status_code != 200:
        print(f"DEBUG discover_payload: {extract_error_text(r)}")
    r.raise_for_status()
    data = r.json()
    max_q = data["max_questions"]

    payload_course = {}
    for course_code, categories in max_q.items():
        payload_course[course_code] = {}
        for cat_name, count in categories.items():
            if count > 0:
                payload_course[course_code][cat_name] = min(count, 3)
        if not payload_course[course_code]:
            del payload_course[course_code]

    return {"questions_request": {"course": payload_course}}


def timed_get(url):
    s = requests.Session()
    t = time.perf_counter()
    r = s.get(url, timeout=10)
    ms = (time.perf_counter() - t) * 1000
    return ms, r.status_code


def timed_post(url, payload):
    s = requests.Session()
    t = time.perf_counter()
    r = s.post(url, json=payload, timeout=10)
    ms = (time.perf_counter() - t) * 1000
    return ms, r.status_code


def timed_get_with_session(session, url):
    t = time.perf_counter()
    r = session.get(url, timeout=10)
    ms = (time.perf_counter() - t) * 1000
    return ms, r.status_code, r


def timed_post_with_session(session, url, payload):
    t = time.perf_counter()
    r = session.post(url, json=payload, timeout=10)
    ms = (time.perf_counter() - t) * 1000
    return ms, r.status_code, r


def resolve_token(args):
    if args.token:
        return args.token
    token = os.getenv(args.token_env)
    if token:
        return token
    return None


def login_session(base_url, token, debug=False):
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    r = session.post(f"{base_url}/login", timeout=10)
    if debug:
        print(f"DEBUG /login: {extract_error_text(r)}")
    if r.status_code != 200:
        raise RuntimeError(
            "Login failed. "
            "Provide a valid bearer token via --token or token env var. "
            f"Response: {extract_error_text(r)}"
        )
    return session


def benchmark(base_url, warmup, n, q_payload, session=None, debug=False):
    if session is None:
        endpoints = [("GET  /ping", lambda: (*timed_get(f"{base_url}/ping"), None))]
        if q_payload is not None:
            endpoints.extend(
                [
                    ("GET  /cat_request", lambda: (*timed_get(f"{base_url}/cat_request"), None)),
                    ("POST /question_post", lambda: (*timed_post(f"{base_url}/question_post", q_payload), None)),
                ]
            )
        banner = "\n-- Single-threaded latency benchmark (fresh session per req) --"
    else:
        endpoints = [("GET  /ping", lambda: timed_get_with_session(session, f"{base_url}/ping"))]
        if q_payload is not None:
            endpoints.extend(
                [
                    ("GET  /cat_request", lambda: timed_get_with_session(session, f"{base_url}/cat_request")),
                    ("POST /question_post", lambda: timed_post_with_session(session, f"{base_url}/question_post", q_payload)),
                ]
            )
        banner = "\n-- Single-threaded latency benchmark (shared authenticated session) --"

    print(banner)
    for name, fn in endpoints:
        for _ in range(warmup):
            fn()
        times = []
        errors = 0
        for _ in range(n):
            ms, status, response = fn()
            if status == 200:
                times.append(ms)
            else:
                errors += 1
                if debug and response is not None:
                    print(f"    DEBUG {name}: {extract_error_text(response)}")
        print(f"\n  {name}  (n={n}, errors={errors})")
        print(f"    {fmt(times)}")


def load_test(base_url, workers, duration_s, q_payload, session_factory=None, debug=False):
    print(f"\n-- Concurrent load test ({workers} workers, {duration_s}s) --")

    results = defaultdict(list)
    errors = defaultdict(int)
    lock = threading.Lock()
    stop = threading.Event()

    def worker():
        worker_session = session_factory() if session_factory else requests.Session()
        worker_endpoints = [("GET  /ping", lambda: timed_get_with_session(worker_session, f"{base_url}/ping"))]
        if q_payload is not None:
            worker_endpoints.extend(
                [
                    ("GET  /cat_request", lambda: timed_get_with_session(worker_session, f"{base_url}/cat_request")),
                    ("POST /question_post", lambda: timed_post_with_session(
                        worker_session,
                        f"{base_url}/question_post", q_payload
                    )),
                ]
            )
        while not stop.is_set():
            for name, fn in worker_endpoints:
                if stop.is_set():
                    break
                try:
                    ms, status, response = fn()
                    with lock:
                        if status == 200:
                            results[name].append(ms)
                        else:
                            errors[name] += 1
                            if debug and response is not None and errors[name] <= 3:
                                print(f"    DEBUG {name}: {extract_error_text(response)}")
                except Exception:
                    with lock:
                        errors[name] += 1

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    time.sleep(duration_s)
    stop.set()
    for t in threads:
        t.join(timeout=5)

    total_ok = sum(len(v) for v in results.values())
    total_err = sum(errors.values())
    total = total_ok + total_err
    print(f"  Total: {total} reqs  ({total/duration_s:.0f} req/s)"
          f"  ok={total_ok}  errors={total_err}")

    for name in sorted(results):
        times = results[name]
        print(f"\n  {name}  (ok={len(times)}, errors={errors[name]})")
        print(f"    {fmt(times)}")


if __name__ == "__main__":
    args = parse_args()
    token = resolve_token(args)

    try:
        r = requests.get(f"{args.url}/ping", timeout=3)
        assert r.json() == {"pong": True}
        print(f"Backend reachable at {args.url}")
    except Exception as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)

    benchmark_session = None
    session_factory = None
    if not args.skip_login and token:
        try:
            benchmark_session = login_session(args.url, token, debug=args.debug)
            print("Authenticated session created via /login")
            session_factory = lambda: login_session(args.url, token, debug=False)
        except Exception as e:
            print(f"ERROR: {e}")
            raise SystemExit(1)
    elif args.skip_login:
        print("Skipping /login as requested")
    else:
        print(
            "No token provided. Protected endpoints may return 401. "
            "Pass --token or set DOSS_BEARER_TOKEN."
        )

    print("Discovering live courses/categories...")
    discovery_session = benchmark_session or requests.Session()
    q_payload = None
    try:
        q_payload = discover_payload(args.url, discovery_session, debug=args.debug)
        for code, cats in q_payload["questions_request"]["course"].items():
            for cat, n in cats.items():
                print(f"  {code} / {cat} -> {n} questions")
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status == 401:
            print(
                "Could not access /cat_request (401). "
                "Continuing with unauthenticated ping-only perf run."
            )
        else:
            raise

    benchmark(args.url, args.warmup, args.n, q_payload, session=benchmark_session, debug=args.debug)
    load_test(
        args.url,
        args.workers,
        args.duration,
        q_payload,
        session_factory=session_factory,
        debug=args.debug,
    )
    print("\nDone.")
