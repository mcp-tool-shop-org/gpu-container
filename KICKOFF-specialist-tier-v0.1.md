Kickoff — Specialist Tier v0.1: the framework (target repo = role-os)

## What this is

Add a **specialist tier** to Role OS: the ability to back a role with a locally-served, trained
low-rank adapter that handles high-frequency narrow dispatches, fronted by a **calibrated gate**
that decides "specialist vs Claude" per dispatch and **fails open to Claude** on any uncertainty.

**v0.1 ships the FRAMEWORK, not a trained specialist.** The deliverable is the control plane —
policy, schema, gate, workload quota, certification/rollback lifecycle — provable end-to-end with a
**stub/passthrough specialist backend** (no GPU, no adapter required). Training real adapters is a
later kickoff; the two specialists designed against this framework (Verifier → prism-verify's L4
lens; Token Budget Analyst → role-os itself) have their own dataset kickoffs
(`KICKOFF-specialist-verifier-dataset.md`, `KICKOFF-specialist-token-budget-dataset.md`).

**Read first:** the architectural lock — `C:/Users/mikey/.claude/projects/F--AI/memory/specialist-tier-architecture.md`.
It records the locked decisions (don't re-litigate them) and the composition map (which existing
tool plays which part). Then `memory/role-os-lockdown-doctrine.md` and `memory/MEMORY.md`.

## This composes existing infrastructure — do NOT reinvent

Role OS **already has** a local seat: `roleos ... --local-panel` (v2.5) and v2.6's panel judges
prism's full abstract. The specialist tier is the formalization of "the local seat is a *trained
adapter*, not a generic base model," plus the gate and the certification lifecycle. Find the
existing `--local-panel` code path first and extend it; do not build a parallel one.

| Concern | Owner (existing tool) | This kickoff's job |
|---|---|---|
| Training the adapter | [[backpropagate]] (PyPI v1.5.0 — rsLoRA, adapter-native export, eval-gated merges) | none (later kickoff) — just define the registry contract it exports into |
| Serving the adapter | gpu-container (vLLM multi-LoRA) | none (later kickoff) — just define the HTTP client contract |
| The verifier product | prism-verify (v1.0.0, `local` family slot) | none — it's a *consumer* |
| The role framework + gate | **role-os** | **everything in v0.1** |

The gate lives in role-os (TS); it talks to the serving substrate over **HTTP** (language-agnostic),
so v0.1's stub backend is just a local HTTP handler returning canned verdicts.

## Office language (non-negotiable — no RPG terms)

Use these names in all code, policy, docs, and comments. The earlier RPG framing (class/character/
XP/level/multiclass/party/respec) is **dropped** — it narrows who will adopt the tool.

| Concept | Name to use |
|---|---|
| A job a specialist can be trained for | **role** (existing) |
| A trained, versioned adapter deployed for a role | **specialist** |
| A training round that passed the eval gate | **certification level** (e.g. "Verifier, certified L2") |
| The frozen labeled eval set | **certification exam** |
| The rolling production-slice eval | **field audit** |
| The rule for when to use a specialist | **dispatch criteria** |
| A specialist trained for two roles, dispatched in sequence | **cross-training** (NOT fused weights — see lock) |
| Revert to a previous specialist version | **version rollback** |
| Max share of dispatches one specialist may take | **workload quota** |

## Architectural locks (from the study-swarm — do not re-open)

1. **Separate gate, not self-report.** The gate is its own small classifier (or embedding/deterministic
   router in v0.1), NOT the specialist grading its own confidence. RLHF-trained models systematically
   inflate verbalized confidence (Leng et al. 2024, arXiv:2410.09724). One-vs-All `P(specialist is
   right)` per specialist (Verma & Nalisnick, ICML 2022, arXiv:2202.03673) — never a joint softmax.
2. **Fail open to Claude.** The gate routes to the specialist ONLY when its OvA score > θ AND the
   input is not OOD AND the specialist's workload quota isn't exhausted. Any miss → Claude. A
   mis-routed specialist must never silently corrupt downstream work.
3. **Workload quota (anti-collapse).** Cap any one specialist at N% of dispatches per window; force a
   periodic shadow-probe to Claude as a ground-truth check (Switch Transformer load-balance pressure,
   Fedus et al. 2022, arXiv:2101.03961).
4. **Sequential dispatch, NOT fused multiclass.** v1 chains specialists (verifier → critic); it does
   not merge adapters at inference. Weight-merging fails for semantically adjacent narrow specialists
   (Chen et al. 2025 position paper, arXiv:2506.13479; Zhang & Zhou 2025, arXiv:2505.22934). Multiclass
   is a v2 research bet behind an A/B gate.
5. **Cross-family base.** Specialist base model is Qwen3 / Gemma (NOT a Claude-family model) — this
   satisfies workflow standard #6 (EXTERNAL_VERIFIER) by construction and is required, not stylistic
   (Panickssery et al., NeurIPS 2024, arXiv:2404.13076).

## Respect the Lockdown Doctrine (this is a seam change)

Adding a specialist backend to a repo is exactly the kind of seam `role-os-lockdown-doctrine.md`
governs: generic orchestration that trusts a specialist's output unsupervised is the wrong change the
system must be able to reject. So the specialist tier ships **with its own reject conditions**, not
just scaffolding:

- The gate **fails open** (reject conditions in the policy file).
- A specialist verdict that fails its consumer's own check (e.g. prism's submodularity/strip guards
  for the Verifier) is **rejected**, not accepted.
- **Workload quota** is a hard cap, not a guideline.
- **Shadow-probe disagreement** beyond a threshold halts specialist dispatch for that role (andon).

## Tracks

### Track A — Specialist policy + role schema
- `policy/specialist-tier.md` — what a specialist is, the dispatch criteria, fail-open, workload
  quota, certification levels, version rollback. Written as **law with reject conditions** (lockdown
  doctrine §5), not description.
- Role schema extension: a role may declare a `specialist:` block —
  `{ backend_url, adapter_id, gate_threshold, fallback: "claude", workload_quota, certified_level }`.
  Roles without the block behave exactly as today (Claude-backed). Additive, non-breaking.

### Track B — The gate (dispatcher)
- Extend the existing `--local-panel` dispatch path. The gate computes OvA `P(specialist is right)`;
  routes to the specialist only on (score > θ ∧ ¬OOD ∧ quota-ok); else Claude.
- v0.1 gate can be **deterministic + embedding-similarity** (cheap, no training) — a trained gate is
  an enhancement. The point of v0.1 is the *control path*, fully testable against a **stub backend**.
- Shadow-probe: every Kth specialist dispatch also calls Claude; log agreement. Disagreement > τ over
  a window halts specialist dispatch for that role and emits an andon event.

### Track C — Certification + rollback lifecycle
- Define the two-track eval **contract** (the harness is built in the dataset/training kickoffs):
  **certification exam** (frozen labeled set) + **field audit** (rolling production slice). A
  specialist is "certified at level N" only when both tracks agree, with replication across two seeds
  (narrow fine-tunes show phase-transition behavior — Snell et al. 2024, arXiv:2411.16035).
- **Adapter registry** contract: specialists are versioned entries (`role, adapter_id, base_model,
  certified_level, exam_hash, field_audit_window`). Before inventing one, confirm whether an existing
  registry concept fits — [[backpropagate]] ships adapter-native export; style-dataset-lab has an
  "adapter registry" feature — and adopt/extend it; otherwise define this minimal schema in role-os.
- **Version rollback** is the named compensator: `roleos specialist rollback <role> <version>` reverts
  the active adapter pointer to a prior certified version. Pure pointer swap, no retrain.

### Track D — Tests + a stub proof
- Unit-test the gate: fail-open on low score, fail-open on OOD, quota cap enforced, OvA threshold,
  shadow-probe-disagreement halt.
- One end-to-end test with a **stub specialist backend** (canned HTTP responses): dispatch → gate →
  (specialist | Claude) → result, asserting fail-open fires when the stub returns low confidence.
- No GPU. No real adapter. The stub proves the control plane.

## Standards compliance (per workflow-standards.md — required section)

| # | Standard | Score | Evidence / remediation |
|---|---|---|---|
| 1 | PIN_PER_STEP | 2 | Specialist dispatch pins `adapter_id + base_model + gate_threshold + exam_hash` in the registry entry and the dispatch log; replayable. Remediation to 3: pin the gate model/version too once the gate is trained (owner: tier maintainer, later kickoff). |
| 2 | ANDON_AUTHORITY | 3 | Gate fails open on any uncertainty; shadow-probe disagreement halts specialist dispatch for the role; quota cap halts over-use. Reject conditions are enforced in policy + gate, not prose. |
| 3 | NAMED_COMPENSATORS | 3 | `version rollback` (pointer swap to prior certified adapter) is the named in-product compensator; owner = tier maintainer. This kickoff performs **no irreversible external action** (no publish/release) — see compensator note below. |
| 4 | DECOMPOSE_BY_SECRETS | 3 | Four boundaries, each hiding one secret family (Parnas): `gate` (routing logic), `serving-client` (vLLM HTTP), `certification` (eval/registry), `policy` (dispatch law). |
| 5 | UNCERTAINTY_GATED_HUMANS | 2 | Shadow-probe disagreement raises a director checkpoint (contrastive: "the specialist said X; Claude said Y; I halted because…"). Held at 2 — the checkpoint is logged, not yet interactive. Remediation: wire to the director-review channel (owner: tier maintainer, target: v0.2). |
| 6 | EXTERNAL_VERIFIER | 3 | Specialist base is cross-family (Qwen3/Gemma) by construction; the Verifier specialist's output is still wrapped by prism's family-different + submodularity guards. Satisfied natively. |

**Compensators (no-skip check):** this kickoff writes only to the role-os repo on a feature branch and
runs local tests. No `npm publish`, no `gh release`, no tag push, no `gh repo edit`. The only
irreversible-ish action is a git commit, undone by `git revert` / branch deletion. The in-product
compensator (`version rollback`) is specified in Track C. **No publish happens in this kickoff.**

## Rules
- **Repo-first / canonical-ownership:** role-os → `mcp-tool-shop-org` (it exists, v2.6.0). Work on a
  **feature branch** (e.g. `specialist-tier`), never main. Confirm `git remote -v` + branch first.
- **Lockdown doctrine:** the specialist tier ships with reject conditions (Track A + the policy file).
  Do not call it done until the gate can say *no* (fail-open + quota + shadow-halt all tested).
- **Workflow-standards:** the section above is mandatory; keep it current as Tracks land.
- **Office language:** no RPG terms anywhere in shipped artifacts.
- **Commit only when Mike asks.** Stage explicit files (never `git add -A`). End commit messages with:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Don't train anything here.** If you find yourself reaching for a GPU, you're out of v0.1 scope —
  that's the training kickoff. v0.1 is provable with a stub.

## First moves
1. Read the architectural lock (`memory/specialist-tier-architecture.md`), `role-os-lockdown-doctrine.md`,
   `MEMORY.md`, and prism-verify `design/01-research-grounding.md` (Locks 1–4 — the Verifier consumer's
   contract).
2. `cd E:\AI\role-os`; confirm state: `git remote -v`, `git branch --show-current`, the test suite
   green (`npm test` or the repo's runner — confirm), and the **existing `--local-panel` code path**
   (grep `local-panel` / `localPanel`). Extend it; don't fork it.
3. Confirm [[backpropagate]]'s adapter-registry schema (so Track C composes it, not a second registry).
4. Branch `specialist-tier`. Land Track A (policy + schema) → B (gate + stub) → C (lifecycle) → D
   (tests). Keep the Standards section current.

## Out of scope (v0.1)
- Any real adapter training (→ later training kickoff, gated by the two dataset kickoffs).
- The trained gate classifier (v0.1 gate is deterministic/embedding — additive upgrade later).
- Fused multiclass / cross-training (v2 research bet).
- Ollama serving (vLLM is the serving substrate — see lock; ollama-intern integration is later, per Mike).
- Interactive director checkpoint (logged in v0.1; wired in v0.2).
