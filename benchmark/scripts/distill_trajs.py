#!/usr/bin/env python3
"""Distill the full .traj files down to the small set of fields our
checker/analysis actually needs (exit_status, submission text, step count).

The full raw .traj files are large (tens to hundreds of KB each, ~88MB
total across 289 instances) and are themselves a downloadable, re-fetchable
public artifact (see fetch_swebench_run.py) — re-fetching is one command
and ~1 minute, so we do not commit them to git. We do commit this distilled
summary (a few KB) so the rest of the pipeline (and a reviewer without
network access) can still inspect exactly what was extracted from each
trajectory and why.
"""

from __future__ import annotations

import json
from pathlib import Path

RUN = "20240620_sweagent_claude3.5sonnet"
HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"
RAW_DIR = DATA_DIR / "raw" / RUN


def main() -> int:
    out = {}
    for inst_dir in sorted(RAW_DIR.iterdir()):
        if not inst_dir.is_dir():
            continue
        iid = inst_dir.name
        traj_path = inst_dir / "traj.json"
        if not traj_path.exists():
            out[iid] = {"traj_present": False}
            continue
        try:
            d = json.loads(traj_path.read_text())
        except Exception as e:
            out[iid] = {"traj_present": True, "parse_error": str(e)}
            continue
        info = d.get("info", {})
        submission = info.get("submission") or ""
        out[iid] = {
            "traj_present": True,
            "exit_status": info.get("exit_status"),
            "n_trajectory_steps": len(d.get("trajectory", [])),
            "submission_chars": len(submission),
            "model_stats": info.get("model_stats", {}),
        }
    out_path = DATA_DIR / "traj_distilled.json"
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"wrote {out_path} ({len(out)} instances)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
