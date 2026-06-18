"""Deterministic check implementations for gatekeep.

Every check is a pure function: (path: Path, spec: dict) -> CheckResult.
No network calls, no LLM calls, no nondeterminism — this is the property
that makes gatekeep's reported numbers reproducible by anyone, with or
without API keys, on or offline.

Adding a new check type means adding one function here and registering it
in CHECK_REGISTRY. Each check_kind has a documented spec contract (the keys
it reads out of the YAML node) at the top of the function as a docstring.
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class CheckResult:
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


# Markers that frequently indicate an agent papered over an unfinished
# deliverable rather than actually doing the work. Conservative list,
# case-insensitive, intended to be low-false-positive: each is a strong
# signal on its own, not a vibe.
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
    """Resolve a glob pattern relative to root; return sorted matches."""
    if any(ch in pattern for ch in "*?["):
        return sorted(root.glob(pattern))
    p = root / pattern
    return [p] if p.exists() else []


def check_file_exists(root: Path, spec: dict) -> CheckResult:
    """spec: {path: str (glob ok), min_count: int = 1}"""
    pattern = spec["path"]
    min_count = spec.get("min_count", 1)
    matches = _resolve(root, pattern)
    ok = len(matches) >= min_count
    return CheckResult(
        ok=ok,
        message=(
            f"found {len(matches)} match(es) for '{pattern}' "
            f"(need >= {min_count})"
        ),
        details={"matches": [str(m.relative_to(root)) for m in matches]},
    )


def check_min_size(root: Path, spec: dict) -> CheckResult:
    """spec: {path: str, min_bytes: int = 1}"""
    pattern = spec["path"]
    min_bytes = spec.get("min_bytes", 1)
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return CheckResult(False, f"no file matched '{pattern}'", {})
    too_small = [
        str(m.relative_to(root)) for m in matches if m.stat().st_size < min_bytes
    ]
    ok = len(too_small) == 0
    return CheckResult(
        ok=ok,
        message=(
            f"{len(matches) - len(too_small)}/{len(matches)} file(s) meet "
            f"min_bytes={min_bytes}"
        ),
        details={"too_small": too_small},
    )


def check_min_words(root: Path, spec: dict) -> CheckResult:
    """spec: {path: str, min_words: int}"""
    pattern = spec["path"]
    min_words = spec["min_words"]
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return CheckResult(False, f"no file matched '{pattern}'", {})
    failures = []
    for m in matches:
        try:
            text = m.read_text(errors="ignore")
        except Exception as e:  # pragma: no cover - defensive
            failures.append(f"{m.name}: unreadable ({e})")
            continue
        n = len(text.split())
        if n < min_words:
            failures.append(f"{m.name}: {n} words < {min_words}")
    ok = len(failures) == 0
    return CheckResult(
        ok=ok,
        message=f"{len(matches) - len(failures)}/{len(matches)} file(s) meet min_words",
        details={"failures": failures},
    )


def check_no_placeholder_text(root: Path, spec: dict) -> CheckResult:
    """spec: {path: str, patterns: list[str] = DEFAULT_PLACEHOLDER_PATTERNS,
    allow: list[str] = []}
    `allow` is a list of substrings; lines containing any allow-listed
    substring are skipped (escape hatch for legitimate uses of a word, e.g.
    this very file).
    """
    pattern = spec["path"]
    patterns = spec.get("patterns", DEFAULT_PLACEHOLDER_PATTERNS)
    allow = spec.get("allow", [])
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return CheckResult(False, f"no file matched '{pattern}'", {})
    hits = []
    for m in matches:
        try:
            text = m.read_text(errors="ignore")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(a in line for a in allow):
                continue
            for cre in compiled:
                if cre.search(line):
                    hits.append(f"{m.relative_to(root)}:{lineno}: {cre.pattern}")
    ok = len(hits) == 0
    return CheckResult(
        ok=ok,
        message=f"{len(hits)} placeholder marker(s) found" if hits else "clean",
        details={"hits": hits[:50]},
    )


def check_json_valid(root: Path, spec: dict) -> CheckResult:
    """spec: {path: str}"""
    pattern = spec["path"]
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return CheckResult(False, f"no file matched '{pattern}'", {})
    bad = []
    for m in matches:
        try:
            json.loads(m.read_text())
        except Exception as e:
            bad.append(f"{m.relative_to(root)}: {e}")
    ok = len(bad) == 0
    return CheckResult(ok, "valid JSON" if ok else f"{len(bad)} invalid", {"bad": bad})


def check_regex_required(root: Path, spec: dict) -> CheckResult:
    """spec: {path: str, pattern: str, flags: str = ''}
    Requires at least one match of `pattern` somewhere in the file(s).
    """
    pattern = spec["path"]
    needle = spec["pattern"]
    flags = re.IGNORECASE if "i" in spec.get("flags", "") else 0
    cre = re.compile(needle, flags)
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return CheckResult(False, f"no file matched '{pattern}'", {})
    missing = []
    for m in matches:
        text = m.read_text(errors="ignore")
        if not cre.search(text):
            missing.append(str(m.relative_to(root)))
    ok = len(missing) == 0
    return CheckResult(
        ok,
        "pattern present" if ok else f"pattern missing in {len(missing)} file(s)",
        {"missing": missing},
    )


def check_valid_unified_diff(root: Path, spec: dict) -> CheckResult:
    """spec: {path: str, min_files: int = 1, forbid_test_only: bool = False}
    Validates the file looks like a syntactically coherent unified diff
    (has `diff --git` or `---`/`+++` headers and at least one hunk `@@`),
    and counts how many distinct files it touches.
    """
    pattern = spec["path"]
    min_files = spec.get("min_files", 1)
    forbid_test_only = spec.get("forbid_test_only", False)
    matches = [m for m in _resolve(root, pattern) if m.is_file()]
    if not matches:
        return CheckResult(False, f"no file matched '{pattern}'", {})
    problems = []
    for m in matches:
        text = m.read_text(errors="ignore")
        if not text.strip():
            problems.append(f"{m.relative_to(root)}: empty patch")
            continue
        file_headers = re.findall(r"^diff --git a/(.+?) b/(.+?)$", text, re.MULTILINE)
        hunks = re.findall(r"^@@ .* @@", text, re.MULTILINE)
        if not file_headers:
            file_headers = re.findall(r"^\+\+\+ b/(.+?)$", text, re.MULTILINE)
            file_headers = [(f, f) for f in file_headers]
        if not hunks:
            problems.append(f"{m.relative_to(root)}: no @@ hunks found (not a real diff)")
            continue
        if len(file_headers) < min_files:
            problems.append(
                f"{m.relative_to(root)}: touches {len(file_headers)} file(s), need >= {min_files}"
            )
        touched = [f[1] if isinstance(f, tuple) else f for f in file_headers]
        non_test = [f for f in touched if "test" not in f.lower()]
        if forbid_test_only and touched and not non_test:
            problems.append(
                f"{m.relative_to(root)}: only touches test file(s): {touched}"
            )
    ok = len(problems) == 0
    return CheckResult(ok, "valid diff" if ok else f"{len(problems)} problem(s)", {"problems": problems})


def check_forbid_glob(root: Path, spec: dict) -> CheckResult:
    """spec: {path: str}  — fails if any file matches (used to ban stray
    scratch/temp files from being mistaken for deliverables)."""
    pattern = spec["path"]
    matches = _resolve(root, pattern)
    ok = len(matches) == 0
    return CheckResult(
        ok,
        "none found" if ok else f"{len(matches)} forbidden match(es)",
        {"matches": [str(m.relative_to(root)) for m in matches]},
    )


CHECK_REGISTRY: dict[str, Callable[[Path, dict], CheckResult]] = {
    "file_exists": check_file_exists,
    "min_size": check_min_size,
    "min_words": check_min_words,
    "no_placeholder_text": check_no_placeholder_text,
    "json_valid": check_json_valid,
    "regex_required": check_regex_required,
    "valid_unified_diff": check_valid_unified_diff,
    "forbid_glob": check_forbid_glob,
}
