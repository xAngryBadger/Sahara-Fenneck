"""Benchmark script for Fennec Excel performance measurement.

Usage:
    python scripts/bench.py [--iterations N] [--file path.xlsx]

Benchmarks:
    1. load_settings() — cached vs uncached
    2. index_file_multi() — single-sheet vs multi-sheet
    3. get_workspace_summary() — text generation
    4. Sheet name listing — cached vs uncached
    5. NIM client availability check
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.app_settings import load_settings  # noqa: E402
from src.indexing.excel_reader import get_workspace_summary, index_file_multi, index_from_path  # noqa: E402


def bench_settings(iterations: int) -> None:
    print("\n--- load_settings() ---")
    from src.config.app_settings import _read_settings_from_disk

    _read_settings_from_disk.cache_clear()
    t0 = time.monotonic()
    for _ in range(iterations):
        _read_settings_from_disk.cache_clear()
        load_settings()
    uncached = (time.monotonic() - t0) / iterations

    load_settings()
    t0 = time.monotonic()
    for _ in range(iterations):
        load_settings()
    cached = (time.monotonic() - t0) / iterations

    print(f"  Uncached: {uncached * 1000:.2f}ms/call")
    print(f"  Cached:   {cached * 1000:.4f}ms/call")
    print(f"  Speedup:  {uncached / cached:.0f}x")


def bench_indexing(file_path: str, iterations: int) -> None:
    print(f"\n--- index_file_multi() [{file_path}] ---")
    if not Path(file_path).exists():
        print("  SKIP: file not found")
        return

    t0 = time.monotonic()
    for _ in range(iterations):
        index_file_multi(file_path, include_all_sheets=True)
    multi_time = (time.monotonic() - t0) / iterations

    t0 = time.monotonic()
    for _ in range(iterations):
        index_file_multi(file_path, include_all_sheets=False)
    single_time = (time.monotonic() - t0) / iterations

    t0 = time.monotonic()
    for _ in range(iterations):
        index_from_path(file_path)
    from_path_time = (time.monotonic() - t0) / iterations

    print(f"  All sheets:     {multi_time * 1000:.1f}ms/call")
    print(f"  Active sheet:   {single_time * 1000:.1f}ms/call")
    print(f"  index_from_path:{from_path_time * 1000:.1f}ms/call")
    print(f"  Speedup (active vs all): {multi_time / single_time:.1f}x")


def bench_summary(file_path: str, iterations: int) -> None:
    print(f"\n--- get_workspace_summary() [{file_path}] ---")
    if not Path(file_path).exists():
        print("  SKIP: file not found")
        return

    ws = index_from_path(file_path)
    t0 = time.monotonic()
    for _ in range(iterations):
        get_workspace_summary(ws)
    elapsed = (time.monotonic() - t0) / iterations
    print(f"  Per call: {elapsed * 1000:.2f}ms")


def bench_sheet_names(file_path: str, iterations: int) -> None:
    print(f"\n--- Sheet name listing [{file_path}] ---")
    if not Path(file_path).exists():
        print("  SKIP: file not found")
        return

    from src.agent.runner import _cached_sheet_names

    _cached_sheet_names.cache_clear()
    t0 = time.monotonic()
    for _ in range(iterations):
        _cached_sheet_names.cache_clear()
        _cached_sheet_names(file_path)
    uncached = (time.monotonic() - t0) / iterations

    _cached_sheet_names(file_path)
    t0 = time.monotonic()
    for _ in range(iterations):
        _cached_sheet_names(file_path)
    cached = (time.monotonic() - t0) / iterations

    print(f"  Uncached: {uncached * 1000:.2f}ms/call")
    print(f"  Cached:   {cached * 1000:.4f}ms/call")
    print(f"  Speedup:  {uncached / cached:.0f}x")


def bench_nim(iterations: int) -> None:
    print("\n--- NIM client ---")
    try:
        from src.agent.llm_client import create_client
        from src.integrations.token_store import get_nim_api_key

        key = get_nim_api_key()
        if not key:
            print("  SKIP: no NIM API key")
            return

        client = create_client({"llm_backend": "nim"})
        print(f"  Client type: {type(client).__name__}")
        print(f"  Model: {client.model}")
        print("  Availability check: SKIPPED (slow — use manual test)")
        print("  Generate: SKIPPED (slow — use manual test)")
    except Exception as e:
        print(f"  ERROR: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fennec Excel benchmarks")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per benchmark")
    parser.add_argument("--file", type=str, default="", help="XLSX file for indexing benchmarks")
    args = parser.parse_args()

    print(f"Fennec Excel Benchmark Suite (iterations={args.iterations})")
    bench_settings(args.iterations)
    if args.file:
        bench_indexing(args.file, args.iterations)
        bench_summary(args.file, args.iterations * 10)
        bench_sheet_names(args.file, args.iterations)
    else:
        print("\n--- Indexing benchmarks ---")
        print("  SKIP: no --file provided (use --file path.xlsx)")
    bench_nim(args.iterations)
    print("\nDone.")


if __name__ == "__main__":
    main()
