#!/usr/bin/env python3
"""
Batch2 canary v2 — revised 5-row set with verified Docker images.

Differences from v1 canary:
- New instance selection: DLR-RM__stable-baselines3-2211, Diaoul__subliminal-1327,
  Diaoul__subliminal-1328, MechanicalSoup__MechanicalSoup-455, asottile__pyupgrade-1043
- Dataset patched with docker_image from result.json for 3 instances that lacked it in export
- All 5 Docker images confirmed locally present before launch

Delegates to run_batch2_openhands internals with overridden paths.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load the batch2 driver module
spec = importlib.util.spec_from_file_location(
    "run_batch2_openhands",
    Path(__file__).resolve().parent / "run_batch2_openhands.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Override paths for v2 canary
mod.DATASET_CANARY = ROOT / "data/batch2_stage3_p2p_canary5v2_20260603.jsonl"
mod.RUN_DIR_CANARY = ROOT / "runs/paul_batch2_openhands_canary5v2_20260603"

# Patch write_progress and _step_done/_mark_done to use the overridden RUN_DIR
# (they reference the module-level RUN_DIR which gets set in main())

def main() -> int:
    # Force --canary flag and set RUN_DIR
    import sys as _sys
    _sys.argv = [_sys.argv[0], "--canary"]
    return mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
