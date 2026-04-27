#!/usr/bin/env python3
"""Create a second-paper 10-issue P2P-only dataset variant.

This transforms the existing second-paper final 10 dataset by setting
FAIL_TO_PASS to [] for all rows while preserving PASS_TO_PASS lists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _detect_repo_root() -> Path:
    script_path = Path(__file__).resolve()
    direct_root = script_path.parent.parent.parent
    if (direct_root / "scripts").exists() and (direct_root / "src").exists():
        return direct_root
    parent_root = direct_root.parent
    if (parent_root / "scripts").exists() and (parent_root / "src").exists():
        return parent_root
    raise RuntimeError(f"Could not detect repository root from {script_path}.")


ROOT = _detect_repo_root()
IN_DIR = ROOT / "data" / "samples" / "second_paper_final_10_f2p_p2p"
OUT_DIR = ROOT / "data" / "samples" / "second_paper_final_10_p2p_only"

IN_DATASET = IN_DIR / "final_10_instances_with_f2p_p2p.jsonl"
IN_SAMPLES = IN_DIR / "secondpaper10_samples.json"
IN_IDS = IN_DIR / "secondpaper10_instance_ids.txt"

OUT_DATASET = OUT_DIR / "final_10_instances_p2p_only.jsonl"
OUT_SAMPLES = OUT_DIR / "secondpaper10_p2p_only_samples.json"
OUT_IDS = OUT_DIR / "secondpaper10_p2p_only_instance_ids.txt"
OUT_NOTES = OUT_DIR / "TRANSFORMATION_NOTES.md"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dataset-jsonl", type=Path, default=IN_DATASET)
    parser.add_argument("--input-samples-json", type=Path, default=IN_SAMPLES)
    parser.add_argument("--input-ids", type=Path, default=IN_IDS)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    rows = _load_jsonl(args.input_dataset_jsonl)
    samples_payload = json.loads(args.input_samples_json.read_text())
    ids = [line.strip() for line in args.input_ids.read_text().splitlines() if line.strip()]

    transformed_rows = []
    for row in rows:
        updated = dict(row)
        updated["FAIL_TO_PASS"] = []
        transformed_rows.append(updated)

    transformed_issues = []
    for issue in samples_payload.get("issues", []):
        updated = dict(issue)
        updated["FAIL_TO_PASS"] = []
        transformed_issues.append(updated)

    transformed_samples = {
        "metadata": {
            **samples_payload.get("metadata", {}),
            "description": "Second-paper 10-issue P2P-only variant (FAIL_TO_PASS cleared)",
            "source_dataset": str(args.input_dataset_jsonl),
            "transformation": "FAIL_TO_PASS set to [] for all issues; PASS_TO_PASS unchanged",
        },
        "issues": transformed_issues,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / OUT_DATASET.name, transformed_rows)
    (args.output_dir / OUT_SAMPLES.name).write_text(json.dumps(transformed_samples, indent=2))
    (args.output_dir / OUT_IDS.name).write_text("\n".join(ids) + "\n")

    note_lines = [
        "# P2P-Only Transformation Notes",
        "",
        "- Source dataset: `second_paper_final_10_f2p_p2p/final_10_instances_with_f2p_p2p.jsonl`",
        "- New dataset: `second_paper_final_10_p2p_only/final_10_instances_p2p_only.jsonl`",
        "- Transformation: set `FAIL_TO_PASS=[]` for all 10 issues.",
        "- `PASS_TO_PASS` lists are preserved from source dataset.",
        "- Instance order is unchanged.",
        "",
        "## Instance IDs",
        "",
    ]
    note_lines.extend([f"- `{iid}`" for iid in ids])
    (args.output_dir / OUT_NOTES.name).write_text("\n".join(note_lines) + "\n")

    print(f"Wrote dataset: {args.output_dir / OUT_DATASET.name}")
    print(f"Wrote samples: {args.output_dir / OUT_SAMPLES.name}")
    print(f"Wrote IDs: {args.output_dir / OUT_IDS.name}")
    print(f"Wrote notes: {args.output_dir / OUT_NOTES.name}")


if __name__ == "__main__":
    main()

