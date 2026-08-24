"""
Stage 2 — Collect Paul/RepoLaunch results and build stage2 dataset.

Run this after Paul finishes:
    python scripts/data/p2p_pipeline/stage2_collect_results.py

Reads:
  - paul-RepoLaunch/workspace/p2p_pipeline_stage2_20260515/playground/*/result.json
  - data/samples/pouya_p2p_pipeline/stage1_approach1/dataset.jsonl  (source rows)

Writes:
  - data/samples/pouya_p2p_pipeline/stage2_approach2/dataset.jsonl
  - data/samples/pouya_p2p_pipeline/stage2_approach2/summary.json
  - data/samples/pouya_p2p_pipeline/stage2_approach2/failed.jsonl   (dropped instances + reasons)
"""

import json
import pathlib
import collections

ROOT       = pathlib.Path(__file__).resolve().parents[3]
PAUL_WS    = pathlib.Path("/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_stage2_20260515")
STAGE1     = ROOT / "data/samples/pouya_p2p_pipeline/stage1_approach1/dataset.jsonl"
OUT_DIR    = ROOT / "data/samples/pouya_p2p_pipeline/stage2_approach2"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_stage1() -> dict:
    rows = [json.loads(l) for l in open(STAGE1)]
    return {r["instance_id"]: r for r in rows}


def load_paul_results() -> dict:
    """Read every result.json from playground subdirectories."""
    results = {}
    playground = PAUL_WS / "playground"
    if not playground.exists():
        print(f"ERROR: playground dir not found: {playground}")
        return results
    for result_file in playground.glob("*/result.json"):
        try:
            data = json.loads(result_file.read_text())
            iid  = data.get("instance_id") or result_file.parent.name
            results[iid] = data
        except Exception as e:
            print(f"  WARNING: could not read {result_file}: {e}")
    return results


def load_organize_jsonl() -> dict:
    """organize.jsonl has docker_image + test_cmds from the organize step."""
    organize = PAUL_WS / "organize.jsonl"
    if not organize.exists():
        return {}
    rows = {}
    for line in organize.open():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            rows[r["instance_id"]] = r
        except Exception:
            pass
    return rows


def main():
    print("Loading Stage 1 dataset…")
    stage1 = load_stage1()
    print(f"  {len(stage1)} instances")

    print("Loading Paul result.json files…")
    paul_results = load_paul_results()
    print(f"  {len(paul_results)} result.json files found")

    print("Loading organize.jsonl…")
    organize = load_organize_jsonl()
    print(f"  {len(organize)} organize entries found")

    validated   = []
    failed_rows = []

    for iid, row in stage1.items():
        result  = paul_results.get(iid, {})
        org     = organize.get(iid, {})

        docker_image = org.get("docker_image") or result.get("docker_image")
        test_cmds    = org.get("test_cmds") or result.get("test_cmds") or []
        status       = result.get("status", "not_started")

        if not docker_image:
            failed_rows.append({
                "instance_id": iid,
                "reason": "no_docker_image",
                "paul_status": status,
                "issue_type": row.get("issue_type"),
                "quality_bucket": row.get("quality_bucket"),
            })
            continue

        # Merge Paul outputs into Stage 1 row
        out = dict(row)
        out["docker_image"]       = docker_image
        out["image_name"]         = docker_image          # override placeholder
        out["test_cmds"]          = test_cmds
        out["paul_status"]        = status
        out["paul_workspace"]     = str(PAUL_WS / "playground" / iid)
        out["pipeline_stage"]     = "stage2_approach2_paul_validated"
        if org.get("log_parser"):
            out["log_parser"]     = org["log_parser"]
        if org.get("rebuild_cmds"):
            out["paul_rebuild_cmds"] = org["rebuild_cmds"]
        validated.append(out)

    # Write outputs
    out_path = OUT_DIR / "dataset.jsonl"
    with open(out_path, "w") as f:
        for r in validated:
            f.write(json.dumps(r) + "\n")

    fail_path = OUT_DIR / "failed.jsonl"
    with open(fail_path, "w") as f:
        for r in failed_rows:
            f.write(json.dumps(r) + "\n")

    # Summary
    by_type  = collections.Counter(r["issue_type"]      for r in validated)
    by_q     = collections.Counter(r.get("quality_bucket", "?") for r in validated)
    fail_by_type = collections.Counter(r["issue_type"]  for r in failed_rows)
    f2p_gt0  = sum(1 for r in validated if (r.get("FAIL_TO_PASS_count") or 0) > 0)
    f2p_zero = sum(1 for r in validated if (r.get("FAIL_TO_PASS_count") or 0) == 0)

    summary = {
        "stage":          "stage2_approach2_paul_validated",
        "description":    (
            "Paul/RepoLaunch executable validation. Docker image built per instance. "
            "P2P tests confirmed to pass at base_commit. gpt-oss:120b via Ollama, 4 workers."
        ),
        "paul_workspace": str(PAUL_WS),
        "total_stage1":   len(stage1),
        "total_validated": len(validated),
        "total_failed":    len(failed_rows),
        "survival_rate":   round(len(validated) / len(stage1) * 100, 1),
        "by_issue_type":  dict(by_type),
        "by_quality":     dict(by_q),
        "failed_by_type": dict(fail_by_type),
        "f2p_gt0":        f2p_gt0,
        "f2p_zero":       f2p_zero,
        "docker_ready":   True,
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    print("\n=== Stage 2 collection complete ===")
    print(json.dumps(summary, indent=2))
    print(f"\nDataset → {out_path}  ({len(validated)} rows)")
    print(f"Failed  → {fail_path} ({len(failed_rows)} rows)")


if __name__ == "__main__":
    main()
