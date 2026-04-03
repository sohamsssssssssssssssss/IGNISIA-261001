from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests


def run_once(base_url: str, gstin: str, token: str | None) -> float:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    start = time.perf_counter()
    response = requests.post(f"{base_url}/api/v1/score/{gstin}", headers=headers, timeout=30)
    response.raise_for_status()
    return (time.perf_counter() - start) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple concurrent load test for MSME scoring endpoint")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--gstin", default="29CLEAN5678B1Z2")
    parser.add_argument("--requests", type=int, default=25)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    durations: list[float] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for duration_ms in pool.map(
            lambda _: run_once(args.base_url, args.gstin, args.token),
            range(args.requests),
        ):
            durations.append(duration_ms)

    print(
        {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "p50_ms": round(statistics.median(durations), 2),
            "p95_ms": round(sorted(durations)[max(0, int(len(durations) * 0.95) - 1)], 2),
            "avg_ms": round(statistics.mean(durations), 2),
            "max_ms": round(max(durations), 2),
        }
    )


if __name__ == "__main__":
    main()
