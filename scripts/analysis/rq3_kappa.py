#!/usr/bin/env python3
"""
Cohen's kappa between the two RQ3 coders, plus the pattern x outcome cross-tabulation.

Both dimensions are multi-label, so kappa is computed per code as a 2x2 present/absent
agreement rather than once over whole label sets: two coders who agree on four of five
codes should not score as a total disagreement.

Run after the second coder fills coder2_patterns and coder2_failures. Rows where either
coder's cell is blank are skipped and counted, so a partial second pass still reports
agreement on what it covers.
"""
import csv, collections, sys
from pathlib import Path

SHEET = Path("/home/22pf2/BenchmarkLLMAgent/docs/analysis/rq3/rq3_coding_sheet.csv")
A_CODES = ["A1_restructure","A2_root_cause","A3_trace","A4_code_context",
           "A5_repro_steps","A6_env","A7_none"]
B_CODES = ["B1_hallucinated","B2_overspecified","B3_signal_loss","B4_abstained","B5_none"]


def kappa(pairs):
    """Cohen's kappa for binary present/absent judgements."""
    n = len(pairs)
    if n == 0:
        return None, 0
    both = sum(1 for a, b in pairs if a and b)
    neither = sum(1 for a, b in pairs if not a and not b)
    po = (both + neither) / n
    pa = sum(1 for a, _ in pairs if a) / n
    pb = sum(1 for _, b in pairs if b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1:
        return None, n            # one code used on every row or none: kappa undefined
    return (po - pe) / (1 - pe), n


def main() -> int:
    rows = list(csv.DictReader(open(SHEET)))
    for dim, codes, c1, c2 in [("A", A_CODES, "coder1_patterns", "coder2_patterns"),
                               ("B", B_CODES, "coder1_failures", "coder2_failures")]:
        usable = [r for r in rows if r[c1].strip() and r[c2].strip()]
        print(f"\nDimension {dim}: {len(usable)} of {len(rows)} rows double-coded")
        if not usable:
            print("  second coder has not filled this dimension yet")
            continue
        ks = []
        print(f"  {'code':22s} {'k':>7} {'coder1':>7} {'coder2':>7}")
        for code in codes:
            pairs = [(code in r[c1], code in r[c2]) for r in usable]
            k, n = kappa(pairs)
            n1 = sum(1 for a, _ in pairs if a); n2 = sum(1 for _, b in pairs if b)
            print(f"  {code:22s} {('n/a' if k is None else f'{k:.3f}'):>7} {n1:7d} {n2:7d}")
            if k is not None:
                ks.append(k)
        if ks:
            print(f"  mean kappa across codes: {sum(ks)/len(ks):.3f}")

    print("\nPattern x outcome (coder 1):")
    outs = ["helped", "hurt", "unchanged"]
    print(f"  {'pattern':22s} " + " ".join(f"{o:>10}" for o in outs))
    for code in A_CODES:
        cells = [sum(1 for r in rows if code in r["coder1_patterns"] and r["outcome"] == o)
                 for o in outs]
        if sum(cells):
            print(f"  {code:22s} " + " ".join(f"{x:10d}" for x in cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
