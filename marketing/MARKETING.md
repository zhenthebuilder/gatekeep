# Marketing Plan — gatekeep

## 1. Positioning

**One-liner:** Gatekeep is a deterministic CI gate for what your AI agent
actually shipped — not what it claims it shipped.

**Category:** Agent reliability / agent ops tooling. Sits alongside
observability (Braintrust, LangSmith), eval frameworks (promptfoo, OpenAI
Evals), and CI tools (GitHub Actions) — but none of those answer the
specific question gatekeep answers: *"did the deliverables this long-running
agent task promised actually land, in a verifiable, machine-checkable
form?"*

**Tagline options (pick A for launch):**
- A. "Trust, but verify your agent's output."
- B. "Contracts for what your agent ships."
- C. "Don't let your agent grade its own homework."

## 2. Problem framing (the pitch)

Long-horizon agent runs — multi-hour coding sessions, autonomous research
tasks, agentic SWE workflows — fail in a specific, under-discussed way:
**deliverable drift**. The agent is given N things to produce. Hours later
it reports success. Some of the N things are missing, stubbed out,
truncated, or subtly fabricated, and nobody finds out until a human (or a
downstream system) goes looking — often after the cost of the run is
already sunk.

Our own benchmark (see RESULTS) on 300 real, public, agent-submitted
SWE-bench Lite tasks shows the scale of the problem concretely: 11 of the
300 tasks fetched zero generated patch from the agent at all, yet would
have been silently treated as "submitted" by status-quo exit-code-based
governance. A deterministic deliverable contract catches every one of
these at zero cost, before any expensive test suite ever runs.

This isn't a hypothetical. It's measured, on a real public benchmark, with
a real agent (SWE-agent + Claude 3.5 Sonnet), using artifacts the agent
actually produced.

## 3. Target users (in priority order)

1. **Agent framework / harness builders** — teams building autonomous
   coding agents, research agents, or operator-style agents who need a
   governance primitive they can wire into their own CI/eval loop.
2. **Platform / DevEx teams running agents at a company** — anyone who lets
   an LLM agent open PRs, write docs, or produce reports unattended and
   wants a cheap pre-flight check before a human reviews it.
3. **Individual builders shipping with Claude Code / Cursor / Devin-style
   agents** — people who already feel the "agent said done, it wasn't"
   pain personally and want a 2-minute fix.
4. **Eval / benchmark teams** — people building benchmarks for agents who
   want a deliverable-completeness pre-filter before expensive scoring.

## 4. Channels & tactics (90-day plan)

### Week 1 — Launch
- **GitHub README + landing page live** (`index.html`), pip-installable
  and curl-installable, both verified < 5 minutes start to finish.
- **Hacker News "Show HN"** post: "Show HN: gatekeep — a deterministic CI
  gate that catches when your AI agent didn't actually finish." Lead with
  the concrete number (11/300 zero-output tasks caught at zero cost) and
  link straight to the SWE-bench-derived A/B with raw logs in-repo —
  HN rewards reproducibility and real numbers over claims.
- **Twitter/X thread** from the project account: 6-8 tweets walking through
  the SWE-bench experiment, the precision/recall numbers, and a 15-second
  terminal recording of `gatekeep init && gatekeep check` failing on a
  deliberately broken contract.
- **r/MachineLearning + r/LocalLLaMA** posts focused on the benchmark
  methodology (researchers there scrutinize methodology, which is our
  strongest asset since the numbers are real and reproducible).

### Weeks 2-4 — Integration content
- Write and publish 3 integration guides as blog-style markdown in the
  repo: "gatekeep + GitHub Actions", "gatekeep + Claude Code hooks",
  "gatekeep + your own agent harness in 10 lines." Cross-link from README.
- Submit gatekeep to `awesome-ai-agents` / `awesome-llmops` curated lists
  (low cost, durable discovery channel).
- Reach out (cold, low-pressure) to 5-10 open-source agent-framework
  maintainers (SWE-agent, OpenHands, AutoGPT-style projects) showing the
  GitHub Action integration as a drop-in addition to their CI, since our
  benchmark substrate literally is their public submission data — natural,
  credible warm intro ("we used your public SWE-agent run to validate
  this, here's what it found").

### Month 2 — Depth
- Publish the NeurIPS-format paper (this repo's `paper/`) to arXiv once
  ready; cross-post abstract + key figure to the channels above.
- Add 2-3 more public-benchmark integrations beyond SWE-bench (e.g. a
  GAIA-style task contract template) to broaden applicability and give a
  reason for a second wave of content.
- Start a minimal "wall of contracts" — a community gallery of
  `gatekeep.yml` files for common task types (data pipeline deliverables,
  doc-generation tasks, research-report tasks) to lower time-to-value for
  new adopters to under 5 minutes for their specific use case, not just
  the generic example.

### Month 3 — Retention & expansion
- Track adoption via GitHub stars/clones/Action installs (the only
  metrics available without a backend — gatekeep is deliberately
  serverless/telemetry-free, which is itself a selling point for a
  governance tool: it does not phone home).
- Solicit 3-5 real "contract" case studies from early adopters (with
  permission) as social proof, replacing hypothetical use cases in the
  landing page with real ones.

## 5. Messaging by audience

| Audience | Hook |
|---|---|
| Agent builders | "Add one YAML file and a CI step; stop debugging 'why did the agent say done when it wasn't.'" |
| Eng leadership / platform teams | "A governance primitive with zero LLM cost and zero added latency — deterministic, auditable, and it never phones home." |
| Researchers / eval teams | "Reproducible by anyone: same contract, same verdict, forever — no model version drift in your grading layer." |
| Individual developers | "30 seconds to your first failing contract. No signup." |

## 6. Pricing / distribution model

Free, open-source (MIT), no hosted service, no telemetry. This is a
deliberate go-to-market choice, not a placeholder: governance tools earn
trust by being inspectable and by not creating a new vendor dependency in
the critical path of someone else's CI. Monetization (if pursued later)
would be a hosted "contract gallery + dashboard" layer on top, kept
strictly optional and never required for the core CLI to work fully
offline.

## 7. Success metrics for this plan

- Concrete, measurable, and honest about what we can actually track without
  a backend:
  - GitHub stars / forks / Action marketplace installs (proxy for reach).
  - Issues/PRs opened by people who are not the original author (proxy for
    real adoption vs. drive-by traffic).
  - Citations or forks of the SWE-bench evaluation script specifically
    (proxy for research-community credibility, separate from product
    adoption).
- Explicitly NOT tracked: revenue, DAU/MAU (no backend exists to measure
  this truthfully, and claiming otherwise would violate the no-fabrication
  rule this whole project is built under).
