"""
Generate pilot solver benchmark report from existing result files.
Reads all individual JSON results and produces summary + detailed report.

Usage:
    python -m scripts.reports.generate_pilot_report
"""

import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "pilot_solver_benchmark"
OLLAMA_MODEL = "llama3.3:70b-instruct-fp16"


def load_all_results():
    results = defaultdict(list)
    for f in sorted(RESULTS_DIR.glob("*.json")):
        if f.name == "benchmark_summary.json":
            continue
        try:
            data = json.loads(f.read_text())
            fw = data.get("framework", f.stem.split("__")[0])
            results[fw].append(data)
        except Exception as e:
            print(f"  WARN: Could not read {f.name}: {e}")
    return dict(results)


def main():
    all_results = load_all_results()

    print(f"\n{'='*95}")
    print(f"{'BENCHMARK RESULTS: LLM Agent Frameworks for GitHub Issue Solving':^95}")
    print(f"{'='*95}")
    print(f"\n  Model:      {OLLAMA_MODEL}")
    print(f"  Issues:     10 (from Paper 2 golden dataset, bug-labeled, with merged PRs)")
    print(f"  Frameworks: {len(all_results)}")
    print(f"  Total runs: {sum(len(v) for v in all_results.values())}")

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'─'*95}")
    print(f"{'FRAMEWORK COMPARISON':^95}")
    print(f"{'─'*95}")
    print(f"\n  {'Framework':<22} {'Patch Rate':>11} {'Avg Time':>10} {'File Overlap':>13} "
          f"{'Patch Sim':>10} {'Errors':>7}")
    print(f"  {'-'*80}")

    summary = {}
    for fw_name in ["autogen", "crewai", "langgraph", "llamaindex", "openai_agents_sdk", "semantic_kernel"]:
        results = all_results.get(fw_name, [])
        n = len(results)
        if n == 0:
            print(f"  {fw_name:<22} {'N/A':>11}")
            continue

        n_patches = sum(1 for r in results if r.get("evaluation", {}).get("has_patch", False))
        n_errors = sum(1 for r in results if r.get("error"))
        n_success = n - n_errors

        times = [r.get("elapsed_s", 0) for r in results if not r.get("error")]
        avg_time = sum(times) / len(times) if times else 0

        file_ovlps = [r.get("evaluation", {}).get("file_overlap", 0) for r in results if not r.get("error")]
        avg_file_ovlp = sum(file_ovlps) / len(file_ovlps) if file_ovlps else 0

        sims = [r.get("evaluation", {}).get("content_similarity", 0) for r in results if not r.get("error")]
        avg_sim = sum(sims) / len(sims) if sims else 0

        summary[fw_name] = {
            "n_issues": n,
            "n_patches": n_patches,
            "n_errors": n_errors,
            "patch_rate": round(n_patches / n, 3),
            "avg_time_s": round(avg_time, 2),
            "avg_file_overlap": round(avg_file_ovlp, 4),
            "avg_similarity": round(avg_sim, 4),
        }

        rate_str = f"{n_patches}/{n} ({n_patches/n*100:.0f}%)"
        time_str = f"{avg_time:.1f}s" if times else "N/A"
        print(f"  {fw_name:<22} {rate_str:>11} {time_str:>10} {avg_file_ovlp:>12.3f} "
              f"{avg_sim:>10.4f} {n_errors:>7}")

    # ── Per-issue breakdown ───────────────────────────────────────────────────
    print(f"\n{'─'*95}")
    print(f"{'PER-ISSUE DETAIL':^95}")
    print(f"{'─'*95}")

    issues_seen = set()
    for results in all_results.values():
        for r in results:
            issues_seen.add(r.get("issue_id", "?"))

    for issue_id in sorted(issues_seen):
        print(f"\n  Issue: {issue_id}")
        print(f"  {'Framework':<22} {'Time':>8} {'Patch':>7} {'FileOv':>7} {'Sim':>8} {'Status':>10}")
        print(f"  {'-'*65}")
        for fw_name in ["autogen", "crewai", "langgraph", "llamaindex", "openai_agents_sdk", "semantic_kernel"]:
            results = all_results.get(fw_name, [])
            matches = [r for r in results if r.get("issue_id") == issue_id]
            if not matches:
                print(f"  {fw_name:<22} {'':>8} {'':>7} {'':>7} {'':>8} {'missing':>10}")
                continue
            r = matches[0]
            ev = r.get("evaluation", {})
            err = r.get("error")
            if err:
                err_short = err.split(":")[0] if ":" in err else err[:20]
                print(f"  {fw_name:<22} {'':>8} {'':>7} {'':>7} {'':>8} {'ERR:'+err_short:>10}")
            else:
                has_p = "Yes" if ev.get("has_patch") else "No"
                print(f"  {fw_name:<22} {r.get('elapsed_s',0):>7.1f}s {has_p:>7} "
                      f"{ev.get('file_overlap',0):>6.2f} {ev.get('content_similarity',0):>7.4f} {'OK':>10}")

    # ── Framework ranking ─────────────────────────────────────────────────────
    print(f"\n{'─'*95}")
    print(f"{'FRAMEWORK RANKING':^95}")
    print(f"{'─'*95}")

    ranked = sorted(
        [(k, v) for k, v in summary.items()],
        key=lambda x: (x[1]["patch_rate"], x[1]["avg_file_overlap"], x[1]["avg_similarity"]),
        reverse=True,
    )

    print(f"\n  {'Rank':<6} {'Framework':<22} {'Patch Rate':>11} {'File Ovlp':>10} {'Similarity':>11} {'Avg Time':>10}")
    print(f"  {'-'*75}")
    for i, (fw, s) in enumerate(ranked, 1):
        rate_str = f"{s['n_patches']}/{s['n_issues']} ({s['patch_rate']*100:.0f}%)"
        print(f"  #{i:<5} {fw:<22} {rate_str:>11} {s['avg_file_overlap']:>9.3f} "
              f"{s['avg_similarity']:>10.4f} {s['avg_time_s']:>9.1f}s")

    # ── Key findings ──────────────────────────────────────────────────────────
    print(f"\n{'─'*95}")
    print(f"{'KEY FINDINGS':^95}")
    print(f"{'─'*95}")

    working = {k: v for k, v in summary.items() if v["n_errors"] < v["n_issues"]}
    failed = {k: v for k, v in summary.items() if v["n_errors"] == v["n_issues"]}

    print(f"\n  Working frameworks ({len(working)}/6):")
    for fw in sorted(working):
        s = working[fw]
        print(f"    - {fw}: {s['patch_rate']*100:.0f}% patch rate, "
              f"{s['avg_file_overlap']:.3f} file overlap, {s['avg_similarity']:.4f} similarity")

    if failed:
        print(f"\n  Failed frameworks ({len(failed)}/6):")
        for fw in sorted(failed):
            errs = [r.get("error","?") for r in all_results.get(fw,[]) if r.get("error")]
            err_type = errs[0].split(":")[0] if errs else "unknown"
            print(f"    - {fw}: {err_type}")

    if working:
        best_fw = max(working, key=lambda k: (working[k]["patch_rate"], working[k]["avg_file_overlap"]))
        fastest_fw = min(working, key=lambda k: working[k]["avg_time_s"] if working[k]["avg_time_s"] > 0 else 9999)
        best_sim = max(working, key=lambda k: working[k]["avg_similarity"])

        print(f"\n  Best overall:     {best_fw} "
              f"({working[best_fw]['patch_rate']*100:.0f}% patches, "
              f"{working[best_fw]['avg_file_overlap']:.3f} file overlap)")
        print(f"  Fastest:          {fastest_fw} ({working[fastest_fw]['avg_time_s']:.1f}s avg)")
        print(f"  Best similarity:  {best_sim} ({working[best_sim]['avg_similarity']:.4f})")

    print(f"\n{'='*95}")

    # Save summary
    out = RESULTS_DIR / "benchmark_summary.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
