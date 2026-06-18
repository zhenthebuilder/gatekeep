#!/usr/bin/env python3
"""A/B experiment: does a deterministic gatekeep deliverable contract give a
useful, cheap, pre-test-suite signal about whether a long-horizon coding
agent's deliverable (its submitted patch) is sound — compared to the status
quo baseline of "the agent's harness reported a submission, therefore ship
it"?

Substrate: 300 real SWE-bench Lite instances, real deliverables from a real
published agent run (SWE-agent + Claude 3.5 Sonnet,
swe-bench/experiments run id 20240620_sweagent_claude3.5sonnet). Ground
truth (`resolved`) comes from princeton-nlp's own SWE-bench evaluation
harness, fetched as part of the public submission's report.json — not
computed by us.

Arm A — baseline / status-quo governance:
    "shippable" iff a non-null patch exists in the trajectory's
    `info.submission` AND the run's exit_status string starts with
    "submitted" (i.e. the agent's own harness believes it finished). This
    mirrors how most agent harnesses gate today: trust the agent's own
    "I'm done" signal.

Arm B — gatekeep:
    Run gatekeep's deterministic `gatekeep.yml` contract (see
    benchmark/contracts/swebench_patch.yml) against the instance's
    logs/<id>/patch.diff. "shippable" iff the contract's required
    deliverable passes (patch exists, non-empty, syntactically valid
    unified diff, touches >=1 non-test file, no placeholder/error markers).

Both arms produce a binary "would let this patch through to the (costly)
test suite" decision per instance, made BEFORE looking at `resolved`. We
then score both arms against the real `resolved` ground truth as a binary
classifier (does "shippable" predict "resolved"?) and report:
  - precision/recall/F1 of each arm at predicting resolved==True
  - how many "doomed" deliverables (resolved==False) each arm would have
    let through vs caught before the test suite ever ran
  - confusion matrices, raw counts

This is NOT a claim that gatekeep makes the agent better at solving
SWE-bench. It is a claim that gatekeep's free, instant, offline check adds
real signal on top of (or instead of) trusting an agent's own completion
self-report, measured on real public data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DATA_DIR = HERE.parent / "data"
RESULTS_DIR = HERE.parent / "results"
RUN = "20240620_sweagent_claude3.5sonnet"
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
    inner = d.get(iid, d)  # report.json is keyed by instance id
    if isinstance(inner, dict) and "resolved" in inner:
        return bool(inner["resolved"])
    return None


def load_traj_info(iid: str) -> dict:
    distilled_path = DATA_DIR / "traj_distilled.json"
    if not hasattr(load_traj_info, "_cache"):
        load_traj_info._cache = json.loads(distilled_path.read_text())
    return load_traj_info._cache.get(iid, {})


def arm_a_baseline(iid: str) -> tuple[bool, str]:
    """Status-quo governance: trust the agent's own exit_status + presence
    of a non-empty submission. No structural inspection of the patch."""
    info = load_traj_info(iid)
    if not info.get("traj_present"):
        return False, "no trajectory at all"
    exit_status = info.get("exit_status") or ""
    submission_chars = info.get("submission_chars", 0)
    if submission_chars > 0 and str(exit_status).startswith("submitted"):
        return True, f"exit_status={exit_status!r}, submission_chars={submission_chars}"
    return False, f"exit_status={exit_status!r}, submission_chars={submission_chars}"


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
    skipped_no_ground_truth = []
    for iid in instance_ids:
        gold = load_ground_truth(iid)
        if gold is None:
            skipped_no_ground_truth.append(iid)
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

    # Headline number: doomed deliverables (resolved=False) that each arm
    # let through to the test suite (i.e. arm said "shippable" but it was
    # not actually resolved) vs caught (arm said "not shippable").
    doomed = [r for r in rows if not r["resolved"]]
    a_let_through = sum(1 for r in doomed if r["arm_a_shippable"])
    a_caught = len(doomed) - a_let_through
    b_let_through = sum(1 for r in doomed if r["arm_b_shippable"])
    b_caught = len(doomed) - b_let_through

    # Among instances arm_a called shippable but arm_b did not: did gatekeep
    # specifically add signal beyond the baseline? (disagreement analysis)
    disagreements = [r for r in rows if r["arm_a_shippable"] and not r["arm_b_shippable"]]
    disagreements_where_b_right = [r for r in disagreements if not r["resolved"]]

    no_generation_count = sum(
        1 for iid in skipped_no_ground_truth if not load_traj_info(iid).get("traj_present")
    )

    summary = {
        "run": RUN,
        "n_instances_total": len(instance_ids),
        "n_instances_with_ground_truth": len(rows),
        "n_skipped_no_ground_truth": len(skipped_no_ground_truth),
        "skipped_no_ground_truth": skipped_no_ground_truth,
        "note_skipped_no_generation_subset": (
            f"{no_generation_count} of the {len(skipped_no_ground_truth)} skipped "
            "instances have no agent trajectory at all (the agent's harness never "
            "produced a submission). Both arms trivially agree these are not "
            "shippable; they are excluded from the precision/recall table above "
            "because there is no SWE-bench evaluation report to use as ground "
            "truth, not because either arm disagrees about them."
        ),
        "arm_a_baseline_metrics": arm_a_metrics,
        "arm_b_gatekeep_metrics": arm_b_metrics,
        "doomed_deliverables_total": len(doomed),
        "arm_a_doomed_let_through": a_let_through,
        "arm_a_doomed_caught": a_caught,
        "arm_b_doomed_let_through": b_let_through,
        "arm_b_doomed_caught": b_caught,
        "n_disagreements_a_shippable_b_not": len(disagreements),
        "n_disagreements_where_b_correctly_flagged_doomed": len(disagreements_where_b_right),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "ab_summary.json").write_text(json.dumps(summary, indent=2))
    (RESULTS_DIR / "ab_raw_rows.json").write_text(json.dumps(rows, indent=2))

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
