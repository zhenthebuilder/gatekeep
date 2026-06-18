---
description: Start a long-horizon research run from a brief. Reads the brief and pursues its high-level goal autonomously.
argument-hint: "[path-to-brief or inline directive]"
---

You are starting a long-horizon research run.

Read the brief below. It is the entire spec for what you must accomplish. Read
it carefully before doing anything else.

$ARGUMENTS

Operating rules for the entire run:

- Do not ask the user clarifying questions. The user is not available during
  the run. If something is ambiguous, make a documented decision in a
  DECISIONS.md (or equivalent) and proceed.
- Use only real numbers from your own experiments. Do not fabricate
  measurements, tool output, citations, or benchmark scores.
- Reframe the problem if a sharper framing serves the high-level goal better,
  but only the high-level goal is fixed; do not change the deliverables list
  or the rules.
- Match a recognized academic conference format if you produce a paper.
- Commit your progress to git in the local worktree so a reviewer can trace
  your decisions.

Begin by reading the brief in full, then outline your plan as your first
commit, then execute.
