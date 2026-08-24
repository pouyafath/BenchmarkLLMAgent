#!/usr/bin/env python3
"""
Batch2 canary confirmation replay — 5 rows from patched dataset.

Purpose:
    Confirm that Fix A (eval field patching) and Fix B (evaluation.py empty-parser fallback)
    together eliminate the eval_framework_error failure mode seen in canary v2.

Key differences from canary v2:
    - Dataset: batch2_stage3_p2p_canary5_replay_20260603.jsonl
      (5 rows from batch2_stage3_p2p_55_patched_20260603.jsonl — all eval fields present)
    - Run dir: runs/paul_batch2_openhands_canary5_replay_20260603/
    - Stage 5e must complete inside a single pipeline invocation (no post-hoc replay)
    - evaluation.py fix (empty parser → default_pytest_parser) is pre-applied

Same 5 canary instances as v2:
    DLR-RM__stable-baselines3-2211, Diaoul__subliminal-1327, Diaoul__subliminal-1328,
    MechanicalSoup__MechanicalSoup-455, asottile__pyupgrade-1043
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

spec = importlib.util.spec_from_file_location(
    "run_batch2_openhands",
    Path(__file__).resolve().parent / "run_batch2_openhands.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Override paths for replay
mod.DATASET_CANARY = ROOT / "data/batch2_stage3_p2p_canary5_replay_20260603.jsonl"
mod.RUN_DIR_CANARY = ROOT / "runs/paul_batch2_openhands_canary5_replay_20260603"


def main() -> int:
    sys.argv = [sys.argv[0], "--canary"]
    return mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
