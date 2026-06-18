"""Contract loading + execution engine for gatekeep."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .checks import CHECK_REGISTRY, CheckResult


@dataclass
class Deliverable:
    id: str
    description: str
    severity: str  # "required" | "advisory"
    checks: list[dict]


@dataclass
class Contract:
    name: str
    deliverables: list[Deliverable]
    version: str = "1"

    @classmethod
    def from_dict(cls, d: dict) -> "Contract":
        deliverables = []
        for item in d.get("deliverables", []):
            deliverables.append(
                Deliverable(
                    id=item["id"],
                    description=item.get("description", ""),
                    severity=item.get("severity", "required"),
                    checks=item.get("checks", []),
                )
            )
        return cls(
            name=d.get("name", "unnamed-contract"),
            deliverables=deliverables,
            version=str(d.get("version", "1")),
        )

    @classmethod
    def from_yaml(cls, path: Path) -> "Contract":
        with open(path) as f:
            d = yaml.safe_load(f)
        return cls.from_dict(d)


@dataclass
class DeliverableReport:
    id: str
    description: str
    severity: str
    ok: bool
    check_results: list[dict] = field(default_factory=list)


@dataclass
class Report:
    contract_name: str
    root: str
    generated_at: float
    deliverables: list[DeliverableReport]

    @property
    def passed(self) -> bool:
        return all(
            d.ok for d in self.deliverables if d.severity == "required"
        )

    @property
    def required_total(self) -> int:
        return sum(1 for d in self.deliverables if d.severity == "required")

    @property
    def required_passed(self) -> int:
        return sum(
            1 for d in self.deliverables if d.severity == "required" and d.ok
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_name": self.contract_name,
            "root": self.root,
            "generated_at": self.generated_at,
            "passed": self.passed,
            "required_total": self.required_total,
            "required_passed": self.required_passed,
            "deliverables": [
                {
                    "id": d.id,
                    "description": d.description,
                    "severity": d.severity,
                    "ok": d.ok,
                    "check_results": d.check_results,
                }
                for d in self.deliverables
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        lines = []
        status = "PASS" if self.passed else "FAIL"
        lines.append(f"# gatekeep report — {self.contract_name}")
        lines.append("")
        lines.append(f"**Overall: {status}**  ")
        lines.append(f"Root: `{self.root}`  ")
        lines.append(
            f"Required deliverables: {self.required_passed}/{self.required_total} passed"
        )
        lines.append("")
        lines.append("| Deliverable | Severity | Status | Notes |")
        lines.append("|---|---|---|---|")
        for d in self.deliverables:
            mark = "PASS" if d.ok else "FAIL"
            notes = "; ".join(
                cr["message"] for cr in d.check_results if not cr["ok"]
            ) or "ok"
            lines.append(f"| `{d.id}` | {d.severity} | {mark} | {notes} |")
        lines.append("")
        for d in self.deliverables:
            if d.ok:
                continue
            lines.append(f"## FAIL: {d.id}")
            lines.append(d.description)
            for cr in d.check_results:
                if not cr["ok"]:
                    lines.append(f"- check `{cr['kind']}`: {cr['message']}")
            lines.append("")
        return "\n".join(lines)


def run_contract(contract: Contract, root: Path) -> Report:
    root = Path(root)
    deliverable_reports = []
    for dlv in contract.deliverables:
        check_results = []
        for check_spec in dlv.checks:
            kind = check_spec["kind"]
            fn = CHECK_REGISTRY.get(kind)
            if fn is None:
                check_results.append(
                    {
                        "kind": kind,
                        "ok": False,
                        "message": f"unknown check kind '{kind}'",
                        "details": {},
                    }
                )
                continue
            try:
                result: CheckResult = fn(root, check_spec)
            except Exception as e:  # defensive: a broken check fails closed
                result = CheckResult(False, f"check raised: {e}", {})
            check_results.append(
                {
                    "kind": kind,
                    "ok": result.ok,
                    "message": result.message,
                    "details": result.details,
                }
            )
        ok = all(cr["ok"] for cr in check_results)
        deliverable_reports.append(
            DeliverableReport(
                id=dlv.id,
                description=dlv.description,
                severity=dlv.severity,
                ok=ok,
                check_results=check_results,
            )
        )
    return Report(
        contract_name=contract.name,
        root=str(root),
        generated_at=time.time(),
        deliverables=deliverable_reports,
    )
