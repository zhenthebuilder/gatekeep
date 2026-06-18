#!/usr/bin/env python3
"""Generalization check: re-run the same A/B methodology as run_ab.py on a
SECOND, independent, real SWE-bench Lite agent submission
(SWE-agent + Claude 3.7 Sonnet, run 20250226_sweagent_claude-3-7-sonnet-20250219)
to check whether gatekeep's signal is specific to one agent/model or holds
up on a different one.

Methodological note (documented honestly): this run's public assets do not
include full .traj trajectories (no `exit_status` field available), so Arm
A here is "the agent produced ANY non-null/non-empty patch" rather than
"non-null patch AND exit_status starts with 'submitted'" (the refinement
used for the primary run in run_ab.py). This is, if anything, a slightly
MORE permissive (easier to satisfy) baseline than Arm A in the primary
experiment, which makes it a fair or conservative comparison point for
gatekeep, not one stacked in gatekeep's favor.

This script is a robustness check, not the paper's headline result --
results are reported separately in benchmark/results/ab_summary_run2.json
and discussed in the paper's Generalization subsection, kept clearly
distinct from Table 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DATA_DIR = HERE.parent / "data"
RESULTS_DIR = HERE.parent / "results"
RUN = "20250226_sweagent_claude-3-7-sonnet-20250219"
RAW_DIR = DATA_DIR / "raw" / RUN

sys.path.insert(0, str(REPO_ROOT / "gatekeep" / "src"))
from gatekeep.engine import Contract, run_contract  # noqa: E402

CONTRACT_PATH = HERE.parent / "contracts" / "swebench_patch.yml"


def load_ground_truth(iid: str) -> bool | None:
    report_path = RAW_DIR / iid / "report.json"
    if not report_path.exists():
        return None
    try:
        d = json.loads(report_path.read_text())
    except Exception:
        return None
    inner = d.get(iid, d)
    if isinstance(inner, dict) and "resolved" in inner:
        return bool(inner["resolved"])
    return None


def arm_a_baseline(iid: str) -> tuple[bool, str]:
    """Adapted baseline for this run (no exit_status available): shippable
    iff a non-empty patch.diff exists at all."""
    patch_path = RAW_DIR / iid / "patch.diff"
    if not patch_path.exists():
        return False, "no patch.diff fetched"
    text = patch_path.read_text(errors="ignore")
    if text.strip():
        return True, f"non-empty patch.diff present ({len(text)} chars)"
    return False, "patch.diff present but empty"


def arm_b_gatekeep(iid: str, contract: Contract) -> tuple[bool, str]:
    patch_path = RAW_DIR / iid / "patch.diff"
    inst_dir = RAW_DIR / iid
    if not patch_path.exists():
        return False, "no patch.diff fetched"
    report = run_contract(contract, inst_dir)
    reasons = []
    for d in report.deliverables:
        if not d.ok:
            for cr in d.check_results:
                if not cr["ok"]:
                    reasons.append(f"{d.id}:{cr['kind']}:{cr['message']}")
    return report.passed, "; ".join(reasons) if reasons else "contract passed"


def confusion(pred: list[bool], gold: list[bool]) -> dict:
    tp = sum(1 for p, g in zip(pred, gold) if p and g)
    fp = sum(1 for p, g in zip(pred, gold) if p and not g)
    fn = sum(1 for p, g in zip(pred, gold) if not p and g)
    tn = sum(1 for p, g in zip(pred, gold) if not p and not g)
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision == precision and recall == recall and (precision + recall) > 0)
        else float("nan")
    )
    accuracy = (tp + tn) / len(gold) if gold else float("nan")
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1, "accuracy": accuracy,
        "n": len(gold),
    }


def main() -> int:
    instance_ids = [
        l.strip() for l in (DATA_DIR / "instance_ids.txt").read_text().splitlines() if l.strip()
    ]
    contract = Contract.from_yaml(CONTRACT_PATH)

    rows = []
    skipped = []
    for iid in instance_ids:
        gold = load_ground_truth(iid)
        if gold is None:
            skipped.append(iid)
            continue
        a_pred, a_reason = arm_a_baseline(iid)
        b_pred, b_reason = arm_b_gatekeep(iid, contract)
        rows.append(
            {
                "instance_id": iid,
                "resolved": gold,
                "arm_a_shippable": a_pred,
                "arm_a_reason": a_reason,
                "arm_b_shippable": b_pred,
                "arm_b_reason": b_reason,
            }
        )

    gold_list = [r["resolved"] for r in rows]
    a_list = [r["arm_a_shippable"] for r in rows]
    b_list = [r["arm_b_shippable"] for r in rows]

    arm_a_metrics = confusion(a_list, gold_list)
    arm_b_metrics = confusion(b_list, gold_list)

    doomed = [r for r in rows if not r["resolved"]]
    a_let_through = sum(1 for r in doomed if r["arm_a_shippable"])
    b_let_through = sum(1 for r in doomed if r["arm_b_shippable"])

    summary = {
        "run": RUN,
        "note": (
            "Generalization/robustness check on a second, independent real "
            "agent submission. Arm A is adapted (non-empty patch present, "
            "no exit_status field available for this run) -- see module "
            "docstring. Not the paper's headline Table 1; reported "
            "separately to avoid conflating two different Arm-A definitions."
        ),
        "n_instances_total": len(instance_ids),
        "n_instances_with_ground_truth": len(rows),
        "n_skipped_no_ground_truth": len(skipped),
        "skipped_no_ground_truth": skipped,
        "arm_a_baseline_metrics": arm_a_metrics,
        "arm_b_gatekeep_metrics": arm_b_metrics,
        "doomed_deliverables_total": len(doomed),
        "arm_a_doomed_let_through": a_let_through,
        "arm_a_doomed_caught": len(doomed) - a_let_through,
        "arm_b_doomed_let_through": b_let_through,
        "arm_b_doomed_caught": len(doomed) - b_let_through,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "ab_summary_run2.json").write_text(json.dumps(summary, indent=2))
    (RESULTS_DIR / "ab_raw_rows_run2.json").write_text(json.dumps(rows, indent=2))

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
