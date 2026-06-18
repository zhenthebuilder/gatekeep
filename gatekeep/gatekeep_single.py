#!/usr/bin/env python3
"""gatekeep_single.py — zero-dependency single-file gatekeep.

Drop this one file anywhere with python3 (3.9+) on PATH and run it. No pip
install, no virtualenv, no third-party dependencies (stdlib only). It
implements the same deterministic check engine as the full `gatekeep`
package, plus a tiny YAML subset parser so it can read the same
`gatekeep.yml` contracts without needing PyYAML.

Usage:
    python3 gatekeep_single.py check [CONTRACT] [--root PATH] [--json]
    python3 gatekeep_single.py init [--out FILE]

One-line try-it (after downloading this file):
    python3 gatekeep_single.py init && python3 gatekeep_single.py check

This file intentionally duplicates (rather than imports) the logic in the
`gatekeep` package so it has zero install step and zero dependencies. See
gatekeep/src/gatekeep/ for the package version with full test coverage;
this file is kept in lockstep with it by the project's test suite
(tests/test_single_file_parity.py in the repo root runs the same contract
through both and asserts identical results).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Minimal YAML-subset loader (supports exactly the shape gatekeep contracts
# use: nested mappings, lists of mappings, scalars, no anchors/multiline).
# --------------------------------------------------------------------------


def _parse_scalar(s: str) -> Any:
    s = s.strip()
    if s == "":
        return None
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        return s[1:-1]
    if s.lower() in ("true", "yes"):
        return True
    if s.lower() in ("false", "no"):
        return False
    if s.lower() in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(x) for x in _split_flow_list(inner)]
    return s


def _split_flow_list(inner: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in inner:
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        if ch in "[{":
            depth += 1
        if ch in "]}":
            depth -= 1
        cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def yaml_load(text: str) -> Any:
    lines = [
        l for l in text.split("\n") if l.strip() and not l.strip().startswith("#")
    ]
    if not lines:
        return {}
    pos = [0]

    def parse_block(min_indent: int) -> Any:
        if pos[0] >= len(lines):
            return None
        first = lines[pos[0]]
        indent = _indent_of(first)
        if indent < min_indent:
            return None
        stripped = first.strip()
        if stripped.startswith("- "):
            return parse_list(indent)
        return parse_map(indent)

    def parse_list(indent: int) -> list:
        result = []
        while pos[0] < len(lines):
            line = lines[pos[0]]
            cur_indent = _indent_of(line)
            if cur_indent != indent or not line.strip().startswith("- "):
                break
            rest = line.strip()[2:]
            pos[0] += 1
            if ":" in rest and not rest.startswith(("'", '"')):
                # inline first key of a map item, e.g. "- id: foo"
                key, _, val = rest.partition(":")
                key = key.strip()
                val = val.strip()
                item: dict[str, Any] = {}
                if val:
                    item[key] = _parse_scalar(val)
                else:
                    item[key] = parse_block(indent + 2)
                # continue reading sibling keys at indent+2
                while pos[0] < len(lines):
                    nxt = lines[pos[0]]
                    nxt_indent = _indent_of(nxt)
                    if nxt_indent != indent + 2 or nxt.strip().startswith("- "):
                        break
                    k2, _, v2 = nxt.strip().partition(":")
                    k2 = k2.strip()
                    v2 = v2.strip()
                    pos[0] += 1
                    if v2:
                        item[k2] = _parse_scalar(v2)
                    else:
                        item[k2] = parse_block(indent + 4)
                result.append(item)
            else:
                result.append(_parse_scalar(rest))
        return result

    def parse_map(indent: int) -> dict:
        result: dict[str, Any] = {}
        while pos[0] < len(lines):
            line = lines[pos[0]]
            cur_indent = _indent_of(line)
            if cur_indent != indent:
                break
            stripped = line.strip()
            if stripped.startswith("- "):
                break
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            pos[0] += 1
            if val:
                result[key] = _parse_scalar(val)
            else:
                nxt = lines[pos[0]] if pos[0] < len(lines) else ""
                nxt_indent = _indent_of(nxt) if nxt.strip() else -1
                if nxt_indent > indent:
                    result[key] = parse_block(nxt_indent)
                else:
                    result[key] = None
        return result

    return parse_block(0)


# --------------------------------------------------------------------------
# Checks (mirrors gatekeep/src/gatekeep/checks.py)
# --------------------------------------------------------------------------

DEFAULT_PLACEHOLDER_PATTERNS = [
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bTBD\b",
    r"lorem ipsum",
    r"\bXXX\b",
    r"\[insert .*?\]",
    r"\bplaceholder\b",
    r"not implemented",
    r"NotImplementedError",
    r"as an AI language model",
    r"I cannot actually",
    r"<your .*? here>",
]


def _resolve(root: Path, pattern: str) -> list[Path]:
    if any(ch in pattern for ch in "*?["):
        return sorted(root.glob(pattern))
    p = root / pattern
    return [p] if p.exists() else []


def check_file_exists(root, spec):
    pattern = spec["path"]
    min_count = spec.get("min_count", 1)
    matches = _resolve(root, pattern)
    ok = len(matches) >= min_count
    return ok, f"found {len(matches)} match(es) for '{pattern}' (need >= {min_count})", {
        "matches": [str(m.relative_to(root)) for m in matches]
    }


def check_min_size(root, spec):
    pattern = spec["path"]
    min_bytes = spec.get("min_bytes", 1)
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return False, f"no file matched '{pattern}'", {}
    too_small = [str(m.relative_to(root)) for m in matches if m.stat().st_size < min_bytes]
    return len(too_small) == 0, f"{len(matches)-len(too_small)}/{len(matches)} meet min_bytes", {"too_small": too_small}


def check_min_words(root, spec):
    pattern = spec["path"]
    min_words = spec["min_words"]
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return False, f"no file matched '{pattern}'", {}
    failures = []
    for m in matches:
        text = m.read_text(errors="ignore")
        n = len(text.split())
        if n < min_words:
            failures.append(f"{m.name}: {n} words < {min_words}")
    return len(failures) == 0, f"{len(matches)-len(failures)}/{len(matches)} meet min_words", {"failures": failures}


def check_no_placeholder_text(root, spec):
    pattern = spec["path"]
    patterns = spec.get("patterns", DEFAULT_PLACEHOLDER_PATTERNS)
    allow = spec.get("allow", [])
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return False, f"no file matched '{pattern}'", {}
    hits = []
    for m in matches:
        text = m.read_text(errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(a in line for a in allow):
                continue
            for cre in compiled:
                if cre.search(line):
                    hits.append(f"{m.relative_to(root)}:{lineno}: {cre.pattern}")
    ok = len(hits) == 0
    return ok, (f"{len(hits)} placeholder marker(s) found" if hits else "clean"), {"hits": hits[:50]}


def check_json_valid(root, spec):
    pattern = spec["path"]
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return False, f"no file matched '{pattern}'", {}
    bad = []
    for m in matches:
        try:
            json.loads(m.read_text())
        except Exception as e:
            bad.append(f"{m.relative_to(root)}: {e}")
    ok = len(bad) == 0
    return ok, ("valid JSON" if ok else f"{len(bad)} invalid"), {"bad": bad}


def check_regex_required(root, spec):
    pattern = spec["path"]
    needle = spec["pattern"]
    flags = re.IGNORECASE if "i" in spec.get("flags", "") else 0
    cre = re.compile(needle, flags)
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return False, f"no file matched '{pattern}'", {}
    missing = []
    for m in matches:
        if not cre.search(m.read_text(errors="ignore")):
            missing.append(str(m.relative_to(root)))
    ok = len(missing) == 0
    return ok, ("pattern present" if ok else f"missing in {len(missing)} file(s)"), {"missing": missing}


def check_valid_unified_diff(root, spec):
    pattern = spec["path"]
    min_files = spec.get("min_files", 1)
    forbid_test_only = spec.get("forbid_test_only", False)
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return False, f"no file matched '{pattern}'", {}
    problems = []
    for m in matches:
        text = m.read_text(errors="ignore")
        if not text.strip():
            problems.append(f"{m.relative_to(root)}: empty patch")
            continue
        file_headers = re.findall(r"^diff --git a/(.+?) b/(.+?)$", text, re.MULTILINE)
        hunks = re.findall(r"^@@ .* @@", text, re.MULTILINE)
        if not file_headers:
            file_headers = [(f, f) for f in re.findall(r"^\+\+\+ b/(.+?)$", text, re.MULTILINE)]
        if not hunks:
            problems.append(f"{m.relative_to(root)}: no @@ hunks found (not a real diff)")
            continue
        if len(file_headers) < min_files:
            problems.append(f"{m.relative_to(root)}: touches {len(file_headers)} file(s), need >= {min_files}")
        touched = [f[1] if isinstance(f, tuple) else f for f in file_headers]
        non_test = [f for f in touched if "test" not in f.lower()]
        if forbid_test_only and touched and not non_test:
            problems.append(f"{m.relative_to(root)}: only touches test file(s): {touched}")
    ok = len(problems) == 0
    return ok, ("valid diff" if ok else f"{len(problems)} problem(s)"), {"problems": problems}


def check_forbid_glob(root, spec):
    pattern = spec["path"]
    matches = _resolve(root, pattern)
    ok = len(matches) == 0
    return ok, ("none found" if ok else f"{len(matches)} forbidden match(es)"), {
        "matches": [str(m.relative_to(root)) for m in matches]
    }


CHECK_REGISTRY = {
    "file_exists": check_file_exists,
    "min_size": check_min_size,
    "min_words": check_min_words,
    "no_placeholder_text": check_no_placeholder_text,
    "json_valid": check_json_valid,
    "regex_required": check_regex_required,
    "valid_unified_diff": check_valid_unified_diff,
    "forbid_glob": check_forbid_glob,
}

# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------


def run_contract(contract: dict, root: Path) -> dict:
    root = Path(root)
    deliverable_reports = []
    for dlv in contract.get("deliverables", []):
        check_results = []
        for spec in dlv.get("checks", []):
            kind = spec["kind"]
            fn = CHECK_REGISTRY.get(kind)
            if fn is None:
                check_results.append({"kind": kind, "ok": False, "message": f"unknown check kind '{kind}'", "details": {}})
                continue
            try:
                ok, message, details = fn(root, spec)
            except Exception as e:
                ok, message, details = False, f"check raised: {e}", {}
            check_results.append({"kind": kind, "ok": ok, "message": message, "details": details})
        ok = all(cr["ok"] for cr in check_results)
        deliverable_reports.append(
            {
                "id": dlv["id"],
                "description": dlv.get("description", ""),
                "severity": dlv.get("severity", "required"),
                "ok": ok,
                "check_results": check_results,
            }
        )
    required = [d for d in deliverable_reports if d["severity"] == "required"]
    passed = all(d["ok"] for d in required)
    return {
        "contract_name": contract.get("name", "unnamed-contract"),
        "root": str(root),
        "generated_at": time.time(),
        "passed": passed,
        "required_total": len(required),
        "required_passed": sum(1 for d in required if d["ok"]),
        "deliverables": deliverable_reports,
    }


def report_to_markdown(report: dict) -> str:
    lines = []
    status = "PASS" if report["passed"] else "FAIL"
    lines.append(f"# gatekeep report — {report['contract_name']}")
    lines.append("")
    lines.append(f"**Overall: {status}**  ")
    lines.append(f"Root: `{report['root']}`  ")
    lines.append(f"Required deliverables: {report['required_passed']}/{report['required_total']} passed")
    lines.append("")
    lines.append("| Deliverable | Severity | Status | Notes |")
    lines.append("|---|---|---|---|")
    for d in report["deliverables"]:
        mark = "PASS" if d["ok"] else "FAIL"
        notes = "; ".join(cr["message"] for cr in d["check_results"] if not cr["ok"]) or "ok"
        lines.append(f"| `{d['id']}` | {d['severity']} | {mark} | {notes} |")
    lines.append("")
    for d in report["deliverables"]:
        if d["ok"]:
            continue
        lines.append(f"## FAIL: {d['id']}")
        lines.append(d["description"])
        for cr in d["check_results"]:
            if not cr["ok"]:
                lines.append(f"- check `{cr['kind']}`: {cr['message']}")
        lines.append("")
    return "\n".join(lines)


EXAMPLE_CONTRACT = """\
name: example-contract
version: 1
deliverables:
  - id: readme
    description: "A README describing the project exists and is substantive."
    severity: required
    checks:
      - kind: file_exists
        path: "README.md"
      - kind: min_words
        path: "README.md"
        min_words: 50
      - kind: no_placeholder_text
        path: "README.md"

  - id: tests
    description: "A test suite exists."
    severity: advisory
    checks:
      - kind: file_exists
        path: "tests/**/*.py"
        min_count: 1
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="gatekeep_single.py")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check")
    p_check.add_argument("contract", nargs="?", default="gatekeep.yml")
    p_check.add_argument("--root", default=".")
    p_check.add_argument("--json", action="store_true")
    p_check.add_argument("--out", default=None)

    p_init = sub.add_parser("init")
    p_init.add_argument("--out", default="gatekeep.yml")
    p_init.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "init":
        out = Path(args.out)
        if out.exists() and not args.force:
            print(f"refusing to overwrite existing {out} (use --force)", file=sys.stderr)
            return 1
        out.write_text(EXAMPLE_CONTRACT)
        print(f"wrote example contract to {out}")
        return 0

    if args.command == "check":
        contract_path = Path(args.contract)
        if not contract_path.exists():
            print(f"contract file not found: {contract_path}", file=sys.stderr)
            return 2
        text = contract_path.read_text()
        if contract_path.suffix == ".json":
            contract = json.loads(text)
        else:
            contract = yaml_load(text)
        report = run_contract(contract, Path(args.root))
        out_text = json.dumps(report, indent=2) if args.json else report_to_markdown(report)
        if args.out:
            Path(args.out).write_text(out_text)
        print(out_text)
        return 0 if report["passed"] else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
