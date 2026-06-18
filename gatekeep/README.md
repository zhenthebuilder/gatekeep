# gatekeep

**Deliverable contracts for long-horizon agent tasks.**

Long-horizon agents (and long-horizon human projects) drift: a task starts
with five required deliverables, and by hour six the agent has quietly
dropped one, half-finished another, and is reporting "done." `gatekeep`
gives you a deterministic, sub-second, offline governance check that
verifies what was *actually* produced against what was *promised* — no
LLM call required, no API key required, fully reproducible by anyone.

You declare a **contract** (`gatekeep.yml`): the deliverables a task must
produce and the checks that prove each one is real. You run
`gatekeep check`. You get a pass/fail report with reasons, an exit code
your CI can gate on, and a paper trail.

This is not an LLM judge. It is closer to a linter or a CI gate for
deliverables: file-exists, non-placeholder, well-formed-diff, valid-JSON,
min-length, regex-required, forbid-glob — fast, boring, and exactly as
trustworthy as the rules you write.

## Install (under 5 minutes, two paths)

### Path 1 — zero install, zero dependencies (fastest)

Download one file and run it with any Python 3.9+:

```bash
curl -fsSL https://raw.githubusercontent.com/REPLACE_ME/gatekeep/main/gatekeep_single.py -o gatekeep_single.py
python3 gatekeep_single.py init        # writes an example gatekeep.yml
python3 gatekeep_single.py check       # runs it, prints a report, exits 1 on fail
```

No pip, no virtualenv, no third-party packages — `gatekeep_single.py` only
uses the Python standard library, including its own minimal YAML-subset
parser. If you don't even have network access to fetch it remotely, just
copy the file from this repo; it is fully self-contained.

### Path 2 — pip install (full CLI, `gatekeep` on PATH)

```bash
git clone https://github.com/REPLACE_ME/gatekeep.git
cd gatekeep/gatekeep
pip install .
gatekeep init
gatekeep check
```

(Requires PyYAML, installed automatically as a dependency.)

Both paths read and write the exact same `gatekeep.yml` contract format,
and are kept in parity by the test suite
(`tests/test_single_file_parity.py`).

## Quickstart

```bash
gatekeep init                 # writes example gatekeep.yml in cwd
$EDITOR gatekeep.yml           # declare your real deliverables
gatekeep check                 # human-readable markdown report, exit code 0/1
gatekeep check --json --out report.json   # machine-readable, for CI artifacts
```

## Contract format

```yaml
name: my-project-deliverables
version: 1
deliverables:
  - id: readme
    description: "A README describing the project exists and is substantive."
    severity: required        # required | advisory
    checks:
      - kind: file_exists
        path: "README.md"
      - kind: min_words
        path: "README.md"
        min_words: 50
      - kind: no_placeholder_text
        path: "README.md"

  - id: api-patch
    description: "The agent's code change is a real, non-trivial diff."
    severity: required
    checks:
      - kind: valid_unified_diff
        path: "patch.diff"
        min_files: 1
        forbid_test_only: true   # fails if the diff only touches test files

  - id: tests
    description: "A test suite exists (nice to have, not blocking)."
    severity: advisory
    checks:
      - kind: file_exists
        path: "tests/**/*.py"
        min_count: 1
```

A run **passes** iff every `required` deliverable's checks all pass.
`advisory` deliverables are reported but never block the exit code — use
them for things you want visibility into without hard-failing CI.

## Check kinds (all deterministic, all offline)

| kind | what it does |
|---|---|
| `file_exists` | glob match with a minimum count |
| `min_size` | minimum byte size per matched file |
| `min_words` | minimum word count per matched file |
| `no_placeholder_text` | flags TODO/FIXME/lorem-ipsum/"not implemented"/etc |
| `json_valid` | parses matched files as JSON |
| `regex_required` | requires a regex match somewhere in the file |
| `valid_unified_diff` | validates diff structure, file count, optional test-only ban |
| `forbid_glob` | fails if any file matches (ban stray scratch files) |

Adding a new kind is one function in `checks.py` (or the mirrored block in
`gatekeep_single.py`) plus a registry entry — no plugin system, no magic.

## Why deterministic instead of an LLM judge?

An LLM judge is expressive but non-reproducible (different model, prompt,
or day -> different verdict) and requires an API key. `gatekeep`'s core
engine is intentionally dumb: every check is a pure function over the
filesystem with no network calls, so the same contract gives the same
verdict for anyone, forever, for free. The accompanying paper's Results
section reports how much real failure this catches on a public benchmark
using *only* this deterministic engine — no LLM calls were used to produce
any reported number. (You may still add an LLM-judge check as a `custom`
plugin for soft rubric criteria; gatekeep's architecture doesn't forbid it
— it just never depends on one for its headline guarantees.)

## CI usage

```yaml
# .github/workflows/gatekeep.yml
on: [push, pull_request]
jobs:
  gatekeep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 gatekeep_single.py check
```

That's the entire integration: one file, one command, no install step,
fails the build on a broken contract.

## License

MIT.
