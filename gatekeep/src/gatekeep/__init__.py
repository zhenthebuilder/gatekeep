"""gatekeep — deliverable contracts for long-horizon agent tasks.

A small, deterministic governance layer: declare what a long-horizon task
must deliver in a `gatekeep.yml` contract, then run `gatekeep check` to get
a structured pass/fail report against the real artifact state — independent
of any agent's own self-report that it is "done".
"""

from .engine import Contract, Report, run_contract
from .checks import CHECK_REGISTRY

__version__ = "0.1.0"

__all__ = [
    "Contract",
    "Report",
    "run_contract",
    "CHECK_REGISTRY",
    "__version__",
]
