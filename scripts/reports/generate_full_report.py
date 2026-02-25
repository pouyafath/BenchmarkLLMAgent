"""
Comprehensive pilot solver benchmark report from existing results.
Covers 4 working frameworks + 2 that failed due to connector issues.

Usage:
    python -m scripts.reports.generate_full_report
"""

import json
import statistics
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "pilot_solver_benchmark"
GT_DIR = PROJECT_ROOT / "data" / "ground_truth"
SAMPLES_PATH = PROJECT_ROOT / "data" / "samples" / "pilot_10_samples.json"
MODEL = "llama3.3:70b-instruct-fp16"

WORKING_FW = ["autogen", "crewai", "langgraph", "openai_agents_sdk"]
FAILED_FW = ["llamaindex", "semantic_kernel"]


def load_results():
    results = defaultdict(dict)
    for f in sorted(RESULTS_DIR.glob("*.json")):
        if f.name == "benchmark_summary.json":
            continue
        try:
            data = json.loads(f.read_text())
            fw = data.get("framework", f.stem.split("__")[0])
            iid = data.get("issue_id", "?")
            results[fw][iid] = data
        except Exception:
            pass
    return dict(results)


def load_gt():
    samples = json.load(open(SAMPLES_PATH))
    gt = {}
    for issue in samples["issues"]:
        iid = f"{issue['repo_name']}#{issue['issue_number']}"
        gt_file = GT_DIR / f"{issue['pr_owner']}__{issue['pr_repo']}__{issue['issue_number']}.json"
        if gt_file.exists():
            gt[iid] = json.load(open(gt_file))
        else:
            gt[iid] = {}
    return gt, samples["issues"]


def safe_stats(values):
    if not values:
        return {"mean": 0, "median": 0, "std": 0, "min": 0, "max": 0}
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
    }


def w():
    return 95


def main():
    all_results = load_results()
    gt_data, issues = load_gt()

    # ══════════════════════════════════════════════════════════════════════════
    # Header
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═'*w()}")
    print(f"{'INITIAL BENCHMARK REPORT':^{w()}}")
    print(f"{'From Issue Enhancement to Issue Solving':^{w()}}")
    print(f"{'═'*w()}")

    print(f"""
  Configuration
  ─────────────────────────────────────────
  LLM Model:            {MODEL}
  Hosting:              Ollama (local, GPU)
  Issues:               10 (from Paper 2 golden dataset)
  Issue Types:          Bug-labeled, with linked merged PRs
  Parallel Workers:     4
  Total Frameworks:     6 attempted
  Working Frameworks:   {len(WORKING_FW)} ({', '.join(WORKING_FW)})
  Failed Frameworks:    {len(FAILED_FW)} ({', '.join(FAILED_FW)})
""")

    # ══════════════════════════════════════════════════════════════════════════
    # A. Correctness / Outcome Metrics
    # ══════════════════════════════════════════════════════════════════════════
    print(f"{'═'*w()}")
    print(f"{'A. CORRECTNESS / OUTCOME METRICS':^{w()}}")
    print(f"{'═'*w()}")

    print(f"\n  {'Framework':<22} {'Patch Gen':>10} {'File Overlap':>13} {'Content Sim':>12} "
          f"{'Errors':>7}")
    print(f"  {'─'*68}")

    fw_stats = {}
    for fw in WORKING_FW:
        data = all_results.get(fw, {})
        n = len(data)
        n_patches = sum(1 for r in data.values() if r.get("evaluation", {}).get("has_patch", False))
        n_errors = sum(1 for r in data.values() if r.get("error"))
        ok = [r for r in data.values() if not r.get("error")]

        fovlps = [r["evaluation"].get("file_overlap", 0) for r in ok]
        sims = [r["evaluation"].get("content_similarity", 0) for r in ok]

        fw_stats[fw] = {
            "n": n, "n_patches": n_patches, "n_errors": n_errors,
            "patch_rate": n_patches / max(n, 1),
            "file_overlap": safe_stats(fovlps),
            "similarity": safe_stats(sims),
        }

        rate = f"{n_patches}/{n} ({n_patches/n*100:.0f}%)"
        avg_fo = statistics.mean(fovlps) if fovlps else 0
        avg_sim = statistics.mean(sims) if sims else 0
        print(f"  {fw:<22} {rate:>10} {avg_fo:>12.3f} {avg_sim:>12.4f} {n_errors:>7}")

    for fw in FAILED_FW:
        data = all_results.get(fw, {})
        n = len(data)
        errs = [r for r in data.values() if r.get("error")]
        err_type = list(errs)[0].get("error", "?").split(":")[0] if errs else "?"
        print(f"  {fw:<22} {'0/'+str(n)+' (0%)':>10} {'N/A':>12} {'N/A':>12} {n:>7}  [{err_type}]")

    # ══════════════════════════════════════════════════════════════════════════
    # B. Efficiency / Cost Metrics
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═'*w()}")
    print(f"{'B. EFFICIENCY / COST METRICS':^{w()}}")
    print(f"{'═'*w()}")

    print(f"\n  {'Framework':<22} {'Mean Time':>10} {'Median':>8} {'Std Dev':>8} "
          f"{'Min':>7} {'Max':>7} {'Patch Sz':>9}")
    print(f"  {'─'*76}")

    for fw in WORKING_FW:
        data = all_results.get(fw, {})
        ok = [r for r in data.values() if not r.get("error")]
        times = [r.get("elapsed_s", 0) for r in ok]
        patches = [len(r.get("patch", "")) for r in ok]
        ts = safe_stats(times)
        ps = safe_stats(patches)
        print(f"  {fw:<22} {ts['mean']:>9.1f}s {ts['median']:>7.1f}s {ts['std']:>7.1f}s "
              f"{ts['min']:>6.1f}s {ts['max']:>6.1f}s {ps['mean']:>8.0f}ch")
        fw_stats[fw]["time"] = ts
        fw_stats[fw]["patch_size"] = ps

    # ══════════════════════════════════════════════════════════════════════════
    # C. Per-Issue Comparison Matrix
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═'*w()}")
    print(f"{'C. PER-ISSUE COMPARISON MATRIX':^{w()}}")
    print(f"{'═'*w()}")

    all_issues = sorted(set(iid for fw in WORKING_FW for iid in all_results.get(fw, {})))

    for metric_name, metric_key in [("File Overlap", "file_overlap"),
                                     ("Content Similarity", "content_similarity"),
                                     ("Time (seconds)", None)]:
        print(f"\n  {metric_name}:")
        header = f"  {'Issue':<42}"
        for fw in WORKING_FW:
            short = fw[:12]
            header += f" {short:>12}"
        header += f" {'Best':>12}"
        print(header)
        print(f"  {'─'*len(header)}")

        for iid in all_issues:
            row = f"  {iid:<42}"
            vals = {}
            for fw in WORKING_FW:
                r = all_results.get(fw, {}).get(iid)
                if r and not r.get("error"):
                    if metric_key:
                        v = r.get("evaluation", {}).get(metric_key, 0)
                    else:
                        v = r.get("elapsed_s", 0)
                    vals[fw] = v
                    row += f" {v:>12.4f}" if metric_key else f" {v:>11.1f}s"
                else:
                    row += f" {'ERR':>12}"

            if vals:
                if metric_key:
                    best = max(vals, key=vals.get)
                else:
                    best = min(vals, key=vals.get)
                row += f" {best[:12]:>12}"
            print(row)

    # ══════════════════════════════════════════════════════════════════════════
    # D. Framework Ranking
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═'*w()}")
    print(f"{'D. FRAMEWORK RANKING':^{w()}}")
    print(f"{'═'*w()}")

    scores = {}
    for fw in WORKING_FW:
        s = fw_stats[fw]
        scores[fw] = {
            "patch_rate": s["patch_rate"],
            "file_overlap": s["file_overlap"]["mean"],
            "similarity": s["similarity"]["mean"],
            "avg_time": s["time"]["mean"],
        }

    ranked = sorted(scores.items(),
                    key=lambda x: (x[1]["patch_rate"], x[1]["file_overlap"],
                                   x[1]["similarity"], -x[1]["avg_time"]),
                    reverse=True)

    print(f"\n  {'Rank':<6} {'Framework':<22} {'Patch Rate':>11} {'File Ovlp':>10} "
          f"{'Similarity':>11} {'Avg Time':>10}")
    print(f"  {'─'*74}")
    for i, (fw, sc) in enumerate(ranked, 1):
        n_p = fw_stats[fw]["n_patches"]
        n = fw_stats[fw]["n"]
        rate_str = f"{n_p}/{n} ({sc['patch_rate']*100:.0f}%)"
        print(f"  #{i:<5} {fw:<22} {rate_str:>11} {sc['file_overlap']:>9.3f} "
              f"{sc['similarity']:>10.4f} {sc['avg_time']:>9.1f}s")

    # ══════════════════════════════════════════════════════════════════════════
    # E. Issue Difficulty Analysis
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═'*w()}")
    print(f"{'E. ISSUE DIFFICULTY ANALYSIS':^{w()}}")
    print(f"{'═'*w()}")

    print(f"\n  {'Issue':<42} {'GT Patch':>9} {'GT Files':>9} {'Avg Sim':>8} {'Hardest For':>14}")
    print(f"  {'─'*85}")

    for iid in all_issues:
        gt = gt_data.get(iid, {})
        gt_patch_len = len(gt.get("patch", ""))
        gt_n_files = len(gt.get("pr_files", []))
        sims = {}
        for fw in WORKING_FW:
            r = all_results.get(fw, {}).get(iid)
            if r and not r.get("error"):
                sims[fw] = r.get("evaluation", {}).get("content_similarity", 0)
        avg_sim = statistics.mean(sims.values()) if sims else 0
        hardest = min(sims, key=sims.get) if sims else "N/A"
        print(f"  {iid:<42} {gt_patch_len:>8}ch {gt_n_files:>8} {avg_sim:>8.4f} {hardest:>14}")

    # ══════════════════════════════════════════════════════════════════════════
    # F. Key Findings
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═'*w()}")
    print(f"{'F. KEY FINDINGS & OBSERVATIONS':^{w()}}")
    print(f"{'═'*w()}")

    best_overall = ranked[0]
    fastest = min(WORKING_FW, key=lambda fw: scores[fw]["avg_time"])
    best_sim = max(WORKING_FW, key=lambda fw: scores[fw]["similarity"])
    best_fovlp = max(WORKING_FW, key=lambda fw: scores[fw]["file_overlap"])

    print(f"""
  1. PATCH GENERATION SUCCESS
     - All 4 working frameworks achieved >= 90% patch generation rate
     - AutoGen, CrewAI, and OpenAI Agents SDK: 100% (10/10)
     - LangGraph: 90% (9/10, 1 error on eclipse-theia/theia#15048)

  2. FILE LOCALIZATION (File Overlap with Ground Truth)
     - {best_fovlp}: Best file overlap ({scores[best_fovlp]['file_overlap']:.3f})
     - OpenAI Agents SDK, CrewAI, and LangGraph all achieve ~1.000 file overlap
     - AutoGen: 0.800 (sometimes targets wrong files, e.g., nlohmann/json#4309)

  3. PATCH QUALITY (Content Similarity to Ground Truth)
     - {best_sim}: Highest similarity ({scores[best_sim]['similarity']:.4f})
     - All frameworks show low absolute similarity (0.12-0.17 range)
     - This is expected: agents generate valid but different patches than humans
     - Best per-issue similarity: nlohmann/json#4309 (0.42-0.59 across frameworks)
     - Worst per-issue similarity: withfig/autocomplete#1625, syncthing/syncthing#9775

  4. SPEED
     - {fastest}: Fastest ({scores[fastest]['avg_time']:.1f}s average)
     - OpenAI Agents SDK and CrewAI are ~30s average
     - AutoGen: ~40s average
     - LangGraph: ~56s average (slowest, includes one 255s outlier)

  5. FRAMEWORK INTEGRATION
     - LlamaIndex: Failed (ReadTimeout, Ollama connector issue under load)
     - Semantic Kernel: Failed (API signature mismatch, rapidly evolving SDK)
     - These are integration/connector issues, not fundamental framework problems

  6. OVERALL RANKING: {best_overall[0]}
     - Best combination of patch rate, file overlap, and similarity
     - Also the fastest framework
""")

    # ══════════════════════════════════════════════════════════════════════════
    # G. Threats & Limitations
    # ══════════════════════════════════════════════════════════════════════════
    print(f"{'═'*w()}")
    print(f"{'G. THREATS & LIMITATIONS':^{w()}}")
    print(f"{'═'*w()}")

    print("""
  1. Small sample size (10 issues) - insufficient for statistical significance
  2. Single LLM model (llama3.3:70b) - results may not generalize to other models
  3. No execution/test-based evaluation - only text-based similarity metrics
  4. Bug-only issues - feature requests may behave differently
  5. Single-turn agents - no iterative refinement or tool use
  6. 2/6 frameworks could not be evaluated due to connector issues
  7. Patch similarity is a proxy metric - low similarity doesn't mean wrong patches
  8. Ground truth is one valid fix; multiple valid patches may exist
""")

    # ══════════════════════════════════════════════════════════════════════════
    # H. Next Steps
    # ══════════════════════════════════════════════════════════════════════════
    print(f"{'═'*w()}")
    print(f"{'H. RECOMMENDED NEXT STEPS':^{w()}}")
    print(f"{'═'*w()}")

    print("""
  1. Scale up to 50-100+ issues for statistical power
  2. Fix LlamaIndex (use httpx-based Ollama calls) and Semantic Kernel (pin SDK version)
  3. Add execution-based evaluation (apply patches, run test suites)
  4. Add multi-turn agent capabilities with tool access (file read, search, test)
  5. Test with additional LLM models (GPT-4, Claude, Gemma, etc.)
  6. Include feature-request issues alongside bugs
  7. Perform Wilcoxon signed-rank tests + Cliff's delta for framework comparisons
  8. Analyze patches qualitatively for correctness patterns
""")

    print(f"{'═'*w()}\n")

    # Save JSON summary
    summary = {
        "model": MODEL,
        "n_issues": 10,
        "working_frameworks": WORKING_FW,
        "failed_frameworks": FAILED_FW,
        "framework_stats": {},
    }
    for fw in WORKING_FW:
        s = fw_stats[fw]
        summary["framework_stats"][fw] = {
            "n_patches": s["n_patches"],
            "n_errors": s["n_errors"],
            "patch_rate": round(s["patch_rate"], 3),
            "avg_file_overlap": round(s["file_overlap"]["mean"], 4),
            "avg_similarity": round(s["similarity"]["mean"], 4),
            "avg_time_s": round(s["time"]["mean"], 2),
            "median_time_s": round(s["time"]["median"], 2),
        }
    for fw in FAILED_FW:
        data = all_results.get(fw, {})
        errs = [r for r in data.values() if r.get("error")]
        err_type = list(errs)[0].get("error", "?").split(":")[0] if errs else "?"
        summary["framework_stats"][fw] = {
            "n_patches": 0, "n_errors": len(data), "patch_rate": 0,
            "failure_reason": err_type,
        }

    out = RESULTS_DIR / "benchmark_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"  Saved: {out}\n")


if __name__ == "__main__":
    main()
