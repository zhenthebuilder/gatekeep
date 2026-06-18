# govern-deliverables: gatekeep

This repository is the full output of a long-horizon research run whose
goal was: *build something people can use to better control and govern the
deliverables of long-horizon agent tasks.*

The answer built here is **gatekeep**: a deterministic, offline,
sub-millisecond deliverable-contract checker. You declare what a
long-horizon task must produce in a small YAML file; `gatekeep` checks the
real artifact state against that declaration and reports pass/fail with
reasons — no LLM call, no API key, fully reproducible.

This repo itself is governed by its own tool: see `gatekeep.yml` for the
contract describing this project's five required deliverables (mirrored
from `BRIEF.md`), and `SELF_CHECK.md` / `SELF_CHECK_report.json` for the
report from running `gatekeep` against this very repository.

## Where everything is

| Deliverable (per the brief) | Location |
|---|---|
| 1. Deployable system | [`gatekeep/`](gatekeep/) — pip package + zero-dependency single file. Start with [`gatekeep/README.md`](gatekeep/README.md) for the under-5-minute install. |
| 2. NeurIPS-format paper | [`paper/paper.tex`](paper/paper.tex) / [`paper/paper.pdf`](paper/paper.pdf) |
| 3. Public-benchmark A/B | [`benchmark/`](benchmark/) — real SWE-bench Lite data, fetch + scoring scripts, raw logs, results |
| 4. Marketing plan | [`marketing/MARKETING.md`](marketing/MARKETING.md) |
| 5. Landing page | [`index.html`](index.html) — open directly in a browser, no build step |

Process artifacts (for a reviewer to trace decisions):

- [`PLAN.md`](PLAN.md) — the initial plan/outline (first commit)
- [`DECISIONS.md`](DECISIONS.md) — every judgment call made during the run, including real bugs found via dogfooding and how they were fixed
- [`gatekeep.yml`](gatekeep.yml) — this run's own deliverable contract
- [`SELF_CHECK.md`](SELF_CHECK.md) / [`SELF_CHECK_report.json`](SELF_CHECK_report.json) — the result of running that contract against this repo

## 30-second version

```bash
cd gatekeep
python3 gatekeep_single.py init      # writes an example gatekeep.yml
python3 gatekeep_single.py check     # runs it, prints a report, exit 0/1
```

Or, to see the real experiment behind the paper:

```bash
python3 benchmark/scripts/run_ab.py
cat benchmark/results/ab_summary.json
```

Every number in `paper/paper.tex` is produced by code in this repository,
run against real, publicly fetched data — see `benchmark/` and
[`paper/paper.tex`](paper/paper.tex) Section 8 (Reproducibility) for exact
commands.
