#!/usr/bin/env python3
"""
Pre-filter stage1 dataset for repos requiring external services that
Paul cannot provision in a bare python:3.10 container:
  - PostgreSQL / PostGIS / MySQL / SQLite spatial
  - Redis / Celery / RabbitMQ / Kafka
  - Elasticsearch / OpenSearch
  - MongoDB
  - Docker-in-Docker (builds requiring docker daemon)

Marks instances as infra_incompatible=True and writes two output files:
  - viable.jsonl    → send to Paul Stage 2
  - incompatible.jsonl → skip Paul, can't be built without external services
"""
import json, re
from pathlib import Path
from collections import Counter

STAGE1  = Path("/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_stage1/dataset.jsonl")
OUT_DIR = Path("/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_stage1")

# Signals in problem_statement, hints, or patch that indicate external service deps
INFRA_PATTERNS = [
    # Database services
    r"\bpostgresql\b", r"\bpostgres\b", r"\bpostgis\b",
    r"\bmysql\b", r"\bmariadb\b",
    r"\bmongodb\b", r"\bmongo\b",
    r"\belasticsearch\b", r"\bopensearch\b",
    r"\bspatialite\b", r"\bgdal\b", r"\bgeos\b",
    # Message brokers / task queues
    r"\bredis\b", r"\bcelery\b", r"\brabbitmq\b", r"\bkafka\b",
    r"\bamqp\b",
    # Infrastructure
    r"\bdocker[-_]?compose\b", r"\bdocker daemon\b",
    r"\bkubernetes\b", r"\bk8s\b",
    # Framework-specific known-infra deps
    r"\bdjango.*database\b", r"\bdjango.*postgre",
    r"\bspatial.*backend\b",
]

compiled = [re.compile(p, re.IGNORECASE) for p in INFRA_PATTERNS]

def is_infra_incompatible(row: dict) -> tuple[bool, list[str]]:
    text = " ".join([
        row.get("problem_statement", "") or "",
        row.get("hints_text", "") or "",
        row.get("all_hints_text", "") or "",
        row.get("patch", "") or "",
        row.get("test_patch", "") or "",
    ])
    matched = []
    for pat, compiled_pat in zip(INFRA_PATTERNS, compiled):
        if compiled_pat.search(text):
            matched.append(pat)
    return bool(matched), matched

rows = [json.loads(l) for l in open(STAGE1)]
viable, incompatible = [], []
signal_counts = Counter()

for row in rows:
    bad, signals = is_infra_incompatible(row)
    if bad:
        row["infra_incompatible"] = True
        row["infra_signals"] = signals
        incompatible.append(row)
        for s in signals:
            signal_counts[s] += 1
    else:
        row["infra_incompatible"] = False
        viable.append(row)

with open(OUT_DIR / "viable_for_paul.jsonl", "w") as f:
    for r in viable: f.write(json.dumps(r) + "\n")
with open(OUT_DIR / "infra_incompatible.jsonl", "w") as f:
    for r in incompatible: f.write(json.dumps(r) + "\n")

print(f"Total stage1 instances:   {len(rows)}")
print(f"Viable for Paul:          {len(viable)}")
print(f"Infra-incompatible:       {len(incompatible)} ({len(incompatible)/len(rows)*100:.1f}%)")
print()
print("Top signals:")
for sig, count in signal_counts.most_common(15):
    print(f"  {sig:40s} {count}")
