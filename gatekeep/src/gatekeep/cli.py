"""gatekeep CLI.

Usage:
    gatekeep check [CONTRACT] [--root PATH] [--json] [--out FILE] [--quiet]
    gatekeep init [--out FILE]
    gatekeep --version
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .engine import Contract, run_contract

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


def cmd_init(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"refusing to overwrite existing {out} (use --force)", file=sys.stderr)
        return 1
    out.write_text(EXAMPLE_CONTRACT)
    print(f"wrote example contract to {out}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    contract_path = Path(args.contract)
    if not contract_path.exists():
        print(f"contract file not found: {contract_path}", file=sys.stderr)
        return 2
    contract = Contract.from_yaml(contract_path)
    root = Path(args.root)
    report = run_contract(contract, root)

    if args.json:
        text = report.to_json()
    else:
        text = report.to_markdown()

    if args.out:
        Path(args.out).write_text(text)
        if not args.quiet:
            print(f"report written to {args.out}")
    if not args.quiet or not args.out:
        print(text)

    return 0 if report.passed else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gatekeep")
    p.add_argument("--version", action="version", version=f"gatekeep {__version__}")
    sub = p.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="run a deliverable contract against a workspace")
    p_check.add_argument("contract", nargs="?", default="gatekeep.yml")
    p_check.add_argument("--root", default=".", help="root directory to check (default: cwd)")
    p_check.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p_check.add_argument("--out", default=None, help="write report to file")
    p_check.add_argument("--quiet", action="store_true", help="suppress stdout echo when --out given")
    p_check.set_defaults(func=cmd_check)

    p_init = sub.add_parser("init", help="write an example gatekeep.yml")
    p_init.add_argument("--out", default="gatekeep.yml")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
