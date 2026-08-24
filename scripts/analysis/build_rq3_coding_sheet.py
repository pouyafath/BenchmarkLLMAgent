#!/usr/bin/env python3
"""
RQ3 ("How Are Issue Reports Enhanced?") — build the stratified sample and coding sheet.

The paper's RQ3 protocol calls for open-coding a stratified sample of agent-generated
enhancements, sampling successes, harms and no-change cases, coded independently by two
coders with Cohen's kappa and a pattern x outcome cross-tabulation.

This script produces the machine-preparable half of that:
  1. per-instance outcome labels (helped / hurt / unchanged) for each enhancer, from the
     merged stage6 correctness matrices, holding the solver fixed at OpenHands;
  2. a stratified sample balanced across enhancer x outcome;
  3. a first-pass automated feature extraction over the original -> enhanced text pair,
     to *seed* human coding (it is a prior, never a substitute for the coders);
  4. a CSV coding sheet with blank columns for two independent coders, plus a codebook.

Human open-coding of the sampled items remains to be done by two people.

Usage:
  bench_env/bin/python scripts/analysis/build_rq3_coding_sheet.py --per-cell 10
"""
from __future__ import annotations
import argparse, csv, glob, json, pathlib, random, re, collections

ROOT = pathlib.Path("/home/22pf2/BenchmarkLLMAgent")
ORIGINALS = ROOT/"data/matrix_sample382_node01.jsonl"
SCORE_DIRS = ["runs/stage6_new182_scores", "runs/stage6_new100_scores",
              "runs/stage6_100_scores", "runs/stage6_new100_scores_sa"]
ENHANCERS = ["aider", "openhands", "swe_agent"]
SOLVER = "openhands"          # held fixed: the paper's primary, most responsive solver
OUTCOMES = ["helped", "hurt", "unchanged"]

SECTION_RE = re.compile(
    r'^\s{0,3}(?:#{1,4}\s*|\*\*)\s*(summary|problem|description|reproduction|steps to reproduce|'
    r'expected(?: behaviou?r)?|actual(?: behaviou?r)?|environment|root cause|proposed fix|'
    r'analysis|context)\b', re.I | re.M)
CODEFENCE_RE  = re.compile(r'```')
TRACEBACK_RE  = re.compile(r'Traceback \(most recent call last\)|^\s*File ".*", line \d+', re.M)
HYPOTHESIS_RE = re.compile(r'\b(likely|probabl[ey]|appears to|seems to|root cause|caused by|'
                           r'suggests?|hypothes|presumabl[ey]|I suspect|the issue stems)\b', re.I)
STEPS_RE      = re.compile(r'^\s*(?:\d+[.)]\s+|[-*]\s+)', re.M)


def load_outcomes() -> dict:
    """merged stage6 matrices -> {state: {solver: {iid: bool}}}"""
    merged: dict = collections.defaultdict(dict)
    for d in SCORE_DIRS:
        p = ROOT/d/"stage6_combined_matrix.json"
        if not p.exists(): continue
        for st, svs in json.load(open(p))["matrix"].items():
            for sv, per in svs.items():
                merged[st].setdefault(sv, {}).update(per)
    return merged


def outcome_label(base: bool, enh: bool) -> str:
    if not base and enh: return "helped"
    if base and not enh: return "hurt"
    return "unchanged"


def load_enhanced() -> dict:
    """{enhancer: {iid: enhanced_problem_statement}}"""
    out: dict = {e: {} for e in ENHANCERS}
    for f in glob.glob(str(ROOT/"runs/matrix*/qwen3_32b/stage4/*/*.jsonl")):
        enh = pathlib.Path(f).parent.name
        if enh not in out: continue
        for line in open(f):
            line = line.strip()
            if not line: continue
            try: d = json.loads(line)
            except Exception: continue
            iid, ps = d.get("instance_id"), d.get("problem_statement")
            if iid and ps: out[enh][iid] = ps
    return out


def load_originals() -> dict:
    orig = {}
    with open(ORIGINALS) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: d = json.loads(line)
            except Exception: continue
            if d.get("instance_id"): orig[d["instance_id"]] = d.get("problem_statement", "")
    return orig


def features(original: str, enhanced: str) -> dict:
    """First-pass automated cues. A prior for the coders, not a verdict."""
    o, e = original or "", enhanced or ""
    def sec(t): return {m.group(1).lower() for m in SECTION_RE.finditer(t)}
    so, se = sec(o), sec(e)
    return {
        "len_ratio":         round(len(e)/max(len(o), 1), 2),
        "sections_added":    "|".join(sorted(se - so)) or "-",
        "code_blocks_added": max(0, len(CODEFENCE_RE.findall(e))//2 - len(CODEFENCE_RE.findall(o))//2),
        "traceback_added":   int(bool(TRACEBACK_RE.search(e)) and not bool(TRACEBACK_RE.search(o))),
        "hypothesis_added":  int(bool(HYPOTHESIS_RE.search(e)) and not bool(HYPOTHESIS_RE.search(o))),
        "steps_added":       max(0, len(STEPS_RE.findall(e)) - len(STEPS_RE.findall(o))),
        "original_retained": int(bool(o.strip()) and o.strip()[:120] in e),
        "text_identical":    int(o.strip() == e.strip()),
    }


CODEBOOK = """# RQ3 Codebook — open-coding agent-generated issue enhancements

Two coders label each row **independently**, then reconcile. Report Cohen's kappa per
dimension and a pattern x outcome cross-tabulation.

## Dimension A — enhancement patterns (all that apply)
- `A1_restructure`   Reorganised into Problem / Reproduction / Expected / Actual sections
- `A2_root_cause`    Appended a root-cause hypothesis or diagnosis
- `A3_trace`         Extracted or surfaced a stack trace / error output
- `A4_code_context`  Added code context (file paths, symbols, snippets)
- `A5_repro_steps`   Added or reformatted reproduction steps
- `A6_env`           Added environment / version information
- `A7_none`          No substantive change

## Dimension B — failure modes (all that apply)
- `B1_hallucinated`  States specifics not derivable from the original or repo
- `B2_overspecified` Commits to one narrow reading, foreclosing others
- `B3_signal_loss`   Drops or buries information present in the original
- `B4_abstained`     Returned the original essentially unchanged
- `B5_none`          No failure mode observed

## Outcome (pre-filled, do not edit)
`helped` = unresolved at baseline, resolved after enhancement;
`hurt` = resolved at baseline, unresolved after; `unchanged` = same either way.
Solver held fixed at OpenHands; model held fixed at Qwen3-32B.

## Note on the auto_* columns
Regex-derived cues to speed reading. They are a prior, not ground truth — code what the
text actually shows and overrule them freely.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cell", type=int, default=10, help="items per enhancer x outcome cell")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="docs/analysis/rq3")
    a = ap.parse_args()
    random.seed(a.seed)

    outcomes, enhanced, originals = load_outcomes(), load_enhanced(), load_originals()
    outdir = ROOT/a.out; outdir.mkdir(parents=True, exist_ok=True)

    pool = collections.defaultdict(list)          # (enhancer, outcome) -> [iid]
    for enh in ENHANCERS:
        base = outcomes.get("baseline", {}).get(SOLVER, {})
        cond = outcomes.get(f"enh:{enh}", {}).get(SOLVER, {})
        for iid in set(base) & set(cond):
            if iid in enhanced[enh] and iid in originals:
                pool[(enh, outcome_label(base[iid], cond[iid]))].append(iid)

    print(f"Population (solver={SOLVER}, model=Qwen3-32B):")
    for enh in ENHANCERS:
        row = "  ".join(f"{o}={len(pool[(enh,o)]):>4}" for o in OUTCOMES)
        print(f"  enh:{enh:<10} {row}")

    rows, short = [], []
    for enh in ENHANCERS:
        for out in OUTCOMES:
            cand = sorted(pool[(enh, out)])
            take = min(a.per_cell, len(cand))
            if take < a.per_cell: short.append(f"enh:{enh}/{out} ({len(cand)})")
            for iid in random.sample(cand, take):
                o, e = originals[iid], enhanced[enh][iid]
                r = {"instance_id": iid, "repo": iid.rsplit("-", 1)[0].replace("__", "/"),
                     "enhancer": enh, "solver": SOLVER, "outcome": out,
                     "original_text": o, "enhanced_text": e}
                r.update({f"auto_{k}": v for k, v in features(o, e).items()})
                for c in ("coder1_patterns", "coder1_failures", "coder2_patterns",
                          "coder2_failures", "notes"):
                    r[c] = ""
                rows.append(r)

    random.shuffle(rows)          # present blind: coders should not see cells grouped
    csv_path = outdir/"rq3_coding_sheet.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    (outdir/"CODEBOOK.md").write_text(CODEBOOK)

    print(f"\nSampled {len(rows)} items ({a.per_cell}/cell, seed={a.seed})")
    if short: print(f"  under-filled cells: {', '.join(short)}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {outdir/'CODEBOOK.md'}")

    print("\nFirst-pass automated signal (population-level, informative for the paper):")
    for enh in ENHANCERS:
        ids = [i for o in OUTCOMES for i in pool[(enh, o)]]
        if not ids: continue
        fs = [features(originals[i], enhanced[enh][i]) for i in ids]
        n = len(fs)
        print(f"  enh:{enh:<10} n={n:<4} "
              f"len_ratio_med={sorted(f['len_ratio'] for f in fs)[n//2]:<6} "
              f"restructured={100*sum(1 for f in fs if f['sections_added']!='-')/n:>5.1f}%  "
              f"hypothesis={100*sum(f['hypothesis_added'] for f in fs)/n:>5.1f}%  "
              f"identical={100*sum(f['text_identical'] for f in fs)/n:>5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
