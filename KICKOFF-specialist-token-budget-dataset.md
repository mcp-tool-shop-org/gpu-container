Kickoff — Token Budget Analyst specialist: dataset build (target repo = role-os)

## ✅ OUTCOME — 2026-06-05 (DONE; the SHIPPED design differs from this spec in two big ways)
Executed on branch `token-budget-dataset` (role-os; commits `32db274` → `c0d6a92`): harvester + corpus +
puzzle curriculum built, tested, committed, pushed. **The current authoritative spec is
`role-os/tools/token-budget-dataset/DESIGN.md`** (+ the architectural lock). Two reframes by Mike during
execution supersede parts of the body below — read these first:

1. **Target = cost-weighted token SPEND, model fixed. Tier-OvA (b) and cascade (c) are DROPPED.** The
   FrugalGPT / tier-routing framing optimizes API dollars by downgrading models — which the studio
   deliberately doesn't do (it runs Opus by design). `cost_weighted_spend = input·1 + cache_write·1.25 +
   cache_read·0.1 + output·5`; raw output hid the economics (cache-read is ~half the real cost). `tier_used`
   + compaction are kept as **metadata**, not prediction targets.
2. **Training format = a PUZZLE CURRICULUM, not a regression table — and the human-grading pass was THROWN
   OUT.** Asking a human to eyeball "was this spend right-sized?" is unanswerable cold (Mike, correctly).
   Replaced by `harvester/puzzles.py`: **440 self-checkable puzzles** across 5 difficulty rungs (the
   certification ladder), **answers computable → no human grading**. The director eyeballs a few puzzles to
   confirm the principle.

**SURVIVED as written:** the scrub/ANDON privacy gate, the fuzzy-join + counterfactual honesty
(starved/wasteful/weak-label), the 5× under-budget cost weight, the deterministic baseline
(`max(ctx·1.5, 50k)`, now predicting *spend*) + the ≥10%-beat-or-ship-deterministic gate, the
exam/audit/train split discipline. The `review-ui/` + `freeze.py` human-resolved-exam path was built but is
now **secondary** to the self-checking puzzle exam.

> Everything below is the ORIGINAL spec, kept as the record of intent. Where it conflicts with the two
> points above, the points above win.

## What this is

Build the **training dataset** for the second specialist — a **Token Budget Analyst** that role-os's
dispatcher consults before each dispatch. **Dataset only. No training.** This is the specialist Mike
flagged as one of the biggest current needs.

Unlike the Verifier, **this dataset does not exist yet** — the first real task is the **harvester**.
Hand the resulting corpus to [[backpropagate]] for training in a later kickoff.

**Read first:** the architectural lock —
`C:/Users/mikey/.claude/projects/F--AI/memory/specialist-tier-architecture.md`. Then `MEMORY.md` and
`role-os-lockdown-doctrine.md`.

## What the Token Budget Analyst predicts (the label space)

> ⚠ **SUPERSEDED — see OUTCOME.** Only **(a)**, reframed to **cost-weighted spend (model fixed)**, is the
> v0.1 target. **(b) model tier and (c) cascade are DROPPED.** **(d) compaction** is kept as metadata /
> an L4 puzzle, not a v0.1 prediction head. Original spec below.

Per dispatch, given (task description, role, context size, complexity signals), predict:
- **(a) token budget** with a **conformal prediction interval** (distribution-free overrun guarantee —
  Yadkori et al., DeepMind 2024, arXiv:2405.01563), not a point estimate;
- **(b) model tier** (Opus / Sonnet / Haiku) as **One-vs-All `P(tier sufficient)`** (Verma & Nalisnick,
  ICML 2022) — not a joint softmax;
- **(c) cascade decision** — try the cheap tier first? (FrugalGPT pattern — Chen et al. 2023,
  arXiv:2305.05176);
- **(d) compaction trigger** — will this dispatch need a mid-run compaction, flagged ahead of time.

## The honest hard part: the label is a counterfactual

We can observe **actual tokens used** and **actual tier picked**, but "optimal budget / cheapest
sufficient tier" is a counterfactual we never directly see. Don't paper over this. The label strategy:

- **Budget label = actual tokens used**, annotated with whether the dispatch was **starved**
  (ran out / needed compaction / failed for length) or **wasteful** (used a large tier for a tiny job).
  So each record carries the observed count *plus* an outcome flag, not a bare number.
- **Tier label = cheapest tier that actually succeeded** where we have a cascade observation; otherwise
  the actual tier + an outcome-quality label (did it complete correctly?).
- **Outcome quality** comes from real signals: dogfood-swarm receipts (did the dispatch succeed?),
  code-review confirmed/refuted, mission pass/fail. No outcome label → the record is a weak/unlabeled
  example, tagged as such (don't pretend it's ground truth).

This counterfactual honesty is the difference between a useful budgeter and a confident-wrong one —
the "where do labels come from" problem the research flags as the binding constraint.

## Cost asymmetry (locked)
**Under-budget is much worse than over-budget.** Running out mid-task = lost work; over-provisioning =
some wasted tokens. Tag records so training/eval weights the false-"enough" (predicted sufficient,
actually starved) at ~**5× the false-"not-enough"** cost (Wang 2025, arXiv:2510.22016). The eval is
**not** balanced accuracy; it's cost-at-fixed-quality (FrugalGPT framing): "matched quality at X% of
the generalist-default cost."

## The sanity gate the specialist must beat (or it doesn't ship)
A learned budgeter only earns its keep if it beats a **deterministic baseline**. Define and record the
baseline now so the later eval is honest:
- baseline budget = `max(context_tokens * 1.5, 50_000)`;
- baseline tier = a small rule table (e.g. context/role → tier).

The specialist must beat this baseline by **≥10% cost at equal quality** on the certification exam, or
v0.1 ships the deterministic policy and the weights wait. (This is basic experimental hygiene, not a
cited result — state it as such.)

## Dataset contract (what to actually produce)

> ⚠ **SUPERSEDED by the shipped schema** — `harvester/schema.py` + `DESIGN.md §11`. Changes vs the original
> below: **dropped** `cascade_observed` / `cheapest_sufficient_tier` (tier/cascade are not targets);
> **`tokens_used` → `cost_weighted_spend`** + its four raw components (`input/cache_creation/cache_read/
> output _total`); `tier_used` + `compaction_*` + `peak_context_tokens` kept as **metadata**;
> **added** `label_reason` (the contrastive rationale), `baseline_spend`, `grain`, `join_confidence`;
> `outcome_source` gained `"transcript"` + `"human"`. The corpus is the **scenario bank**; the trained
> artifact is the **puzzle curriculum** (`harvester/puzzles.py` → `dataset/v0.1/puzzles/`).

Original contract (kept for the record):
```
{ dispatch_id, task_text, role, context_tokens, complexity_signals: {...},
  tokens_used, tier_used, cascade_observed: bool, cheapest_sufficient_tier: str|null,
  outcome: "success"|"starved"|"wasteful"|"failed"|"unknown",
  outcome_source: "dogfood"|"code-review"|"mission"|"none", weak_label: bool }
```

Splits, same discipline as the Verifier:
- **Certification exam** — frozen, the level-progression metric set. **SHIPPED REALITY:** the certification
  exam is the **self-checking puzzle exam** (`puzzles_exam.jsonl`, 55 puzzles, answers computable). The
  human-resolved `exam.jsonl` path (`review-ui/` + `freeze.py`) was built but is **secondary** — the
  "human grades spend" idea was dropped as unanswerable.
- **Field audit** — rolling slice from new dispatches after each training cutoff; exam↔audit divergence
  is the overfitting alarm.
- Exam temporally disjoint from training; never sampled into the training pool. **(Done: puzzle splits are
  keyed by source dispatch so no scenario leaks across the boundary.)**

## Where the data lives (the harvester's real challenge)
The signal is spread across:
- **Claude Code session transcripts** — the harness writes `agent-*.jsonl` per run in the transcript
  directory; these carry token usage. **Confirm the actual path/format first** (don't assume).
- **role-os mission logs / run records** — mission pass/fail + which roles ran.
- **dogfood-swarm receipts** and **code-review outputs** — outcome-quality labels to join on.

The harvester's job is to locate, parse, and **join** these into dispatch records. Build a small sample
end-to-end and inspect it before scaling — the join keys (how to match a transcript dispatch to an
outcome) are the part most likely to be wrong.

## ⚠ Privacy / scrub (load-bearing here)
Transcripts and mission logs contain real work — possibly secrets, paths, PII, proprietary canon. The
harvester **must** run a scrub pass before any record leaves role-os: strip credentials/keys, redact
absolute user paths, drop verbatim large artifacts (keep features: length, role, signals — not raw
content where avoidable). Training data is forever; do not bake secrets into it.

## Standards compliance (per workflow-standards.md — required section)

| # | Standard | Score | Evidence / remediation |
|---|---|---|---|
| 1 | PIN_PER_STEP | 3 | Each record pins `dispatch_id`, source file, and the harvester version; corpus ships a manifest hash; exam-set hash frozen. |
| 2 | ANDON_AUTHORITY | **3 (DONE)** | Scrub re-scan AND exam↔train contamination check both hard-fail the build; `build.py` writes nothing until both pass. The remediation item is shipped + proven by `test_harvester.py`. |
| 3 | NAMED_COMPENSATORS | 3 | Local versioned files only; compensator = delete the version dir / `git revert`. Reading transcripts/logs is read-only. No external irreversible action. |
| 4 | DECOMPOSE_BY_SECRETS | 3 | `locate` (find sources) · `parse` (per-source) · `join` (dispatch↔outcome) · `scrub` · `split` · `manifest` — each a separate stage hiding one concern. |
| 5 | UNCERTAINTY_GATED_HUMANS | **3 (reframed)** | The director gates the **curriculum**, not the grading: he eyeballs a few puzzles per rung to confirm they teach the right principle. The "human resolves each uncertain spend label" plan was dropped as unanswerable cold (Mike); puzzle answers self-check, so the human gate moved to where a human judgment is actually possible. |
| 6 | EXTERNAL_VERIFIER | 2 | The budgeter judges Claude dispatches and its base is cross-family (non-Claude) — consistent with #6. Held at 2 because the budgeter's *outcome labels* partly derive from the same dispatches it predicts; remediation: hold out an outcome-label source (e.g. mission pass/fail) never used in features (owner: dataset maintainer). |

**Compensators (no-skip check):** local dataset files only; all sources read read-only; no
publish/release/tag/repo-edit. Reversible by `rm` / `git revert`.

## Rig-safety
Largely **no GPU** — this is log parsing + joining. If you use embeddings for dedup/complexity
signals, that's light local inference: run under `gpu-container-watchdog`, N=0, per
`KICKOFF-preflight-rig-safety.md`. No training here.

## Rules
- **Repo-first:** role-os → `mcp-tool-shop-org` (v2.6.0). Local `E:/AI/role-os/`. Feature branch
  (`token-budget-dataset`), not main. Confirm remote + branch.
- role-os is **Node/TS**, but the harvester can be whatever parses the logs cleanly — confirm the repo
  convention; if Python is cleaner for jsonl/joins, put it under a `tools/` or `scripts/` dir and keep
  it out of the shipped npm package.
- Confirm [[backpropagate]]'s expected training-data shape before fixing the corpus format. [[repo-dataset]]
  (v1.2.0) may help package it.
- Workflow-standards section mandatory; keep current.
- Commit only when Mike asks; explicit staging; co-author trailer.

## First moves
> ✅ **ALL DONE** (2026-06-05). Confirmed: transcripts are `subagents/agent-*.jsonl` (token usage in
> `message.usage`) + top-level session `<uuid>.jsonl`; outcomes in `dogfood-labs/swarms/control-plane.db`,
> role-os verdicts, readouts `family-verdicts.json`. Harvested 1217 records, inspected the (fuzzy) join
> before scaling, scrub/split/manifest + baseline all shipped. Nothing here left to do.

1. Read the architectural lock + `MEMORY.md`.
2. **Locate the data**: confirm the Claude Code transcript directory + `agent-*.jsonl` format (where
   token usage actually lives); find role-os mission run records; find dogfood-swarm + code-review
   receipt locations.
3. `cd E:\AI\role-os`; confirm state (remote, branch, tests green). Branch `token-budget-dataset`.
4. Build `locate` + `parse` for ONE source, harvest a small sample, **inspect the join** before
   scaling. Then `scrub`, `split`, `manifest`. Define + record the deterministic baseline.

## Out of scope
- Training the adapter (→ training kickoff).
- The gate/dispatch wiring (→ `KICKOFF-specialist-tier-v0.1.md`; this only produces training data).
- Live token accounting in role-os (a separate runtime feature; this is the offline dataset).
