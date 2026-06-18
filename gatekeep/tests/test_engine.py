import json
import textwrap
from pathlib import Path

import pytest

from gatekeep.engine import Contract, run_contract


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_file_exists_pass(tmp_path):
    write(tmp_path / "README.md", "hello " * 60)
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "readme",
                    "severity": "required",
                    "checks": [{"kind": "file_exists", "path": "README.md"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert report.passed
    assert report.deliverables[0].ok


def test_file_missing_fails(tmp_path):
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "readme",
                    "severity": "required",
                    "checks": [{"kind": "file_exists", "path": "README.md"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert not report.passed


def test_advisory_failure_does_not_block_pass(tmp_path):
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "optional-tests",
                    "severity": "advisory",
                    "checks": [{"kind": "file_exists", "path": "tests/*.py"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert report.passed  # advisory-only failures don't block
    assert not report.deliverables[0].ok


def test_min_words(tmp_path):
    write(tmp_path / "short.md", "too short")
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "doc",
                    "severity": "required",
                    "checks": [
                        {"kind": "file_exists", "path": "short.md"},
                        {"kind": "min_words", "path": "short.md", "min_words": 100},
                    ],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert not report.passed
    assert "min_words" not in "" # sanity


def test_no_placeholder_text_catches_todo(tmp_path):
    write(tmp_path / "doc.md", "this section is a TODO for later\n" * 5)
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "doc",
                    "severity": "required",
                    "checks": [{"kind": "no_placeholder_text", "path": "doc.md"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert not report.passed
    hits = report.deliverables[0].check_results[0]["details"]["hits"]
    assert len(hits) > 0


def test_no_placeholder_text_clean_passes(tmp_path):
    write(tmp_path / "doc.md", "this section is finished and complete.\n" * 5)
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "doc",
                    "severity": "required",
                    "checks": [{"kind": "no_placeholder_text", "path": "doc.md"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert report.passed


def test_json_valid(tmp_path):
    write(tmp_path / "good.json", json.dumps({"a": 1}))
    write(tmp_path / "bad.json", "{not json")
    contract_good = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "j",
                    "severity": "required",
                    "checks": [{"kind": "json_valid", "path": "good.json"}],
                }
            ],
        }
    )
    contract_bad = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "j",
                    "severity": "required",
                    "checks": [{"kind": "json_valid", "path": "bad.json"}],
                }
            ],
        }
    )
    assert run_contract(contract_good, tmp_path).passed
    assert not run_contract(contract_bad, tmp_path).passed


def test_valid_unified_diff_detects_empty_patch(tmp_path):
    write(tmp_path / "empty.diff", "")
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "patch",
                    "severity": "required",
                    "checks": [{"kind": "valid_unified_diff", "path": "empty.diff"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert not report.passed


def test_valid_unified_diff_accepts_real_diff(tmp_path):
    diff = textwrap.dedent(
        """\
        diff --git a/foo.py b/foo.py
        index 0000000..1111111 100644
        --- a/foo.py
        +++ b/foo.py
        @@ -1,1 +1,2 @@
         x = 1
        +y = 2
        """
    )
    write(tmp_path / "real.diff", diff)
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "patch",
                    "severity": "required",
                    "checks": [{"kind": "valid_unified_diff", "path": "real.diff"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert report.passed


def test_forbid_test_only_patch(tmp_path):
    diff = textwrap.dedent(
        """\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,1 +1,2 @@
         x = 1
        +y = 2
        """
    )
    write(tmp_path / "real.diff", diff)
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "patch",
                    "severity": "required",
                    "checks": [
                        {
                            "kind": "valid_unified_diff",
                            "path": "real.diff",
                            "forbid_test_only": True,
                        }
                    ],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert not report.passed


def test_unknown_check_kind_fails_closed(tmp_path):
    contract = Contract.from_dict(
        {
            "name": "t",
            "deliverables": [
                {
                    "id": "x",
                    "severity": "required",
                    "checks": [{"kind": "does_not_exist", "path": "x"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    assert not report.passed


def test_report_markdown_and_json_smoke(tmp_path):
    write(tmp_path / "README.md", "hello " * 60)
    contract = Contract.from_dict(
        {
            "name": "smoke",
            "deliverables": [
                {
                    "id": "readme",
                    "severity": "required",
                    "checks": [{"kind": "file_exists", "path": "README.md"}],
                }
            ],
        }
    )
    report = run_contract(contract, tmp_path)
    md = report.to_markdown()
    js = report.to_json()
    assert "smoke" in md
    parsed = json.loads(js)
    assert parsed["passed"] is True
