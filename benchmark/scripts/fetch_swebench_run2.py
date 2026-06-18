#!/usr/bin/env python3
"""Fetch a SECOND, independent SWE-bench `experiments` run, used only as a
generalization / robustness check (Section "Generalization" in the paper):
does gatekeep's signal hold up on a different agent's submissions, not just
the one used for the headline numbers in Table 1?

Run: 20250226_sweagent_claude-3-7-sonnet-20250219 (SWE-agent + Claude 3.7
Sonnet), a later, separate, real public submission in the same
swe-bench/experiments repository. This run's public assets do not include
full .traj trajectories, so we cannot reconstruct an identical Arm A
baseline (no exit_status field) -- see
benchmark/scripts/run_ab_second_run.py for how Arm A is adapted faithfully
for this run (still "trust the agent's own production of a patch," just
without the exit_status refinement).
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

RUN = "20250226_sweagent_claude-3-7-sonnet-20250219"
BASE = f"https://swe-bench-submissions.s3.amazonaws.com/lite/{RUN}"
HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"
RAW_DIR = DATA_DIR / "raw" / RUN

SESSION = requests.Session()


def fetch(url: str, timeout: int = 20) -> bytes | None:
    for attempt in range(4):
        try:
            resp = SESSION.get(url, timeout=timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            time.sleep(1 + attempt)
    return None


def fetch_instance(iid: str) -> tuple[str, dict]:
    inst_dir = RAW_DIR / iid
    inst_dir.mkdir(parents=True, exist_ok=True)
    status = {"report": True, "patch": True}

    report_path = inst_dir / "report.json"
    if not report_path.exists():
        data = fetch(f"{BASE}/logs/{iid}/report.json")
        if data is None:
            status["report"] = False
        else:
            report_path.write_bytes(data)

    patch_path = inst_dir / "patch.diff"
    if not patch_path.exists():
        data = fetch(f"{BASE}/logs/{iid}/patch.diff")
        if data is None:
            status["patch"] = False
        else:
            patch_path.write_bytes(data)

    return iid, status


def main() -> int:
    ids_path = DATA_DIR / "instance_ids.txt"
    instance_ids = [l.strip() for l in ids_path.read_text().splitlines() if l.strip()]
    print(f"fetching artifacts for {len(instance_ids)} instances from run={RUN}", flush=True)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"run": RUN, "fetched": 0, "missing_report": [], "missing_patch": []}

    done = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(fetch_instance, iid): iid for iid in instance_ids}
        for fut in as_completed(futures):
            iid, status = fut.result()
            if not status["report"]:
                summary["missing_report"].append(iid)
            if not status["patch"]:
                summary["missing_patch"].append(iid)
            done += 1
            summary["fetched"] = done
            if done % 25 == 0:
                print(f"  ...{done}/{len(instance_ids)}", flush=True)

    (DATA_DIR / f"fetch_summary_{RUN}.json").write_text(json.dumps(summary, indent=2))
    print("done.", flush=True)
    print(
        f"missing: report={len(summary['missing_report'])} patch={len(summary['missing_patch'])}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
