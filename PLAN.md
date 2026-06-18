# PLAN — Govern Deliverables

## Reframing decision

High-level goal: build something people can use to **better control and
govern the deliverables of long-horizon agent tasks**, adoptable in real
workflows.

Reframing chosen: **"Deliverable Contracts"** — a lightweight, declarative
governance layer that sits between a long-horizon agent run and its outputs.
The system is called **`gatekeep`**.

Why this framing: long-horizon agent runs (exactly like this one) fail
silently in two ways that matter to a person trying to govern them:

1. **Drift** — the agent declares a set of deliverables up front (explicitly
   or implicitly) and silently drops/changes/forgets one over a long run.
2. **Unverifiable claims** — the agent asserts a deliverable is "done" but
   the artifact doesn't actually satisfy machine-checkable properties
   (exists, right shape, internally consistent, no fabricated/placeholder
   content patterns, etc).

`gatekeep` addresses both with a single artifact: a **contract file**
(`gatekeep.yml`) that declares the deliverables a task must produce, plus a
**checker** (CLI + library) that runs structural/content checks against the
actual workspace and produces a pass/fail **governance report** with a
human-readable diff against the contract. It is intentionally NOT another
LLM judge — it is fast, deterministic, dependency-light static
verification, runnable in CI, pre-commit, or ad hoc, so a human (or a
calling agent) gets a verifiable signal independent of the agent's own
self-report. Optional LLM-judge rubric scoring is offered as an add-on
check type for soft criteria (e.g. "paper has a grounded results section")
but the core engine is deterministic.

This is "dogfood-able": I will write a `gatekeep.yml` for THIS very run
(the 5 required deliverables from BRIEF.md) and run `gatekeep check` against
my own workspace before declaring done, as a self-validating proof of concept.

## Deliverables mapping (BRIEF.md requirement -> what I build)

1. **Deployable system** -> `gatekeep/` Python package, pip-installable from
   a local/sdist path AND published as a single-file script
   (`gatekeep/install.sh` one-liner + `pipx`/`pip install .`), plus a
   zero-dependency single-file fallback (`gatekeep_single.py`) usable via
   `curl | python3` for the "under 5 minutes, single command" bar. Includes
   a GitHub Action wrapper for CI adoption.
2. **NeurIPS-format paper** -> `paper/` LaTeX (neurips_2026.sty or similar
   acquired/recreated style), Results section grounded in real measurements
   from (a) our own benchmark harness across multiple synthetic long-horizon
   task transcripts and (b) a public benchmark (see #3).
3. **Public benchmark A/B** -> Use **GAIA** or **a public agent-trajectory
   dataset** as the substrate — need to pick one we can actually fetch and
   score offline without an LLM-as-grader requirement, OR construct an A/B
   where we run a recognized public benchmark's eval harness twice (with vs
   without gatekeep contract-checking in the loop) and report deltas with
   real numbers. Decide concretely after a feasibility pass (see Step 2
   below) — must be something fetchable via WebFetch/pip without needing
   paid API keys for the *benchmark data* itself (LLM calls for the agent
   side may be unavailable too — must design around no-LLM-API-key
   assumption; verify first).
4. **Marketing plan** -> `MARKETING.md`.
5. **Landing page** -> `index.html`, zero build step, links to install
   command from #1.

## Risk / unknowns to resolve early

- Do I have any LLM API key available in this sandbox? If not, the "public
  benchmark A/B" must be framed as: governance layer applied to **existing
  public agent-trajectory logs** (e.g. from a public dataset of agent runs)
  rather than running new live agent rollouts. Need to check environment
  for ANTHROPIC_API_KEY / network access first.
- NeurIPS style files: fetch official .sty from web if reachable; else
  hand-roll a faithful two-column NeurIPS-like LaTeX class substitute and
  document the substitution as a decision.

## Execution steps

1. Environment recon: network access, API keys, LaTeX availability, python
   version. (DECISIONS.md entry)
2. Pick concrete public benchmark substrate; write SCOPE.md decision.
3. Build `gatekeep` core: contract schema (YAML), checker engine (file
   exists / glob / json-schema / regex-forbidden(placeholder,TODO,lorem) /
   word-count-min / json-valid / custom python check plug-ins), CLI
   (`gatekeep check`, `gatekeep init`), report renderer (markdown + json).
4. Unit tests for gatekeep (pytest), run them, fix.
5. Package for distribution: pyproject.toml, single-file fallback script,
   one-line install script, README with <5 min quickstart.
6. Build benchmark harness: synthetic long-horizon multi-deliverable task
   corpus (self-built) + the chosen public benchmark; run A/B
   (gatekeep-on vs gatekeep-off / baseline-self-report) with real
   deterministic scoring; save raw logs under `benchmark/results/`.
7. Write NeurIPS-format paper in `paper/`, compile to PDF if latex
   available, embed real numbers/tables from step 6 logs only.
8. Self-validate: write `gatekeep.yml` contract for this very repo's 5
   deliverables, run `gatekeep check .` and include the report as evidence
   (e.g. `SELF_CHECK.md` / report json) — meta proof point for the paper.
9. Marketing plan + landing page.
10. Final pass: re-run gatekeep self-check, fix gaps, commit, stop.

## Decision log location

`DECISIONS.md` in repo root, appended at each judgment call.
