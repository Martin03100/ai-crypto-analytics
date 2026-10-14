"""Simple load test: many concurrent visitors on the public pages' API calls; prints response times and errors.

Run it against a LOCAL server, never against production (it is a flood of requests, and the per-IP limits answer
most of them with 429 anyway):

    uvicorn app.main:app --port 8000           # in another terminal, e.g. with RATE_LIMIT_* raised
    python scripts/load_test.py --base http://localhost:8000 --users 50 --seconds 30

429 answers are counted separately: they mean the rate limits work, not that the server failed.
"""

from __future__ import annotations

import argparse
import statistics
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests

PATHS = ("/api/health", "/api/public/config", "/api/public/track-record", "/api/public/status/history",
         "/api/public/calendar", "/api/public/accuracy-insights")


def visitor(base: str, until: float, results: dict, lock: threading.Lock, index: int) -> None:
    session = requests.Session()
    i = index
    while time.monotonic() < until:
        path = PATHS[i % len(PATHS)]
        i += 1
        started = time.monotonic()
        try:
            status = session.get(base + path, timeout=30).status_code
        except requests.RequestException:
            status = 0
        elapsed = (time.monotonic() - started) * 1000
        with lock:
            results[path].append((status, elapsed))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--seconds", type=int, default=20)
    args = parser.parse_args(argv)
    if "onrender.com" in args.base or "netlify.app" in args.base:
        parser.error("refusing to load-test the production site; start a local server instead")

    results: dict = defaultdict(list)
    lock = threading.Lock()
    until = time.monotonic() + args.seconds
    with ThreadPoolExecutor(max_workers=args.users) as pool:
        for n in range(args.users):
            pool.submit(visitor, args.base.rstrip("/"), until, results, lock, n)

    total = sum(len(v) for v in results.values())
    print(f"{args.users} visitors, {args.seconds} s, {total} requests, {total / args.seconds:.0f} per second\n")
    print(f"{'endpoint':34} {'ok':>6} {'429':>6} {'errors':>7} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    failed = 0
    for path in PATHS:
        rows = results.get(path, [])
        ok = [ms for status, ms in rows if 200 <= status < 400]
        limited = sum(1 for status, _ in rows if status == 429)
        errors = len(rows) - len(ok) - limited
        failed += errors
        times = sorted(ok) or [0.0]
        p95 = times[min(len(times) - 1, int(len(times) * 0.95))]
        print(f"{path:34} {len(ok):6} {limited:6} {errors:7} {statistics.median(times):8.0f} {p95:8.0f} {times[-1]:8.0f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
