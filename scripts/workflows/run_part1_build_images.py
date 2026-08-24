#!/usr/bin/env python3
"""
PART 1 (Stages 1-3) — prepare & PERSIST Docker images for a dataset.
Reproducible on GPU-01 and GPU-02.

Stages 1-3 turn a raw issue into a ready-to-solve environment:
  Stage 1  LLM classification / setup planning   (paul-RepoLaunch `collect`, setup phase)
  Stage 2  Docker image build                     -> pouya/stage2_2026:<instance_id>_linux
  Stage 3  Validation (P2P>0 test executes)       (recorded in the dataset row)

The image produced in Stage 2 is the hand-off artifact for Part 2 (Stages 4-6).
This driver guarantees those images are SAVED ON DISK and REUSABLE — never living
only in Docker's build cache, never silently lost to a prune:

  * Built images are normal tagged Docker images (overlay2 on-disk), not cache.
  * Every image is backed up to NFS as a .tar.gz (scripts/ops/backup_stage2_images.py),
    so an accidental `docker image prune -a` is recoverable in minutes, on either node.
  * scripts/ops/cleanup_between_runs.py NEVER deletes pouya/stage2_2026 images.

Modes:
  verify   — report which dataset images are present locally / backed up (default)
  backup   — save all present dataset images to NFS (persist "forever")
  build    — build any MISSING images via the paul-RepoLaunch setup lane, then back up

Usage:
  python scripts/workflows/run_part1_build_images.py --dataset data/matrix_sample3.jsonl
  python scripts/workflows/run_part1_build_images.py --dataset data/matrix_sample3.jsonl --mode backup
  python scripts/workflows/run_part1_build_images.py --dataset data/matrix_sample3.jsonl --mode build
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NFS_BACKUP = Path("/data/22pf2_data/stage2_image_backups")
REPOLAUNCH = Path("/home/22pf2/paul-RepoLaunch")
REPOLAUNCH_PY = REPOLAUNCH / ".." / "anaconda3/envs/paul-repolaunch/bin/python"
PER_IMAGE_TIMEOUT = 3600   # 60 min/instance build cap


def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
def log(m): print(f"[{now()}] {m}", flush=True)
def load(p): return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def image_present(img: str) -> bool:
    return subprocess.run(["docker","image","inspect",img,"--format","{{.Id}}"],
                          capture_output=True).returncode == 0


def backup_present(img: str) -> bool:
    tag = img.split(":")[-1]
    return (NFS_BACKUP / f"{tag}.tar.gz").exists()


def do_verify(rows):
    log(f"Dataset images: {len(rows)}")
    n_present = n_backed = 0
    for d in rows:
        img = d.get("docker_image","")
        p, b = image_present(img), backup_present(img)
        n_present += p; n_backed += b
        log(f"  {'present' if p else 'MISSING':>7} | {'backed-up' if b else 'no-backup':>9} | {img}")
    log(f"Summary: {n_present}/{len(rows)} present locally, {n_backed}/{len(rows)} backed up to NFS")
    return n_present, n_backed


def do_backup(rows):
    """Persist every locally-present image to NFS (idempotent)."""
    cmd = [sys.executable, str(ROOT/"scripts/ops/backup_stage2_images.py"), "backup"]
    log(f"Backing up present pouya/stage2_2026 images to {NFS_BACKUP} ...")
    subprocess.run(cmd, cwd=str(ROOT))


def build_one(d) -> bool:
    """Build a single missing image via the paul-RepoLaunch setup lane (Stage 1-2)."""
    iid = d["instance_id"]; img = d.get("docker_image","")
    if image_present(img):
        log(f"  [{iid}] already present — skip build"); return True
    log(f"  [{iid}] building image {img} (setup-only, ~up to {PER_IMAGE_TIMEOUT//60}min)...")
    # The proven builder is paul-RepoLaunch `collect` in setup-only/overwrite mode.
    # We invoke it per-instance. If the RepoLaunch env is unavailable, we report and
    # leave a clear manual instruction rather than silently failing.
    if not Path(REPOLAUNCH_PY).resolve().exists():
        log(f"  [{iid}] SKIP: RepoLaunch python not found at {REPOLAUNCH_PY}. "
            f"Build manually with the node1 rebuild lane (see WORKFLOW.md Part 1).")
        return False
    queue = REPOLAUNCH / f"configs/_part1_build_{iid}.json"
    queue.write_text(json.dumps({"instances":[d], "setup_only": True, "overwrite": True}))
    t0 = time.time()
    try:
        r = subprocess.run(
            [str(Path(REPOLAUNCH_PY).resolve()), "-m", "launch.scripts.collect",
             "--queue", str(queue), "--setup-only", "--overwrite", "--max-workers", "1"],
            cwd=str(REPOLAUNCH), capture_output=True, text=True, timeout=PER_IMAGE_TIMEOUT)
        ok = image_present(img)
        log(f"  [{iid}] {'BUILT' if ok else 'BUILD FAILED'} in {time.time()-t0:.0f}s"
            + ("" if ok else f"  (stderr tail: {r.stderr[-200:]})"))
        return ok
    except subprocess.TimeoutExpired:
        log(f"  [{iid}] BUILD TIMEOUT after {PER_IMAGE_TIMEOUT}s"); return False
    except Exception as e:
        log(f"  [{iid}] BUILD ERROR: {e}"); return False


def do_build(rows):
    missing = [d for d in rows if not image_present(d.get("docker_image",""))]
    log(f"{len(missing)}/{len(rows)} images missing — building")
    built = sum(build_one(d) for d in missing)
    log(f"Built {built}/{len(missing)} missing images")
    do_backup(rows)   # persist everything (newly built + pre-existing)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--mode", choices=["verify","backup","build"], default="verify")
    args = ap.parse_args()
    rows = load(args.dataset)
    NFS_BACKUP.mkdir(parents=True, exist_ok=True)
    log(f"PART 1 (Stages 1-3) — mode={args.mode} — dataset={args.dataset} ({len(rows)} issues)")
    if args.mode == "verify": do_verify(rows)
    elif args.mode == "backup": do_backup(rows); do_verify(rows)
    elif args.mode == "build": do_build(rows); do_verify(rows)
    log("PART 1 done. Hand off to Part 2 (run_matrix_test.py / run_node1_full383_qwen3.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
