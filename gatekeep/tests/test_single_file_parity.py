"""Asserts gatekeep_single.py (zero-dependency fallback) produces the same
pass/fail verdicts as the installed gatekeep package on the same fixtures.
This is what keeps the README's "two install paths" claim honest.
"""

import importlib.util
import json
import sys
import textwrap
from pathlib import Path

import pytest

from gatekeep.engine import Contract, run_contract as pkg_run_contract

SINGLE_FILE = Path(__file__).resolve().parents[1] / "gatekeep_single.py"


def _load_single_module():
    spec = importlib.util.spec_from_file_location("gatekeep_single", SINGLE_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


single = _load_single_module()


CONTRACT_YAML = textwrap.dedent(
    """\
    name: parity-contract
    version: 1
    deliverables:
      - id: readme
        description: "readme exists and is substantive"
        severity: required
        checks:
          - kind: file_exists
            path: "README.md"
          - kind: min_words
            path: "README.md"
            min_words: 20
          - kind: no_placeholder_text
            path: "README.md"
      - id: tests
        description: "tests exist"
        severity: advisory
        checks:
          - kind: file_exists
            path: "tests/*.py"
            min_count: 1
    """
)


@pytest.mark.parametrize("readme_words,expect_pass", [(30, True), (5, False)])
def test_parity_pass_fail(tmp_path, readme_words, expect_pass):
    (tmp_path / "README.md").write_text("word " * readme_words)
    (tmp_path / "gatekeep.yml").write_text(CONTRACT_YAML)

    # Package path
    contract = Contract.from_yaml(tmp_path / "gatekeep.yml")
    pkg_report = pkg_run_contract(contract, tmp_path).to_dict()

    # Single-file path
    parsed = single.yaml_load(CONTRACT_YAML)
    single_report = single.run_contract(parsed, tmp_path)

    assert pkg_report["passed"] == single_report["passed"] == expect_pass
    assert pkg_report["required_passed"] == single_report["required_passed"]
    assert pkg_report["required_total"] == single_report["required_total"]
    pkg_ids_ok = {d["id"]: d["ok"] for d in pkg_report["deliverables"]}
    single_ids_ok = {d["id"]: d["ok"] for d in single_report["deliverables"]}
    assert pkg_ids_ok == single_ids_ok


def test_yaml_loader_handles_nested_lists():
    text = textwrap.dedent(
        """\
        name: x
        deliverables:
          - id: a
            severity: required
            checks:
              - kind: file_exists
                path: "a.txt"
                min_count: 2
        """
    )
    parsed = single.yaml_load(text)
    assert parsed["name"] == "x"
    assert parsed["deliverables"][0]["id"] == "a"
    assert parsed["deliverables"][0]["checks"][0]["kind"] == "file_exists"
    assert parsed["deliverables"][0]["checks"][0]["min_count"] == 2


def test_yaml_loader_handles_folded_block_scalar_then_more_siblings():
    """Regression test: a `description: >` folded block scalar inside a
    list item must not swallow subsequent sibling deliverables. This bug
    was caught by dogfooding gatekeep's own self-check contract.
    """
    text = textwrap.dedent(
        """\
        name: x
        deliverables:
          - id: a
            description: >
              This is a long description
              that wraps across lines.
            severity: required
            checks:
              - kind: file_exists
                path: "a.txt"
          - id: b
            description: "short one"
            severity: required
            checks:
              - kind: file_exists
                path: "b.txt"
        """
    )
    parsed = single.yaml_load(text)
    assert len(parsed["deliverables"]) == 2
    assert parsed["deliverables"][0]["id"] == "a"
    assert "long description" in parsed["deliverables"][0]["description"]
    assert "wraps across lines" in parsed["deliverables"][0]["description"]
    assert parsed["deliverables"][1]["id"] == "b"
    assert parsed["deliverables"][1]["description"] == "short one"


def test_yaml_loader_double_quoted_string_unescapes_like_pyyaml():
    """Regression test: a real bug found via dogfooding gatekeep's own
    paper contract (gatekeep.yml's `research-paper` deliverable uses
    exactly this pattern to require a \\section{Results} heading). Each
    literal `\\\\` in the YAML source must collapse to one `\\` in the
    parsed Python string, matching PyYAML, not just have outer quotes
    stripped verbatim.
    """
    import yaml

    text = 'pattern: "\\\\\\\\section\\\\{Results\\\\}"\n'
    pyyaml_value = yaml.safe_load(text)["pattern"]
    single_value = single.yaml_load(text)["pattern"]
    assert pyyaml_value == "\\\\section\\{Results\\}"
    assert single_value == pyyaml_value


def test_yaml_loader_strips_trailing_inline_comment_like_pyyaml():
    """Regression test: a real bug found via dogfooding. A trailing
    ` # comment` after a quoted scalar must be stripped, matching PyYAML,
    not treated as part of the value.
    """
    import yaml

    text = 'allow:\n  - "TODO list"   # escape hatch example, unused in practice\n'
    pyyaml_value = yaml.safe_load(text)["allow"]
    single_value = single.yaml_load(text)["allow"]
    assert single_value == pyyaml_value == ["TODO list"]


def test_yaml_loader_literal_block_scalar_preserves_newlines():
    text = textwrap.dedent(
        """\
        name: x
        deliverables:
          - id: a
            description: |
              line one
              line two
            severity: advisory
            checks: []
        """
    )
    parsed = single.yaml_load(text)
    assert parsed["deliverables"][0]["description"] == "line one\nline two"
