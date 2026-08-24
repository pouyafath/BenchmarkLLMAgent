"""
Stage 1.5 — LLM-based issue type classification.

Replaces the keyword/label heuristic with gpt-oss:120b via Ollama.
Reads stage1_approach1/dataset.jsonl, classifies every issue as
bug / feature / refactoring, writes result back in-place and saves
a separate summary.

Model : gpt-oss:120b  (local Ollama, http://localhost:11434)
Workers: 4 parallel threads (matches Ollama capacity)

Resume-safe: skips rows that already have issue_type set.
Live counts: prints Bug/Feature/Refactoring tally every 20 completions.
"""

import json
import pathlib
import threading
import time
import urllib.request
import urllib.error
import concurrent.futures

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT      = pathlib.Path(__file__).resolve().parents[3]
STAGE1    = ROOT / "data/samples/pouya_dataset_2026_stage1/dataset.jsonl"
OUT_DIR   = ROOT / "data/samples/pouya_dataset_2026_stage1"

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gpt-oss:120b"
MAX_WORKERS  = 4
MAX_RETRIES  = 3
TIMEOUT_SEC  = 120

VALID_TYPES = {"bug", "feature", "refactoring"}

# ── Prompt ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a software engineering assistant that classifies GitHub issues.

Classify the given issue into EXACTLY one of these three categories:

- bug: A defect, error, crash, or unexpected behavior that needs to be fixed.
  The developer is reporting something that is broken or incorrect.

- feature: A request for new functionality, capability, or improvement that
  does not currently exist. The developer wants something added.

- refactoring: A request to restructure, clean up, simplify, or improve
  existing code quality without changing external behavior. Includes
  deprecations, code style, maintenance, and technical debt.

You MUST respond with ONLY one word: bug, feature, or refactoring.
No explanation. No punctuation. Just the single word."""

def build_prompt(row: dict) -> str:
    title  = (row.get("issue_title") or "").strip()
    labels = ", ".join(row.get("issue_labels") or [])
    body   = (row.get("problem_statement") or "").strip()[:1500]

    parts = ["Classify this GitHub issue.\n"]
    if title:
        parts.append(f"Title: {title}")
    if labels:
        parts.append(f"Labels: {labels}")
    if body:
        parts.append(f"Issue description:\n{body}")
    parts.append("\nRespond with ONLY one word: bug, feature, or refactoring.")
    return "\n".join(parts)


def call_ollama(prompt: str) -> str:
    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "stream": False,
        "options": {"temperature": 0.0, "seed": 42},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
        data = json.load(resp)
    return data.get("response", "").strip().lower()


def classify_one(row: dict) -> dict:
    prompt = build_prompt(row)
    raw    = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = call_ollama(prompt)
            break
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raw = f"error:{exc}"
            else:
                time.sleep(2 * attempt)

    for t in VALID_TYPES:
        if t in raw:
            issue_type = t
            break
    else:
        issue_type = "unknown"

    out = dict(row)
    out["issue_type"]        = issue_type
    out["issue_type_source"] = "llm_gpt_oss_120b"
    out["issue_type_raw"]    = raw
    out.pop("keyword_issue_type", None)
    return out


def main():
    rows = [json.loads(l) for l in open(STAGE1)]
    total = len(rows)

    # ── Resume: split into already-done and pending ───────────────────────────
    results   = list(rows)          # will be updated in-place as work completes
    pending   = [(i, r) for i, r in enumerate(rows) if r.get("issue_type") not in VALID_TYPES]
    already   = total - len(pending)

    # Seed live counters from already-classified rows
    live = {t: sum(1 for r in rows if r.get("issue_type") == t) for t in VALID_TYPES}
    live["unknown"] = sum(1 for r in rows if r.get("issue_type") == "unknown")
    lock = threading.Lock()
    file_lock = threading.Lock()

    print(f"Total rows:      {total}")
    print(f"Already labeled: {already}  (bug={live['bug']} feature={live['feature']} refactoring={live['refactoring']})")
    print(f"To classify:     {len(pending)}")
    print()

    if not pending:
        print("Nothing to do — all rows already classified.")
    else:
        completed = 0
        start     = time.time()

        def write_row(idx: int, row: dict) -> None:
            """Write the full dataset back after each completion (append-safe via full rewrite)."""
            with file_lock:
                results[idx] = row
                with open(STAGE1, "w") as f:
                    for r in results:
                        f.write(json.dumps(r) + "\n")

        def print_live(completed: int, total_pending: int, elapsed: float) -> None:
            rate = completed / elapsed if elapsed > 0 else 0
            eta  = (total_pending - completed) / rate if rate > 0 else 0
            with lock:
                b = live["bug"]
                fe = live["feature"]
                re_ = live["refactoring"]
                unk = live["unknown"]
                done_total = already + completed
            print(
                f"  [{done_total}/{total}]  "
                f"Bug={b}  Feature={fe}  Refactoring={re_}  Unknown={unk}  |  "
                f"{elapsed:.0f}s elapsed  ETA {eta:.0f}s"
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_to_idx = {pool.submit(classify_one, r): i for i, r in pending}
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    classified = future.result()
                except Exception as exc:
                    classified = dict(rows[idx])
                    classified["issue_type"]        = "unknown"
                    classified["issue_type_source"] = "llm_error"
                    classified["issue_type_raw"]    = str(exc)

                with lock:
                    t = classified.get("issue_type", "unknown")
                    live[t] = live.get(t, 0) + 1

                write_row(idx, classified)
                completed += 1

                if completed % 20 == 0 or completed == len(pending):
                    print_live(completed, len(pending), time.time() - start)

    # ── Final summary ─────────────────────────────────────────────────────────
    final = [json.loads(l) for l in open(STAGE1)]
    by_type = {}
    by_src  = {}
    by_q    = {}
    for r in final:
        t = r.get("issue_type", "unknown")
        s = r.get("issue_type_source", "?")
        q = r.get("quality_bucket", "?")
        by_type[t] = by_type.get(t, 0) + 1
        by_src[s]  = by_src.get(s, 0) + 1
        by_q[q]    = by_q.get(q, 0) + 1

    f2p_gt0 = sum(1 for r in final if (r.get("FAIL_TO_PASS_count") or 0) > 0)
    f2p_0   = sum(1 for r in final if (r.get("FAIL_TO_PASS_count") or 0) == 0)

    cross = {}
    for r in final:
        t      = r.get("issue_type", "unknown")
        struct = "F2P>0" if (r.get("FAIL_TO_PASS_count") or 0) > 0 else "F2P=0"
        cross.setdefault(t, {})[struct] = cross.get(t, {}).get(struct, 0) + 1

    summary = {
        "stage":       "stage1_approach1_llm_classified",
        "description": (
            f"P2P>0 static diff parse. Issue type classified by {OLLAMA_MODEL} via Ollama. "
            "F2P stored as reference only — not used as filter."
        ),
        "model":        OLLAMA_MODEL,
        "total":        len(final),
        "by_issue_type": by_type,
        "by_source":    by_src,
        "by_quality":   by_q,
        "f2p_gt0":      f2p_gt0,
        "f2p_zero":     f2p_0,
        "cross_type_x_test_structure": cross,
        "docker_ready": False,
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\n=== Classification complete ===")
    print(json.dumps(by_type, indent=2))


if __name__ == "__main__":
    main()
