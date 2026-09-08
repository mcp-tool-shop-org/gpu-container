Kickoff — Specialist training + serve + wire (the GPU-heavy one; ONE specialist end-to-end first)

## STATUS — 2026-06-05 (read before treating this as "Verifier-first")
- **Framework: LANDED.** `KICKOFF-specialist-tier-v0.1.md` shipped to role-os (fail-open gate + adapter
  registry + version-rollback; merged PR #10). **Precondition 1 is met.**
- **Token Budget Analyst corpus: BUILT** — and it is the corpus that now exists, *not* the Verifier's.
  `role-os/tools/token-budget-dataset/` (branch `token-budget-dataset`): 1217 scrubbed dispatch records +
  a **puzzle curriculum** (440 self-checkable puzzles, 5 rungs, 385 train / 55 exam). **Frame corrected by
  Mike: the target is cost-weighted token SPEND, model fixed — tier-OvA and cascade are DROPPED.** See the
  architectural lock.
- **Verifier L4 corpus: PARTIAL.** Only the capture sink shipped (prism PR #2 `prism.eval.harvest`);
  backfill + MiniCheck hard-negatives + the ~500-record human-resolved exam are still TODO.
- **So "first end-to-end" is now a Mike decision, not a given.** The budgeter corpus is ready *now* and is
  self-checkable (cleaner eval, no human grading); the Verifier wires into a shipped product (prism's
  `local` slot — a cleaner end-to-end demo) but its corpus isn't built. **Track A (prove serving) gates
  both regardless** — pick one, prove it end-to-end, then do the other.

## ⚠ PREFLIGHT FIRST — non-negotiable
Read `KICKOFF-preflight-rig-safety.md` (this repo) BEFORE any GPU/model work, and follow it. Run
**`gpu-container-watchdog --watch`** for the entire session (it monitors the HOST memory — the metric
behind the 2026-06-04 incident). Abort = `wsl --shutdown`. The short version, specialized for training:

- **Training fits this rig comfortably IF configured right** — a **4-bit base** (QLoRA/QDoRA) 7–9B with
  gradient checkpointing + bounded batch×seq lives in well under 16 GB VRAM, far inside the 32 GB card.
  This is NOT the gpt-oss-120b inference case that caused the incident. The danger is a *misconfig*
  (full-precision base, unbounded batch/seq, CPU-paged optimizer ballooning host RAM), not the workload.
- **Pin the safe config:** 4-bit base, gradient checkpointing ON, batch×seq bounded, LoRA optimizer
  stays on-GPU (no CPU offload needed — trainable params are tiny). Keep host RAM < ~80%, VRAM with
  headroom.
- **Never train and serve concurrently** on the single 5090. Train → save adapter → free VRAM → serve.
- **Base model + adapters live on `E:\AI-Models`** (bind mount, never a Docker named volume — the
  C:-drive `docker_data.vhdx` trap).

## Preconditions (do not start until both are true)
1. ✅ **MET — The framework exists.** `KICKOFF-specialist-tier-v0.1.md` is landed (the fail-open gate +
   adapter registry + version-rollback are in role-os, merged PR #10). You wire the trained adapter
   **behind that gate**, so a bad specialist can't corrupt downstream work.
2. ✅ **MET (budgeter) — A corpus exists.** The **Token Budget Analyst** corpus + puzzle curriculum is
   built and manifest-hashed (`role-os/tools/token-budget-dataset/`, train/exam split, no leakage). The
   **Verifier L4** corpus from `KICKOFF-specialist-verifier-dataset.md` is still **partial** (capture sink
   only). So whichever specialist you take first, confirm *its* corpus is the built one.

**Read first:** the architectural lock —
`C:/Users/mikey/.claude/projects/F--AI/memory/specialist-tier-architecture.md` (the locked decisions —
don't re-open them).

## Scope: ONE specialist end-to-end first, then the other
A single specialist proven train→certify→serve→wire is worth more than two half-built ones. **Either the
Verifier (L4) or the Token Budget Analyst can be first** (see STATUS — the budgeter's corpus is the one
already built). They do **NOT** share an identical pipeline:
- **Verifier** = a classification fine-tune (per-pair `{supported|unsupported|abstain}` head, **AUROC/AURC**
  eval, human-resolved exam) → Tracks B + C below.
- **Budgeter** = a **reasoning / puzzle-curriculum** fine-tune (self-checkable answers, **puzzle-accuracy**
  eval, no human grading) → **Track E**, which now stands on its own, not as a "repeat."

Tracks **A** (prove serving) and **D** (serve + wire behind the gate) are shared mechanics for both.

## Track A — Environment + **prove you can serve before you train**
The biggest unknown on this rig is **serving**, not training. Resolve it first, with a generic base
model, before spending a training run you might not be able to deploy:
- **Serving path decision (test early):** vLLM multi-LoRA is the research-preferred server, but vLLM on
  **Blackwell sm_120 + WSL2** is unproven here. The proven-on-rig fallback is **llama.cpp per-request
  LoRA adapters** (PR #10994) — and the gpu-container image (`ghcr.io/ggml-org/llama.cpp:full-cuda`,
  CUDA 12.8) **already ships llama.cpp**. So: try vLLM in WSL2; if it won't build/run on sm_120, use
  llama.cpp's `--lora` per-request hot-swap. Pick the one that actually serves an adapter on this rig
  and record which.
- Smoke-test serving with the **base model + a throwaway/random adapter** (N=0, all-VRAM): confirm the
  endpoint loads the base, hot-swaps an adapter per request, and returns a structured verdict. If you
  can't serve a stub adapter, stop — there's no point training one.
- Download the base (Qwen3-7B or Gemma-2-9B, a 4-bit quant for serving) to `E:\AI-Models` via bind mount.

## Track B — Train the Verifier L4 adapter ([[backpropagate]])
- Train with **backpropagate** (the existing harness). Method: **DoRA r=8–16, α=2r, q/v/o projections**
  if backpropagate supports DoRA; else **rsLoRA** (confirmed supported) at the same rank/α/targets. The
  research prefers DoRA but rsLoRA is a fine v0.1 — confirm support and record the choice.
- **4-bit base (QLoRA/QDoRA), gradient checkpointing ON, bounded batch×seq** (claim/evidence pairs are
  short — cap seq at ~1–2K). Output head: per-pair `{supported | unsupported | abstain}`.
- **Two seeds.** Narrow fine-tunes phase-transition (Snell 2024) — a one-seed jump is noise. Train two;
  a certification level requires the gain to replicate across both.
- Compose backpropagate's **data-quality/eval loop + eval-gated export** rather than a bare training run.

## Track C — Eval harness + certification (the "level" gate)
Build the two-track harness the dataset kickoff specced:
- **Certification exam** (frozen, human-resolved ~500): primary **AUROC** (discriminate first, gate ≥
  ~0.7), then **AURC** at coverage 0.5/0.7/0.9, then Brier/ECE as calibration addenda. Cost-weighted at
  **FP:FN ≈ 5:1** against false-"supported" (a shipped hallucination >> a wasted generalist call).
  Report **multi-hop accuracy separately** (small verifiers lag there — Seo 2025).
- **Field audit** (rolling production slice): same metrics; **exam↔audit divergence is the overfitting
  alarm**.
- **Sanity floor:** don't regress on a public groundedness bench (LLM-AggreFact/MiniCheck) and pass
  prism's existing prism-on-prism meta-test.
- **Certification rule (the gate):** a level is earned only when exam AUROC/AURC improves with
  **non-overlapping bootstrap CIs**, the field audit moves the **same direction**, the sanity floor
  doesn't regress > ~2pp, and it **replicates across the two seeds**. Anything less is not a level —
  log it and keep the prior certified adapter.
- **Conformal abstention:** calibrate the abstain threshold on a held-out slice (distribution-free
  overrun bound — Yadkori 2024). The verifier must be able to say "I don't know" → defer to Claude.

## Track D — Serve the certified adapter + wire it behind the gate
- Serve the certified Verifier adapter (Track A's path) at a stable endpoint.
- **Wire into prism-verify's `local` lens slot** — point prism's local L4 backend at the endpoint. prism
  KEEPS its family-different routing + reasoning-strip + submodularity guards around the cheap local
  lens; the specialist just makes the `local` L4 call cheap+good. Confirm prism's config for the local
  backend URL (don't assume).
- The role-os **fail-open gate** (from the framework kickoff) fronts every specialist dispatch: route to
  the specialist only on (OvA score > θ ∧ ¬OOD ∧ quota-ok); else Claude. Register the adapter in the
  registry at its certified level. Turn on the **shadow-probe** (every Kth dispatch also calls the
  cross-family path; disagreement > τ halts specialist dispatch — andon).

## Track E — Token Budget Analyst (corpus BUILT; a puzzle curriculum, NOT the verifier pipeline)
The budgeter corpus exists now (`role-os/tools/token-budget-dataset/`, built 2026-06-05) and is trained
**differently from the verifier**. Frame (locked by Mike): predict **cost-weighted token spend, model
fixed** — tier-OvA + cascade are **dropped**; compaction is metadata. The delivery is a **puzzle
curriculum** that teaches the *principles* of token economics, then asks the real prediction.

- **Data:** `python -m harvester.puzzles build` → 5 self-checkable rungs from real dispatches
  (L1 spot-the-driver · L2 which-costs-more (the trap) · L3 fit-or-split · L4 spot-the-failure ·
  L5 what-if), 385 train / 55 exam, split by source dispatch (no leakage). **Every answer is computable —
  no human grading.** Cost model = `input·1 + cache_write·1.25 + cache_read·0.1 + output·5` (confirm
  absolute $/Mtok before dollarizing). Spend is heavy-tailed → **estimate in log space**.
- **Train (backpropagate):** same rig-safe mechanics as Track B (4-bit base, DoRA/rsLoRA r=8–16, grad
  checkpointing, bounded batch×seq, **two seeds**) — but as a **reasoning / instruction SFT**: puzzle
  prompt → worked reasoning → verifiable answer. Because answers are checkable, this is a natural fit for
  **rejection-sampling SFT or RLVR** (reward = answer correct) if backpropagate supports it; else plain
  SFT on the worked solutions.
- **Certify — the rungs ARE the levels:** primary metric = **held-out puzzle-exam accuracy per rung**
  (`puzzles_exam.jsonl`, self-checking — no AUROC, no human labels). A rung is *earned* only when its exam
  accuracy clears the bar with **non-overlapping CIs across two seeds** AND the model still passes the
  **lower** rungs (no catastrophic forgetting). The progression is the certification ladder; add harder
  rungs over time.
- **Beat-the-baseline floor (still binding):** on the *real* prediction that follows each puzzle, the
  trained budgeter must beat the deterministic baseline (`baseline_spend = max(context·1.5, 50k)`) by
  **≥10% at equal quality**, or v0.1 ships the deterministic policy and the weights wait. (Experimental
  hygiene — recorded per-record in the corpus manifest, not a cited result.)
- **Serve + wire:** Track D's mechanics, but behind **role-os's dispatcher gate** (consulted before each
  dispatch), not prism's lens. **Fail open to the deterministic baseline** (not Claude) on low confidence
  / OOD — the baseline is the safe floor here.
- **Director gate (already in motion):** Mike eyeballs a handful of puzzles per rung to confirm they teach
  the right principle — never hand-grades spend (that ask was dropped, correctly).

## Standards compliance (per workflow-standards.md — required section)

| # | Standard | Score | Evidence |
|---|---|---|---|
| 1 | PIN_PER_STEP | 3 | Each certification pins base-model SHA + adapter hash + training config + seed + exam-set hash + the metrics, in the adapter registry — byte-for-byte replayable. |
| 2 | ANDON_AUTHORITY | 3 | The certification gate refuses to promote a non-replicating/regressing adapter; the runtime shadow-probe halts specialist dispatch on disagreement; the gate fails open on uncertainty/OOD/quota. |
| 3 | NAMED_COMPENSATORS | 3 | **Version rollback** (registry pointer → prior certified adapter) is the named compensator for a bad deploy; owner = tier maintainer. Fail-open is the per-dispatch compensator. See the no-skip note. |
| 4 | DECOMPOSE_BY_SECRETS | 3 | `serve` (endpoint/hot-swap) · `train` (backpropagate config) · `eval` (harness/metrics) · `wire` (prism slot + role-os gate) — separate boundaries, each one secret family. |
| 5 | UNCERTAINTY_GATED_HUMANS | 2 | A new certified level surfaces a director sign-off before it becomes the active adapter (contrastive: "L(N) beat L(N−1) by X on exam + audit; promote?"). Held at 2 until that sign-off is wired interactive. *(Budgeter: the director already reviews each puzzle rung for principle-correctness — the standing gate; spend is never hand-graded.)* |
| 6 | EXTERNAL_VERIFIER | 3 | The Verifier's base is cross-family (non-Claude) by construction; its own output is still externally checked by prism's family-different + submodularity guards. The eval uses metric-based labels (not a same-family judge). |

**Compensators (no-skip check):** training writes local adapter files (reversible). Serving is local.
Wiring is code on a **feature branch** (reversible via git). The one production-affecting action is
**activating a specialist for live dispatch** — compensator = **version rollback** (pointer swap) +
the standing **fail-open** to Claude; both pre-built in the framework kickoff. **No `npm publish` / `gh
release` / tag push in this kickoff** — shipping a new prism/role-os version that *defaults* to the
specialist is a separate, Mike-gated release decision.

## Rules
- **Repo-first / canonical-ownership:** adapters + datasets are artifacts (not a repo). Code changes:
  prism-verify + role-os → `mcp-tool-shop-org`, on **feature branches**, never main. Confirm remote +
  branch before editing.
- **Rig-safety overrides everything** — watchdog running, 4-bit base, bounded batch×seq, never train+serve
  at once, stop instantly on a memory warning (`wsl --shutdown`).
- **Prove serving before training** (Track A) — don't train an adapter you can't deploy on this rig.
- **Don't re-open the locks** (DoRA/rsLoRA, vLLM-or-llama.cpp, sequential-not-fused, cross-family,
  two-track eval) — they're in the architectural lock. New *evidence* can revise them; preference can't.
- Workflow-standards section mandatory; keep current. Commit only when Mike asks; explicit staging;
  trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## First moves
1. Read the architectural lock + `KICKOFF-preflight-rig-safety.md` + `MEMORY.md` + prism `design/01`.
2. **Decide which specialist goes first** (STATUS): framework is landed ✓; the **budgeter** corpus is the
   built one ✓ (Verifier's is partial). Confirm *its* corpus is manifest-hashed before training it.
3. Start the watchdog. `Get-PSDrive`, `docker run --rm alpine free -m` (~28 GB), confirm `E:\AI-Models`.
4. **Track A FIRST** — prove an adapter can be served on this rig (vLLM in WSL2, else llama.cpp
   per-request) with the base + a stub adapter, before any training run.

## Out of scope
- Lenses L1/L2/L3 (later specialists, same pipeline).
- Fused multiclass / cross-training (v2 research bet).
- A release that makes a specialist the *default* (Mike-gated; this kickoff wires it behind the gate only).
- Ollama serving (vLLM/llama.cpp here; ollama-intern is a later, separate integration).
