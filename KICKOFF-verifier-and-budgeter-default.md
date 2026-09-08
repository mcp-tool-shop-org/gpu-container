# Kickoff — Verifier specialist #2 + promote the budgeter to default

Carries over from the budgeter session (2026-06-05): the **first Role OS specialist shipped end-to-end**
— Token Budget Analyst, trained → certified (all 5 rungs, **0.944 acc / 0.866 flip-consistency**) →
served → wired behind role-os's fail-open gate. Full write-up: `gpu-container/specialist-training/RESULTS.md`.

Two follow-ons. **Do the Verifier first** (GPU-heavy); the budgeter-default is a smaller switch-flip.

---

## The two carryovers

1. **Verifier specialist #2** — L4 Groundedness (claim + evidence → supported / unsupported / abstain).
   Dataset is **already hardened + audit-gated** (see below). Build at scale (Phase 2) → train → certify
   → serve → wire into **prism-verify's `local` lens** slot.
2. **Promote the budgeter to default** — it's registered + promoted + gate-routed (proven via
   `wire_test.mjs`). This flips it from "wired behind the gate" to "consulted on every dispatch" in
   role-os's production loop. **Mike-gated** (shipping a default-on version is a release decision).

---

## What the budgeter taught us — apply ALL of it (this is the point of the kickoff)

### Dataset (the verifier dataset already bakes these in)
- **Flip-consistency is the truth metric, NOT accuracy.** Raw accuracy is shortcut-inflated. Score
  contrast GROUPS (every member right). This caught the 4B's shortcuts *and* a later weight-decay
  regression a loss curve would have hidden. *(memory: budgeter-curriculum-flip-consistency)*
- **Contrast groups defeat surface shortcuts.** Same evidence + one swap (supported↔unsupported); same
  claim + varied evidence (supported/unsupported/abstain). Surface-near, verdict-different → the model
  must do the real check, not read length/fluency/topic.
- **Balance** so a majority-guess can't score (audit reports the ceiling).
- **Group-atomic, leak-free split** — a source never spans train/exam; a contrast group is never torn.
- **An audit as a HARD GATE before training** (`audit.py`). This is what catches gaming. Exit 1 = do not train.
- **Fluent corruptions are primary; deterministic ones are a seed only.** Ungrammatical artifacts
  (Phase-1 produced `"a passengers of forty-three"`) are themselves a shortcut signal. Phase 2 (model-gen
  fluent + cross-family gate) is the real data.

### Training (the proven config — do NOT re-derive)
- **Base: Qwen3-14B** (full bf16, QLoRA 4-bit). The 4B sat at chance on hard reasoning; 14B cracked it.
  Groundedness reasoning is at least as hard → 14B.
- **rsLoRA r16 α32, dropout 0.05, lr 1e-4, weight_decay 0.01 (DEFAULT — NOT 0.05; 0.05 over-regularized
  and dropped the computation rungs), warmup 10.**
- **batch 4 × grad_accum 4 (eff 16) + gradient_checkpointing** → ~94% GPU util, ~18–22 GB VRAM, 4× faster
  than batch 1.
- **600 steps (~6 epochs).** The grokking budget. 300 caught the hard rung mid-transition (seed-dependent);
  600 crossed it. The verifier's hardest rung (multi-hop / partial) will likely need the same.
- **Two seeds (42, 1337) + MODEL SOUP** — average ΔW = B·A in MERGED space, then SVD-truncate to r16
  (NEVER the A/B factors — cross-terms; the naive factor-soup failed at 0.71). The soup killed per-run
  variance and beat both parents. Reuse `gpu-container/specialist-training/soup_adapters.py` verbatim.
- **Serve rsLoRA at llama.cpp `--lora` scale 4** (the converter bakes α/r, not α/√r; the default scale 1.0
  serves empty/base output). *(memory: rslora-llamacpp-serve-scale)*

### Rig-safety (non-negotiable)
- **Watchdog with `--power-max 100`** for training — the default 95 aborts efficient training at safe
  temps (it killed a budgeter run at 73 °C / 95% power). `--temp-max 87` is the real guard.
  `gpu-container-watchdog --watch --on-breach wsl-shutdown --host-mem-max 80 --power-max 100`.
  *(memory: watchdog-power-abort-vs-training)*
- **Never train + serve concurrently** on the single 5090. Train → save → free VRAM → serve.
- Train output to ext4 (`~/bp-runs`), copy to E: (drvfs `os.rename` fails). bp-env is pinned
  (torch 2.10.0+cu128, transformers 5.5.0, trl 0.24.0, peft 0.19.1, bnb 0.49.2). 14B HF base is cached.
- Stay on WSL2 the whole way (training + serving). Do not drift to native Windows.

### Serving + wiring
- The `/verify` shim pattern: `gpu-container/specialist-training/verify_shim.py` is the template — it
  bridges the gate/lens HTTP contract to llama.cpp and **pins the served adapter_id** (mismatch fails open).

---

## The Verifier dataset — ALREADY HARDENED (don't rebuild the structure)

`E:\AI\prism-verify\specialist\dataset\`. Validated on the model-free demo: **audit PASS** — 12/12
flip-ready groups, 0 torn, 0 evidence leaked; balance 43/36/21 (sup/unsup/abstain).

| file | role |
|------|------|
| `config.py` | verdicts, 5-rung principles, SYSTEM_PROMPT, cost-asymmetry (false-"supported" 5× worse) |
| `corrupt.py` | Phase-1 deterministic swaps + negate (the SEED only — can be ungrammatical) |
| `puzzles.py` | **contrast-group generators**: `evidence_group` (sup↔unsup, same evidence one swap), `claim_group` (sup/unsup/abstain 3-way, same claim varied evidence — strongest anti-shortcut), `conjunct_group` (L3), `hop_group` (L4); each emits `pair_id` + `contrast` |
| `build_demo.py` | Phase-1 builder + group-atomic split + runs the audit (model-free, runnable now) |
| `synth.py` | **Phase-2 model-gen**: cross-family generate-then-gate (qwen3.6 generates, mistral-small:24b judges; keep only gate-confirmed). Emits the grouped structure. `validate_pair` checks gate agreement first |
| `audit.py` | **the HARD GATE**: balance, flip-readiness, split integrity, evidence leak. Exit 1 = FAIL |

Rungs (= verifier certification levels): L1 trace-the-claim · L2 plausible-but-unsupported (the trap) ·
L3 partial/insufficient · L4 multi-hop · L5 abstain-when-silent.

---

## Track V-A — build the dataset at scale (Phase 2)
1. Free the GPU (no budgeter serve). qwen3.6:latest + mistral-small:24b are present on the rig.
2. **Validate the cross-family gate FIRST** (`python synth.py` → `validate_pair`): need high supported-
   agreement AND high unsupported-agreement. If low, swap the gate family (gemma4:31b / granite4.1:30b /
   aya-expanse:32b are on the rig). *Validate before scaling — the budgeter rule.*
   - **Validated 2026-06-05 (qwen3.6 → mistral-small:24b):** supported-agreement 100%; fluent corruptions
     excellent — entity/relation-direction/temporal/attribution all generated subtle-and-wrong and
     gate-confirmed unsupported. **quantifier/scope confirm weaker** (~50–67% on a micro-sample). The gate
     DISCARDS anything it can't confirm, so kept records are always correct — the cost is YIELD, not
     quality. So: run `validate_pair` on n≥20 for real per-error-type rates, **budget ~1.5–2× generation
     attempts**, and consider down-weighting quantifier/scope or trying a stricter gate (granite4.1/gemma4)
     for those types. NOTE: Ollama is on the WINDOWS host — run synth.py on Windows, or set
     `OLLAMA_HOST=http://<win-host-ip>:11434` from WSL (the resolv.conf nameserver IP).
3. Harvest evidence (real studio facts / prism design text / a clean factual corpus). Run Phase 2 at scale
   (**all-generate then all-gate** to avoid per-record model swaps). Combine with Phase-1
   `claim_group`/`hop_group`/`conjunct_group` for the abstain / multi-hop / L3 structure.
4. Group-atomic split (by source fact). Build the SFT (`to_sft`).
5. **Run `audit.py` — it MUST PASS** (flip-ready all groups, 0 torn, 0 leak, balance reasonable). The gate.
   Do not train on a failing dataset.
6. Director eyeballs a handful per rung for principle-correctness (the gold is by-construction; never hand-graded).

## Track V-B — train (the budgeter recipe, verbatim)
`train_budgeter.py` is model/data-parametric — point it at the verifier SFT. Qwen3-14B, rsLoRA r16 α32,
lr 1e-4, **wd 0.01 default**, batch4 + grad_accum4 + checkpointing, 600 steps, seeds 42 & 1337, then
`soup_adapters.py`. Watchdog `--power-max 100`. Output ext4 → copy to E:.

## Track V-C — certify (flip-consistency)
Build a held-out, group-atomic verifier exam. Reuse the `certify.py` pattern: per-rung accuracy +
flip-consistency + bootstrap CI, served @ scale 4. **Cost-asymmetric: weight a false-"supported" 5×**
(shipping a hallucination ≫ wasting a generalist call). A rung is earned when strong + replicates across
the 2 seeds, or the soup is robust on all rungs (the budgeter's soup beat both seeds — expect the same).

## Track V-D — serve + wire into prism-verify's `local` lens
- Serve the soup (Docker llama.cpp, 14B Q4 + adapter @ **scale 4**) + a `/verify` shim adapted to the
  groundedness contract: input `{evidence, claim}` → `{verdict, score, adapter_id, base_model, duration_ms}`.
- Wire into **prism-verify's `local` lens slot** (NOT role-os's dispatcher gate — that's the budgeter's).
  Point prism's local L4 backend at the endpoint.
- **Fail open** on low-confidence / OOD to prism's other lenses / the API lens (the verifier's fallback is
  the generalist verification path, not a deterministic baseline). Confirm prism's lens-fallback hook.

## Track B-DEFAULT — promote the budgeter to default in role-os
- Re-serve: `serve_budgeter.ps1` + `verify_shim.py` (registry persists at `role-os/.role-os/specialists.json`).
- Wire `dispatchSpecialist` into role-os's **production dispatch loop** (consulted before each dispatch),
  with the deterministic `max(context·1.5, 50000)` as the fail-open fallback. Pattern proven in `wire_test.mjs`.
- **Mike-gated:** wiring the production consult is this kickoff; *flipping the default-on* ships when Mike says.
- Named compensator: `roleos specialist rollback <role> <prior-version>` (pure pointer swap, no retrain).

---

## Standards compliance (the six)

| # | standard | score | evidence |
|---|----------|-------|----------|
| 1 | PIN_PER_STEP | 2 | Base model, hyperparams, model names, serve-scale 4, and bp-env are all pinned in this doc + the scripts; per-record gen/gate prompts are fixed in synth.py. (Not byte-replayable: local-model sampling varies — TEMP_GATE=0 mitigates the judge.) |
| 2 | ANDON_AUTHORITY | 3 | `audit.py` hard-fails a gamed/leaky dataset (exit 1) before any training; the cross-family gate discards ambiguous records; the certification gate refuses a non-replicating adapter. |
| 3 | NAMED_COMPENSATORS | 3 | Budgeter-default: `roleos specialist rollback` (pointer swap). Adapters/datasets are tagged + immutable; serve teardown documented (`docker rm -f` / `pkill`). No irreversible publish in this kickoff. |
| 4 | DECOMPOSE_BY_SECRETS | 3 | dataset (V-A) · train (V-B) · certify (V-C) · serve+wire (V-D) · budgeter-default (B-DEFAULT) are separate boundaries; verifier (prism lens) and budgeter (role-os gate) are distinct integration secrets. |
| 5 | UNCERTAINTY_GATED_HUMANS | 2 | Director eyeballs the rung samples (principle-correctness); the default-flip is explicitly Mike-gated. Held at 2 until the eyeball is a wired interactive checkpoint. |
| 6 | EXTERNAL_VERIFIER | 3 | **Exemplary** — the dataset's cross-family generate-then-gate IS the external-verifier pattern: a different model family (Mistral) judges the generator's (Qwen) output with the generator's reasoning hidden. Certification uses flip-consistency on a held-out exam. The budgeter gate's shadow-probe compares against a different judge. |

## Definition of done
- **Verifier:** dataset `audit.py` PASS → soup trained (14B, 600 steps, 2 seeds) → all rungs earned
  (flip-consistency, cost-asymmetric) → served @ scale 4 → wired into prism's `local` lens with fail-open
  → director eyeball.
- **Budgeter-default:** production consult wired + fail-open proven; the default-on flip staged for Mike's
  release call.
