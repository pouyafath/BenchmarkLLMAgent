#!/usr/bin/env python3
"""
Re-evaluate Stage 5 results for the 2026-06-01 openhands pilot-40 run
with corrected test name matching and P2P-gated resolution criteria.

This is a thin wrapper around pilot40_reeval_lib.

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/reeval_pilot40_openhands.py
"""

from __future__ import annotations

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot40_reeval_lib import reeval_run

RUN_DIR = Path("/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601")


def main() -> int:
    results = reeval_run(RUN_DIR, expected_count=40)
    if not results:
        return 1
    print("\nDone. Now regenerate the Stage 6 report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
