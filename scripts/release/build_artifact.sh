#!/usr/bin/env bash
# Assemble the replication package the paper promises.
#
# Two things cannot live in git and so are collected here instead: the three 279-instance
# datasets (42MB, matched by data/*.jsonl in .gitignore) and the stored solver patches,
# without which none of the scoring is reproducible. Everything else is already tracked and
# is copied so the archive stands alone.
set -euo pipefail
ROOT=/home/22pf2/BenchmarkLLMAgent
OUT="${1:-$ROOT/dist}"
STAMP=$(date +%Y%m%d)
PKG="$OUT/benchmarkllmagent_artifact_$STAMP"

mkdir -p "$PKG"/{data,scripts,docs,predictions}

echo "[1/5] datasets and labels"
cp "$ROOT"/data/stage6_all279_v1.jsonl "$PKG/data/"
cp "$ROOT"/data/stage6_all279_v2.jsonl "$PKG/data/"
cp "$ROOT"/data/stage6_all279_v3.jsonl "$PKG/data/"
cp "$ROOT"/data/stage6_all279_methods.json "$PKG/data/"
cp "$ROOT"/data/stage6_all279_f2p_derived.json "$PKG/data/"
cp "$ROOT"/data/stage6_f2p_evaluable_85.json "$PKG/data/"

echo "[2/5] scored results"
cp "$ROOT"/data/stage6_strict_all_conditions.json "$PKG/data/"
cp "$ROOT"/data/stage6_strict_matrix_279.json "$PKG/data/"
cp "$ROOT"/data/stage6_run4_appendonly_cells.json "$PKG/data/"
cp "$ROOT"/data/stage6_replication80_result.json "$PKG/data/"
cp "$ROOT"/data/stage6_replication80_ids.json "$PKG/data/"
cp "$ROOT"/data/stage6_rerun_cells_summary.json "$PKG/data/"

echo "[3/5] solver patches (the expensive part; scoring is reproducible only from these)"
# Explicit allowlist, not a date filter: the repository also holds health checks and small
# smoke runs from the same period, and an earlier date-based sweep pulled those in.
RUNS=(
  stage6_100_consol                      # tranche 1 of the main matrix
  matrix200_extra100_20260630_174724     # tranche 2
  matrix382_extra182_20260706_134335     # tranche 3
  rerun_matrix_qwen3_20260825_164839     # run 1, repo-grounded enhancers, half A
  rerun_matrix_qwen3_B_20260825_165431   # run 1, half B
  rerun3_A_20260827_234635               # run 3, all five agents with repo access
  rerun3_B_20260827_234639
  rerun4_A_20260828_220623               # run 4, append-only
  rerun4_B_20260828_220627
  targeted60v2_20260831_132828           # targeted localisation experiment
  targeted60v3_20260831_210847
  replication80_20260903_014441          # pre-registered replication
  oai_aider_oh_279eval_20260805_203247   # GPT-5-mini cross-model check
  cl_enhanced_382_20260730_173424        # reward-gated enhancer
)
n=0
for r in "${RUNS[@]}"; do
  [ -d "$ROOT/runs/$r" ] || { echo "      WARNING: runs/$r missing" >&2; continue; }
  while IFS= read -r p; do
    rel=${p#"$ROOT"/runs/}
    dest="$PKG/predictions/$(dirname "$rel")"
    mkdir -p "$dest" && cp "$p" "$dest/" && n=$((n+1))
  done < <(find "$ROOT/runs/$r" -name preds.json 2>/dev/null)
done
echo "      $n prediction files from ${#RUNS[@]} runs"

echo "[4/5] code and documentation"
cp -r "$ROOT"/scripts/evaluate "$ROOT"/scripts/analysis "$PKG/scripts/"
cp -r "$ROOT"/src "$PKG/scripts/src"
cp "$ROOT"/docs/REPRODUCE.md "$PKG/"
cp -r "$ROOT"/docs/analysis "$PKG/docs/"
find "$PKG" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "[5/5] integrity check: no credentials in the archive"
if grep -rIlE 'ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{40,}' "$PKG" 2>/dev/null | head -1 | grep -q .; then
  echo "REFUSING TO PACKAGE: a credential pattern appears in the archive." >&2
  grep -rIlE 'ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{40,}' "$PKG" 2>/dev/null | head >&2
  exit 1
fi
echo "      clean"

tar -C "$OUT" -czf "$PKG.tar.gz" "$(basename "$PKG")"
rm -rf "$PKG"
echo
echo "Wrote $PKG.tar.gz  ($(du -h "$PKG.tar.gz" | cut -f1))"
echo "Upload to Zenodo and put the DOI in the paper's data-availability statement."
