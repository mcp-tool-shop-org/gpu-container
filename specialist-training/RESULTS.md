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
