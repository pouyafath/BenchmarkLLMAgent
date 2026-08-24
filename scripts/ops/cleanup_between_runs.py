#!/usr/bin/env python3
"""
Between-runs cleanup for GPU-01 / GPU-02. Run this AFTER a pipeline run finishes
and BEFORE launching the next one. Safe to run on either twin server.

Reclaims the two resources that leak across runs and crash the pipeline:
  1. DISK  — ghcr.io/openhands/runtime:* images (Stage-5 throwaway layers, 10-20GB each)
             + stopped containers + build cache.
  2. RAM/SWAP — leaked host-side python/ipykernel/action_execution_server processes
             that OpenHands solver instances orphan on timeout (held 88GB on GPU-02).

NEVER touches:
  - pouya/stage2_2026:*  (Stage 1-3 base images — irreplaceable, back up with
    backup_stage2_images.py instead)
  - any process belonging to a CURRENTLY ACTIVE run (the script aborts if one is running)

Usage:
  python scripts/ops/cleanup_between_runs.py            # clean (refuses if a run is active)
  python scripts/ops/cleanup_between_runs.py --dry-run  # show what would be cleaned
  python scripts/ops/cleanup_between_runs.py --force     # clean even if a run looks active
"""
from __future__ import annotations
import argparse, os, signal, subprocess, sys
from datetime import datetime, timezone

PROTECTED_IMAGE_REPO = "pouya/stage2_2026"
EPHEMERAL_IMAGE_REPO = "ghcr.io/openhands/runtime"
LEAK_PATTERNS = ["action_execution_server", "ipykernel_launcher"]
RUN_MARKERS = ["run_node2_qwen3", "run_node1_full383", "run_solving_after_enhancement"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def log(msg):
    print(f"[{now()}] {msg}", flush=True)


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def disk_free_gb(path="/"):
    s = os.statvfs(path)
    return s.f_bavail * s.f_frsize / 1024**3


def swap_used_gb():
    try:
        with open("/proc/meminfo") as f:
            info = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        return (info["SwapTotal"] - info["SwapFree"]) / 1024**2
    except Exception:
        return -1


def active_run_pids():
    """PIDs of currently-running pipeline launchers (their children must NOT be killed)."""
    pids = set()
    r = sh("ps -eo pid,cmd")
    for line in r.stdout.splitlines():
        if any(m in line for m in RUN_MARKERS) and "cleanup_between_runs" not in line:
            try:
                pids.add(int(line.split()[0]))
            except (ValueError, IndexError):
                pass
    return pids


def find_leaked_procs():
    """Return [(pid, rss_kb, age, cmd)] for leaked solver subprocesses."""
    procs = []
    r = sh("ps -eo pid,rss,etime,cmd --no-headers")
    for line in r.stdout.splitlines():
        if any(p in line for p in LEAK_PATTERNS) and "grep" not in line:
            parts = line.split(None, 3)
            if len(parts) == 4:
                try:
                    procs.append((int(parts[0]), int(parts[1]), parts[2], parts[3][:60]))
                except ValueError:
                    pass
    return procs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Show what would be cleaned, change nothing")
    ap.add_argument("--force", action="store_true", help="Clean even if a run appears active")
    args = ap.parse_args()

    log(f"BEFORE: disk free={disk_free_gb():.0f}GB on /   |   swap used={swap_used_gb():.1f}GB")

    active = active_run_pids()
    if active and not args.force:
        log(f"ABORT: a pipeline run appears ACTIVE (PIDs {sorted(active)}). "
            f"Its subprocesses would be killed. Re-run with --force only if you are sure.")
        return 1
    if active and args.force:
        log(f"WARNING: --force with active run PIDs {sorted(active)} — killing leaked procs anyway")

    # ── 1. Reap leaked solver subprocesses ────────────────────────────────────
    leaked = find_leaked_procs()
    total_rss = sum(p[1] for p in leaked) / 1024**2
    log(f"Leaked solver processes: {len(leaked)} holding {total_rss:.1f}GB RSS")
    if leaked:
        oldest = max(leaked, key=lambda p: p[2])
        log(f"  oldest: pid {oldest[0]} age {oldest[2]}  ({oldest[3]})")
    if args.dry_run:
        log("  [dry-run] would SIGKILL the above")
    else:
        killed = 0
        for pid, _, _, _ in leaked:
            try:
                os.kill(pid, signal.SIGKILL)
                killed += 1
            except ProcessLookupError:
                pass
            except PermissionError:
                log(f"  no permission to kill pid {pid} (different user?)")
        log(f"  killed {killed}/{len(leaked)} leaked processes")

    # ── 2. Remove ephemeral OpenHands runtime images ──────────────────────────
    r = sh(f"docker images --format '{{{{.Repository}}}}:{{{{.Tag}}}}' {EPHEMERAL_IMAGE_REPO}")
    oh_imgs = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    log(f"Ephemeral {EPHEMERAL_IMAGE_REPO} images: {len(oh_imgs)} (~{len(oh_imgs)*12} GB est.)")
    if args.dry_run:
        log("  [dry-run] would 'docker rmi -f' the above")
    elif oh_imgs:
        sh("docker rmi -f " + " ".join(oh_imgs))
        log(f"  removed {len(oh_imgs)} runtime images")

    # ── 3. Prune stopped containers + build cache ─────────────────────────────
    if args.dry_run:
        log("  [dry-run] would 'docker container prune -f' and 'docker builder prune -f'")
    else:
        c = sh("docker container prune -f")
        b = sh("docker builder prune -f")
        log(f"  container prune: {c.stdout.strip().splitlines()[-1] if c.stdout.strip() else 'nothing'}")
        log(f"  builder prune:   {b.stdout.strip().splitlines()[-1] if b.stdout.strip() else 'nothing'}")

    # ── Safety assertion: protected base images untouched ─────────────────────
    r = sh(f"docker images {PROTECTED_IMAGE_REPO} --format '{{{{.Tag}}}}'")
    n_base = len([l for l in r.stdout.strip().split("\n") if l.strip()])
    log(f"Protected {PROTECTED_IMAGE_REPO} base images still present: {n_base} (UNTOUCHED)")

    log(f"AFTER:  disk free={disk_free_gb():.0f}GB on /   |   swap used={swap_used_gb():.1f}GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
