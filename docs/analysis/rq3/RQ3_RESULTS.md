# RQ3 results — first coding pass (2026-09-10)

90-item stratified sample, seed 42, ten per enhancer x outcome cell. Solver held at
OpenHands, model at Qwen3-32B. Codebook in [`CODEBOOK.md`](CODEBOOK.md); labels in
[`rq3_coding_sheet.csv`](rq3_coding_sheet.csv) under `coder1_*`.

## Coding procedure and its limit

A large language model performed this first pass. That is a methodological choice with a
cost, and the paper discloses it rather than leaving a reader to infer it. The specific
limit: an automated pass can see what a rewrite did to the text, but cannot check a cited
symbol against the repository. `B1_hallucinated` was therefore applied only where an
assertion is not derivable from the original report, never where it is merely unverified.
Under that rule, invented-but-obvious reproduction steps do not count as hallucination,
while an invented file path does.

Run `scripts/analysis/rq3_kappa.py` once `coder2_*` is filled. Kappa is computed per code
as a 2x2 present/absent agreement, because both dimensions are multi-label and whole-set
matching would score a four-of-five agreement as a total disagreement.

## What the agents do

| Rewrite move | % | Failure mode | % |
|---|---:|---|---:|
| Restructure into sections | 91 | Drops or buries content | 50 |
| Add reproduction steps | 67 | None observed | 32 |
| Add code context | 50 | Abstained | 9 |
| Add environment info | 14 | Hallucinated specifics | 9 |
| Add root-cause hypothesis | 10 | Over-specified | 2 |
| Surface a stack trace | 6 | | |
| No substantive change | 9 | | |

The template is near-universal at 91%. The moves that would carry real diagnostic content
are the rare ones: a root-cause hypothesis in 10%, a surfaced trace in 6%.

Median length ratio is 1.06x, which hides the behaviour: **34 of 90 outputs are shorter
than their input and 24 are more than twice as long**. Enhancement is about as often
compression as expansion.

## No move is associated with helping

| Pattern | helped | hurt | unchanged | p |
|---|---:|---:|---:|---:|
| Restructure | 26 | 28 | 28 | 0.578 |
| Reproduction steps | 21 | 18 | 21 | 0.638 |
| Code context | 14 | 16 | 15 | 0.875 |
| Environment info | 4 | 5 | 4 | 0.914 |
| Root-cause hypothesis | 4 | 3 | 2 | 0.690 |
| Surface a trace | 2 | 0 | 3 | 0.227 |

Failure modes are equally flat (all p >= 0.587). Nothing about which moves an agent applies
predicts whether the fix improves, which is what RQ1's directionless perturbation looks
like at the level of individual reports.

## Tooling artifacts: 10 of 90

Eleven percent of enhancements carry scaffolding from the enhancer's own execution:

* unfilled template slots where a file path, regex or exception name should be (7 rows);
* a shell heredoc terminator, `EOF > /tmp/.../enhanced_issue.md`, ending the report;
* the benchmark instance identifier pasted in as the issue title;
* pip output and a `sudo` error string from the enhancing machine, inserted as reproduction
  steps, carrying that machine's filesystem paths into the report.

These appear only in the OpenHands (6) and Aider (4) enhancers, never in SWE-agent. An
agent writing prose into a file has no mechanism to check that the file is a well-formed
report, and nothing downstream checks either.

## Individual observations worth keeping

* **Item 45** (PySnooper, hurt): the enhancement invents a concrete one-line output format
  the maintainer never specified and presents it as the expected behaviour. A clear case of
  a fabricated specification preceding a worsened outcome.
* **Item 74** (outlines, unchanged): invents three file names and presents them as an
  Affected Files checklist. None exist in the repository.
* **Item 14** (astropy, helped): the strongest diagnosis in the sample, naming
  `_binparse_fixed` versus `_binparse_var` and the 4-byte length prefix. Real diagnosis is
  possible; it is just rare.
* **Item 54** (sentry-python, unchanged): 168 to 732 characters that add no fact, and leave
  the Affected Files section as the literal instruction to fill it in later.
