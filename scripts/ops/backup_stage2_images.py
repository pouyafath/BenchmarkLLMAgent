#!/usr/bin/env python3
"""
Backup / restore / verify pouya/stage2_2026 Docker images to/from NFS.

These images are irreplaceable without re-running Stage 2 (hours of work).
They are the main victim of accidental `docker image prune -a` runs.
ghcr.io/openhands/runtime images are intentionally EXCLUDED — they are
rebuilt fresh during every run and are safe to prune.

Usage:
  # Save all pouya/stage2_2026 images present locally to NFS:
  python scripts/ops/backup_stage2_images.py backup

  # Check which images from a dataset are missing locally (fast, no NFS needed):
  python scripts/ops/backup_stage2_images.py verify --dataset data/node2_gpu02_ready_stage45_20260614.jsonl

  # Restore missing images from NFS backup:
  python scripts/ops/backup_stage2_images.py restore --dataset data/node2_gpu02_ready_stage45_20260614.jsonl
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone

NFS_BACKUP_DIR = Path("/data/22pf2_data/stage2_image_backups")
REPO = "pouya/stage2_2026"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _local_images() -> set[str]:
    r = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", REPO],
        capture_output=True, text=True)
    return {l.strip() for l in r.stdout.strip().split("\n") if l.strip()}


def _dataset_images(dataset_path: str) -> list[str]:
    images = []
    with open(dataset_path) as f:
        for line in f:
            d = json.loads(line.strip())
            img = d.get("docker_image", "")
            if img:
                images.append(img)
    return images


def cmd_verify(args):
    dataset_images = _dataset_images(args.dataset)
    local = _local_images()
    missing = [img for img in dataset_images if img not in local]
    present = [img for img in dataset_images if img in local]

    print(f"[{_now()}] Dataset: {args.dataset}")
    print(f"  Required: {len(dataset_images)}")
    print(f"  Present:  {len(present)}")
    print(f"  Missing:  {len(missing)}")
    if missing:
        print(f"\nMISSING IMAGES:")
        for img in missing:
            tag = img.split(":")[-1]
            backup_path = NFS_BACKUP_DIR / f"{tag}.tar.gz"
            status = "✓ backup exists" if backup_path.exists() else "✗ no backup"
            print(f"  {img}  [{status}]")
        print(f"\nTo restore: python scripts/ops/backup_stage2_images.py restore --dataset {args.dataset}")
        return 1
    else:
        print(f"\nAll {len(present)} images present locally. OK.")
        return 0


def cmd_backup(args):
    local = _local_images()
    if not local:
        print(f"No {REPO} images found locally. Nothing to backup.")
        return 1

    NFS_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[{_now()}] Backing up {len(local)} images to {NFS_BACKUP_DIR}")

    saved, skipped, failed = 0, 0, 0
    for img in sorted(local):
        tag = img.split(":")[-1]
        dest = NFS_BACKUP_DIR / f"{tag}.tar.gz"
        if dest.exists() and not args.force:
            skipped += 1
            continue
        print(f"  Saving {img} ...", end="", flush=True)
        t0 = time.time()
        r = subprocess.run(
            f"docker save {img} | gzip > {dest}",
            shell=True, capture_output=True)
        if r.returncode == 0:
            size_mb = dest.stat().st_size / 1024**2
            print(f" {size_mb:.0f} MB ({time.time()-t0:.0f}s)")
            saved += 1
        else:
            print(f" FAILED: {r.stderr.decode()[:80]}")
            if dest.exists():
                dest.unlink()
            failed += 1

    print(f"\nDone: {saved} saved, {skipped} skipped (already backed up), {failed} failed")
    return 0 if failed == 0 else 1


def cmd_restore(args):
    dataset_images = _dataset_images(args.dataset)
    local = _local_images()
    missing = [img for img in dataset_images if img not in local]

    if not missing:
        print(f"All {len(dataset_images)} images already present. Nothing to restore.")
        return 0

    print(f"[{_now()}] Restoring {len(missing)} missing images from {NFS_BACKUP_DIR}")
    restored, failed, no_backup = 0, 0, 0
    for img in missing:
        tag = img.split(":")[-1]
        backup_path = NFS_BACKUP_DIR / f"{tag}.tar.gz"
        if not backup_path.exists():
            print(f"  NO BACKUP: {img}")
            no_backup += 1
            continue
        print(f"  Restoring {img} ...", end="", flush=True)
        t0 = time.time()
        r = subprocess.run(
            f"gunzip -c {backup_path} | docker load",
            shell=True, capture_output=True)
        if r.returncode == 0:
            print(f" OK ({time.time()-t0:.0f}s)")
            restored += 1
        else:
            print(f" FAILED: {r.stderr.decode()[:80]}")
            failed += 1

    print(f"\nDone: {restored} restored, {failed} failed, {no_backup} had no backup")
    if no_backup > 0:
        print(f"  Images with no backup must be rebuilt via Stage 2 (paul-RepoLaunch).")
    return 0 if (failed == 0 and no_backup == 0) else 1


def main():
    p = argparse.ArgumentParser(description="Backup/restore pouya/stage2_2026 Docker images")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("backup", help="Save all local pouya/stage2_2026 images to NFS")
    b.add_argument("--force", action="store_true", help="Overwrite existing backups")

    v = sub.add_parser("verify", help="Check which dataset images are missing locally")
    v.add_argument("--dataset", required=True, help="JSONL dataset file")

    res = sub.add_parser("restore", help="Restore missing images from NFS backup")
    res.add_argument("--dataset", required=True, help="JSONL dataset file")

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return 1

    cmds = {"backup": cmd_backup, "verify": cmd_verify, "restore": cmd_restore}
    return cmds[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
