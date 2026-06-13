# Token Budget Analyst — Training Results

Role OS specialist #1. Trained 2026-06-05 on the Robot rig (RTX 5090, WSL2 + Docker llama.cpp).

## Result

**`budgeter-14b600-soup` is the validated specialist** — a QLoRA adapter on Qwen3-14B, all five
curriculum rungs earned on the held-out, shortcut-resistant exam (n=305):

| rung | acc | flip-consistency |
|------|-----|------------------|
| L1 spot-the-driver | 1.00 | 1.00 |
| L2 which-costs-more | 0.89 | 0.78 |
| L3 fit-or-split | 0.95 | 0.90 |
| L4 starved-or-healthy | 0.86 | 0.71 |
| L5 what-if | 1.00 | 1.00 |
| **overall** | **0.944** | **0.866** |

`flip-consistency` = fraction of contrast groups where EVERY flipped twin is also correct. It is the
load-bearing metric: a shortcutting model scores high accuracy but ~0 flip-consistency.

## The arc (and why each step)

1. **4B baseline → only L5 was real.** v1 scored 0.82–0.92, but a HANS-style audit showed the rungs
   were gamed (always-"B" on L2, always-"starved" on L4). A balanced + contrast-paired curriculum scored
   by flip-consistency exposed the truth: the 4B learned only L5 (dynamics); L1 defaulted, L2 sat at chance.
2. **14B cracked the arithmetic.** Qwen3-14B made L1 perfect immediately. L2 (compare two weighted-token
   totals) is the hardest, most compositional rung.
3. **600 steps grokked L2.** L2 showed a grokking phase-transition signature — seed-dependent at 300 steps.
   300→600 steps crossed it (seed1337 L2 flip 0.11 → 0.82). A study-swarm grounded this (Zhu 2024 critical
   data size, arXiv:2401.10463; Omnigrok, Liu 2022, arXiv:2210.01117).
4. **Model soup killed the residual variance.** At 600 steps the hard rungs (L3/L4) showed run-to-run
   variance (batch4 + checkpointing + 4-bit is not bit-reproducible). A model soup of two seeds — averaged
   the correct way — produced an adapter robust on ALL rungs, beating both parents.

## Certification history (flip-consistency per rung)

| config | L1 | L2 | L3 | L4 | L5 | overall |
|--------|----|----|----|----|----|---------|
| 4B v2 (avg 2 seeds) | 0.10 | 0.01 | 0.47 | 0.43 | 0.96 | 0.32 |
| 14B@300 seed42 | 1.00 | 0.61 | 0.83 | 0.29 | 1.00 | 0.79 |
| 14B@600 seed42 | 1.00 | 0.78 | 0.83 | 0.57 | 1.00 | 0.84 |
| 14B@600 seed1337 | 1.00 | 0.82 | 0.31 | 0.71 | 1.00 | 0.75 |
| **14B@600 soup** | **1.00** | **0.78** | **0.90** | **0.71** | **1.00** | **0.87** |

## Findings (durable — also in session memory)

1. **Flip-consistency is the truth metric.** It caught both the v1 shortcuts and a later weight-decay
   regression that a falling loss curve would have hidden.
2. **rsLoRA serves at scale ~4 on llama.cpp.** `convert_lora_to_gguf` bakes α/r, not α/√r → the adapter
   is served 4× too weak at the default `--lora` scale 1.0 (empty / base-like output). Apply scale 4.0.
3. **More steps, not more weight decay, crossed L2's grokking transition.** Bumping wd 0.01→0.05
   over-regularized (L5 flip 1.0→0.4 — the Goldilocks band). Hold lr/wd at backpropagate defaults.
4. **Model soup must average ΔW = B·A in merged space, then SVD-truncate to r16.** Averaging the A/B
   factors injects cross-terms (the naive soup failed at 0.71). The correct merge beat both seeds.
5. **The watchdog's default `--power-max 95` aborts efficient training** (which legitimately draws ~95%
   power at a safe 73 °C). Train with `--power-max 100`; `--temp-max 87` is the real guard.
6. **batch4 + gradient_checkpointing on 14B = ~94% util, ~18–22 GB VRAM, 4× faster than batch1.**

## Reproduce

- Base: `Qwen/Qwen3-14B` (full bf16, QLoRA 4-bit). rsLoRA r16 α32, dropout 0.05, lr 1e-4, **defaults**
  (wd 0.01, warmup 10). batch4 × grad_accum4 (eff 16), gradient_checkpointing, seq 1024, no-packing,
  600 steps (~6 epochs over 1633 SFT examples).
- `BUDGETER_TAG=14b600 bash train_real.sh` → 2 seeds → `python soup_adapters.py <out> <seed42> <seed1337>`
  → `certify_all.ps1 soup-14b600 budgeter-14b600-soup`.
- Serve: Docker `ghcr.io/ggml-org/llama.cpp:full-cuda`, `-m Qwen3-14B-Q4_K_M.gguf
  --lora-init-without-apply --lora <soup>.gguf`, then POST `/lora-adapters [{"id":0,"scale":4.0}]`.

## Task #5 — DONE: served + wired behind the role-os fail-open gate

- **Served:** `serve_budgeter.ps1` runs llama.cpp (Qwen3-14B-Q4 + `budgeter-14b600-soup` @ --lora
  scale 4) on :8090; `verify_shim.py` bridges the gate's `POST /verify` contract on :8000 (returns
  `{verdict, score, adapter_id, base_model, duration_ms}`; pins its served adapter_id).
- **Registered + promoted:** `node role-os/bin/roleos.mjs specialist register/promote` → active version
  `budgeter-14b600-soup-20260605` (L5) in `role-os/.role-os/specialists.json` (manifest `budgeter-v1.json`).
- **Wired + proven** (`wire_test.mjs` → `dispatchSpecialist`): in-domain dispatch → gate routes to the
  specialist (real budgeter inference, spend ~20.4k); OOD → **fails open to the deterministic baseline**
  `max(context·1.5, 50000)` = 50k (not Claude). The adapter_id pin check passes; an audit receipt
  (`roleos-specialist-receipt/v1`) is written per dispatch. Version-`rollback` is the named compensator.
- Making the specialist the DEFAULT in role-os's production dispatch loop is a separate, Mike-gated
  release decision (not in this kickoff).

Live services (restartable): Docker container `budgeter-serve` (:8090) + `verify_shim.py` (:8000).
Tear down: `docker rm -f budgeter-serve` and `pkill -f verify_shim.py`.

---

# Cross-training (specialists S4) — first live fusion, 2026-06-12

**Candidate:** `budgeter-x-conformance-add` = budgeter-14b600-soup × conformance-14b-soup-v0.2,
task-vector addition at r32/α64 (serve scale 4.0 parity). Tooling: `cross_train.py`
(compatibility readout → merge → report).

**Compatibility readout (the instrument worked):** sign-agreement 0.508 (coin-flip),
mean cosine 0.005, top-20% overlap 0.115 (random rate) — the parents are ORTHOGONAL.
The readout steered the method: TIES trim/mask machinery resolves interference we don't
have and destroys low-rankness (SVD residual 0.479 @ r16, 0.413 @ r32); plain addition
preserves rank ≤ 32 exactly (residual **0.0022** @ r32).

**Preregistered gate (before any exam):** budgeter acc ≥0.85 ∧ flip ≥0.75;
conformance acc ≥0.90 ∧ flip ≥0.85 ∧ false-conformant ≤0.05. Both or no birth.

**Result: FAILED — no registration.** Budgeter 0.738/0.441 (L2, the 600-step grokked
arithmetic rung, collapsed to chance: 0.519/0.111; L1 0.964, L5 1.0 held). Conformance
0.84/0.681, false-conformant 0.097, cost-weighted error 0.297 (parent 0.0405).
**The delicate circuits broke; the robust ones held** — functional interference at full
strength (λ=1), exactly the 4–14B fragile-merging regime the design preregistered for.
Both exams archived (`certify/exams/`, hashes pinned: budgeter `ebc5416a…` — matches the
original registry pin, a true re-exam; conformance `cb6de192…` now properly archived).
Attempt receipts: `certify/x-add-r32-{budgeter,conformance}.json`,
`runs/cross-train-add-r32.json`, plus `certification-attempt` events in role-os's
all-attempts ledger.

**Why no λ-tuning followed:** tuning the merge coefficient against the certification exam
is optimizing the proxy (Goodhart). The literature-correct next protocol is **learned
concatenation (LoRA Soups CAT)** — per-adapter weights calibrated on TRAIN data, certified
ONCE on the untouched exams. The λ=1 endpoint is now a measured bracket for that session.

## S4b — CAT calibration (2026-06-12): second preregistered attempt, FAILED, mechanism found

**Calibration** (`calibrate_cat.py`): 2-param CAT — learnable (λ_A, λ_B) over both frozen
LoRA branches on Qwen3-14B 4-bit, CE on a 50/50 TRAIN interleave (1621 budgeter + 742
conformance rows; 24 probes held out; exams untouched). Converged in ~25 steps to a stable
plateau: **λ_A=0.728, λ_B=0.615** (probe CE 0.764 → 0.296) — gradient descent confirming
the λ=1 over-drive hypothesis. **vector-caliper trajectory captured per checkpoint**
(last-token hidden-state cloud, native entropy/margin): geometry FLAT throughout (effDim
4.6–4.8, spread ~59) — no cloud collapse; baseline committed as
`vector-caliper/baselines/qwen-cat-budgeter-conformance.{json,svg}` (first LLM baseline).

**Single certification shot** (`budgeter-x-conformance-cat`, add-r32 at calibrated λ,
residual 0.0021): **FAILED the preregistered gate.**

| exam | result | parent | gate |
|---|---|---|---|
| budgeter | 0.711 acc / **0.386 flip** (L2 0.546/0.111, L3 0.379/0.069) | 0.944/0.866 | ≥0.85/0.75 ✗ |
| conformance | 0.951 / 0.903, **fc-rate 0.056**, cwe 0.144 | 0.986/0.972/0.014 | fc ≤0.05 ✗ (hair) |

**The finding (the caliper made it legible):** the TRAIN-CE surface and the
flip-consistency surface DISAGREE. Calibration achieved fluent answer reproduction on both
tasks (probe acc 0.92, healthy geometry) while the budgeter's grokked compositional rungs
stayed broken at every tested λ — and conformance nearly healed at λ_B=0.615. The fragile
element is specifically the 600-step grokked arithmetic circuit: it survives NO tested
weight-space superposition with the conformance vector. Probe metrics cannot see circuit
damage; **exams stay sovereign.**

**Conclusion:** weight-space fusion is exhausted for this pair (ties-r16, add-r32 λ=1,
CAT-calibrated λ — all receipted in the all-attempts ledger). The buildable path to a
certified budgeter+conformance specialist is the **joint data-mixed retrain** (S4c): the
proven train pipeline with `BUDGETER_DATA` = concatenated SFT, 2 seeds, soup, certify both
exams. **Untraining note:** for linear weight-space merges, task-vector negation is exact
by construction (subtracting λ_B·ΔW_B recovers λ_A·ΔW_A algebraically) — the experimental
form of untraining only becomes meaningful on jointly-trained adapters → S4c scope.

---

# S4c — the first certified cross-trained specialist (2026-06-12)

**`budgeter-conformance-s4c2-soup` — PASSED the preregistered gate on attempt #4** and is
registered (L5, both roles, full lineage) in role-os. Solo parents remain the active
pointers per-role (they are narrowly stronger per-skill); the cross-trained adapter is the
certified breadth asset.

| exam | S4c-2 soup | gate | parent |
|---|---|---|---|
| budgeter | **0.918 / 0.803** (L2 0.861/0.722) | ≥0.85 / ≥0.75 ✓ | 0.944 / 0.866 |
| conformance | **0.972 / 0.944, fc 0.014** | ≥0.90 / ≥0.85 / ≤0.05 ✓ | 0.986 / 0.972, fc 0.014 |

**The attempt ledger (the story):** #1 add-r32 λ=1 fusion — budgeter flip 0.441, FAIL.
#2 CAT-calibrated fusion — 0.386, FAIL (train-CE and flip-consistency surfaces disagree).
#3 uniform 50/50 joint retrain (1200 steps) — 0.669, FAIL (dilution + upsampled-conformance
memorization pressure; study-swarm wf_3010a824-e2f diagnosed both). #4 **warm-start joint**
(init from the grokked solo soup, conformance + 20% budgeter replay, 800 steps × 2 seeds,
soup) — **PASS**. flip trajectory across attempts: 0.441 → 0.386 → 0.669 → **0.803**.

**What the run proved:**
- **Warm-start preserves grokked circuits through joint training.** L2-train basin proxy:
  source 0.967/0.933 → seed42 0.950/0.900 → seed1337 0.933/0.867 → soup 0.933/0.867. The
  Omnigrok/Grokking-Tickets prediction held exactly (vs re-grokking from scratch, which
  stalled at every tested mixture).
- **20% replay was enough protection** for the warm-started skill while conformance trained
  to within 1.4 points of its dedicated parent — Dong 2023 / Scialom 2022 calibrated right.
- **Mid-run ANDON discipline works**: the inter-seed L2 proxy (TRAIN-split only, exam
  sealed) gated seed 1337's launch; its own reference control caught a harness bug
  (thinking-mode gagging) before any decision was made on bad numbers.
- Run receipts: `RUN-PLAN-s4c2.md` (preregistered design + gate), `data/s4c2_train_sft.jsonl`
  (sha 34c81e44…), `logs/s4c2_seed{42,1337}.log`, `certify/s4c2-soup-{budgeter,conformance}.json`,
  `certify/s4c2-version-{tba,tcc}.json`, caliper lineage baseline
  (`runs/s4c2-lineage-states.json` → vector-caliper). Exams archived + hash-pinned
  (ebc5416a… / cb6de192…).

**Open follow-ups:** untraining experiment on the jointly-trained adapter (subtract the
conformance task vector, re-proxy L2 + conformance — the meaningful form, now that a joint
substrate exists); training-knowledge wave candidates: warm-start-preserves-grokking,
CE-vs-flip divergence, allocator-creep VRAM lesson.
