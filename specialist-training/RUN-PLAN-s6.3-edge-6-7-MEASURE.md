# RUN-PLAN — S6.3 edge 6→7 MEASUREMENT arms (gating-primary, fine cadence) — v2, post adversarial-verify

**Status:** preregistered 2026-06-13; **revised after a cross-family adversarial verify** (Claude refute panel
read the code + GLM-4.6 / gpt-oss:120b / hermes3 cross-family jury — see `cross-family-cloud-verification`).
**Awaiting the director's GPU go.** Attended only; single lever; threshold sealed BEFORE the foundation arm.
**Edge:** tech-6 `sdxl-style-lora-unet-only` (alpha8) → tech-7 `sdxl-style-lora-te-trigger-reg-gating`.
**Question:** does warming tech-7 from a tech-6 UNet foundation reduce GPU-steps-to-**gating**-cert vs from base?
**Honest prior:** transfer is pair-specific and can be ≤0 (Pruksachatkun 2020); warm-starting an *unconditional*
UNet style may make GATING harder (the TE must learn to suppress style without the trigger) → a measured ≤0 is a
real **confirmed-negative** edge, not a failure, and never flips to a spurious positive.

## v3 (re-verify adjudication, 2026-06-13)
A cross-family re-verify (gpt-oss:120b) flagged that v2 **over-corrected into a low-power test**. Adjudicated
(Claude is the adjudicator — the panel is not auto-trusted): the per-seed **CI-non-overlap gate is dropped** (it
was plan-text only; the shipped producer code never enforced it). At n=3 on GPU the honest output is a
**DIRECTIONAL signal, not a significance claim** (Bowyer 2025) — the honesty is the *visible* `n_receipts=3` on the
edge, gated by consistent-sign + magnitude-floor, with per-seed crossing CIs **reported for transparency, not
gated**. Rejected its "use a common baseline" (would lose the warm-UNet confound control) and "receipts not
independent" (seeds {42,1337,7} give independent init noise); kept its threshold-seed and net-budget points.

## What changed from v1 (the verify closed these false-confirm paths)
1. **Cert metric → paired, step-0-relative.** v1's `siglip_centroid_gap` is an *unpaired* difference — Goodhart-able
   by notrig drifting off-manifold for any reason. v2 uses **`siglip_paired_div`** (same-seed per-subject;
   composition-controlled by construction) measured **relative to each arm's own step-0 baseline** (defeats the
   warm-UNet-fakes-gating + absolute-T-unequal-bar confounds).
2. **Robust crossing, not first-crossing.** A single noise spike on the peak-then-decline curve flips the bracket.
   v2 uses a **sustained crossing** (≥2 consecutive checkpoints ≥ T) + **bootstrap crossing-step CIs** required
   NON-overlapping per seed.
3. **Anti-censoring early checkpoints** (5/10/15) — the foundation arm may cross below step 25.
4. **Deterministic hash-pinned threshold** — no 0.06-vs-0.6×peak disjunction. T = 3 × pooled bootstrap SEM of the
   from-base gating signal, sealed from a from-base run NOT in the measurement arms (no circularity).
5. **n_receipts = 3 mandatory + magnitude floor** — at n=2 the null sign-agreement is a coin flip. The
   producer (record_measurement.py) now ENFORCES n≥3 + consistent sign + floor from the raw per-seed deltas, and
   role-os re-checks (committed 2026-06-13 `467b98d`); a false `confirmed` can no longer be written or rendered.
6. **Quantitative M0** — a strict-load no-op would make the foundation arm byte-identical to from-base and fake a
   "confirmed-neutral." M0 now asserts an exact loaded-key count + a nonzero-delta positive control.
7. **alpha16-variant provenance** — the foundation is alpha16 (scale-matched); tech-6-canonical is alpha8. The
   edge is recorded as `tech-6(alpha16-variant) → tech-7`, never a plain `6→7`.
8. **Net-budget** — the 600 foundation steps are recorded; the curriculum renders net budget, not just from-warm %.

## Locked cert (sealed)
`gating_signal(arm, step) = paired_div(arm, step) − paired_div(arm, step0)`, where
`paired_div = mean over the 10 held-out subjects of [1 − cos(SigLIP2(trig_i), SigLIP2(notrig_i))]`
(SigLIP2-so400m; trig/notrig share the per-subject seed). **steps_to_gating_cert** = first step with a
**sustained** `gating_signal ≥ T` (≥2 consecutive checkpoints). T sealed per M1; hash recorded in every receipt.
Both arms' **step-0 `paired_div` is measured + reported** (own-baseline controls the warm-UNet intercept — the
Goodhart fix; reporting both makes any base-vs-foundation step-0 divergence a visible finding, not a hidden offset).

## Standards compliance
| Standard | Score | Evidence |
|---|---|---|
| PIN_PER_STEP | 3 | Every command/hparam/seed/cert-model pinned; per-run lock logs sd-scripts head sha + base + foundation sha256 + the sealed-T hash. |
| ANDON_AUTHORITY | 3 | M0 quantitative no-op halt + positive control; `_watchdog.ps1` (87C/31.2GB/90%RAM); ≤0/neutral recorded honestly. |
| NAMED_COMPENSATORS | 3 | Only semi-irreversible action = the curriculum write-back: idempotent, `git revert`-able, and now verdict-gated (a false write is impossible by construction). All adapters/grids `rm`-able. |
| DECOMPOSE_BY_SECRETS | 3 | trainer / SigLIP cert (different family) / verdict-gated producer / role-os consumer split on stable seams. |
| UNCERTAINTY_GATED_HUMANS | 3 | Director-gated GPU go; both design forks put contrastively + decided; threshold sealed pre-foundation; small-N uncertainty reported honestly. |
| EXTERNAL_VERIFIER | 3 | Cert = SigLIP (different family, sealed). THIS PLAN was cross-family adversarially verified (Claude code-reading panel + GLM-4.6 + gpt-oss:120b jury); every surfaced blocker is closed above; the honesty enforcement landed in code with a 5/5 end-to-end test. |

## Protocol (pinned; NO GPU until the director's go)
Common: native-Windows sd-scripts, `_watchdog.ps1` up + ×2 heartbeat, `$env:PYTHONUTF8='1'; $env:HF_HOME='E:\AI-Models\hf-cache'`,
base `sd_xl_base_1.0.safetensors`, dataset `dataset_stdstyl`, 1024² bf16 --sdpa --cache_latents --gradient_checkpointing --caption_extension .txt.

**M0 — Foundation + warm-start partial-load (quantitative ANDON):**
1. Train foundation = tech-6 recipe at **alpha16** (scale-matched): `--network_train_unet_only --network_dim 16 --network_alpha 16 --lr 1e-4 AdamW constant --max_train_steps 600 --seed 42 --output_name s63_foundation_unet16`.
2. 1-step warm-start smoke (tech-7 cfg + `--network_weights …s63_foundation_unet16.safetensors --max_train_steps 1`). Parse the `load network weights` log: **ASSERT** loaded UNet lora pairs == the U-Net module count (≈722), missing_keys == exactly the `lora_te*` set, **unexpected_keys == []**. **Positive control:** gen 1 image with the foundation loaded (no training) vs a cold net — they MUST differ numerically. Either assert fails → HALT (a strict-load no-op would fake a neutral result).

**M1 — Seal T (from from-base runs NOT in the measurement arms):**
Run **two reserved from-base seeds (98, 99)**, fine cadence, score `gating_signal`; bootstrap the n=20 per-subject paired divs per checkpoint; `T = 3 × max-over-checkpoints pooled-SEM(gating_signal)`, pooled across both reserved seeds (damps single-seed idiosyncrasy — re-verify point). Write `_s63_measure_threshold.json` (T + its sha256) BEFORE any M2 foundation-arm checkpoint is scored. Never re-tuned.

**M2 — The two arms (single lever = foundation), n_receipts = 3 seeds {42, 1337, 7}:**
- **base arm:** tech-7 from base; **foundation arm:** tech-7 `--network_weights s63_foundation_unet16`. Everything else IDENTICAL (seed, LR, data, cadence, eval).
- Cadence: **5, 10, 15, 25, 50, 75, 100, 125, 150, 175, 200** (early points kill left-censoring). Per checkpoint: gen trig+notrig (same seed) → `gating_signal` relative to that arm's step-0.
- `steps_to_gating_cert` = first **sustained** crossing (≥2 consecutive ≥ T); bootstrap its CI from the per-subject paired divs.

**M3 — Aggregate (small-N HONEST — Bowyer 2025, no CLT):**
`steps_saved_frac_seed = (base_seed − foundation_seed)/base_seed`, matched per seed. Emit ALL THREE per-seed values
to `measurement.json` as `per_seed_steps_saved_frac` + the preregistered `magnitude_floor` (= bootstrap noise floor).
record_measurement.py computes the verdict: **confirmed iff all 3 seeds agree in sign AND |median| ≥ floor** (the
floor is the noise control); else `unverified` (transfer-neutral). Per-seed crossing CIs are **reported, not gated**
(gating on per-seed CI non-overlap at n=3 is a low-power false-negative trap — re-verify adjudication). The edge
carries `n_receipts=3` so the director sees the power: a directional signal, not a significance claim (Bowyer 2025).
**Net budget** (foundation_steps=600 + foundation-arm steps, vs base-arm steps) is reported ALONGSIDE
`steps_saved_frac`, which is the from-warm fraction only.

## Preregistered decision rules (before any number is seen)
- **M0 ANDON:** exact loaded-key count + unexpected==[] + nonzero positive-control, else HALT.
- **`confirmed`** (edge `tech-6(alpha16-variant)→tech-7`): 3/3 consistent sign AND |median| ≥ floor. (n=3 =
  directional, not significance — `n_receipts` is recorded + rendered so the power is visible; per-seed CIs
  reported, not gated.) A consistent ≤0 → **`confirmed-negative`** (warm-start measured NOT to help — a real result).
- **`unverified` stays** on: mixed sign, |median| < floor, n<3, or overlapping crossing CIs.
- No threshold re-tuning, no seed cherry-pick; exam + T hash-pinned; the 600 foundation steps recorded in the net budget.

## measurement.json (matches the verdict-gated producer)
```json
{ "edges": [ { "predecessor": "sdxl-style-lora-unet-only-blackwell-5090",
  "successor": "sdxl-style-lora-te-trigger-reg-gating-blackwell-5090",
  "per_seed_steps_saved_frac": [<seed42>, <seed1337>, <seed7>], "magnitude_floor": <bootstrap floor>,
  "edge_kind": "cheaper", "validated_as": "sequence",
  "note": "alpha16-variant foundation; gating-primary siglip_paired_div step-0-relative; foundation_steps=600" } ] }
```

## Compensators (NO skip)
| Action | Reversible? | Undo (owner: this session) | Post-rollback |
|---|---|---|---|
| Foundation + arm adapters → `output\s63_*` | yes | `Remove-Item E:\AI\training\output\s63_*` | none registered |
| Eval grids → `eval_grid_ckpt*` | yes | `Remove-Item …\eval_grid_ckpt* -Recurse` | none |
| Curriculum write-back (record_measurement.py → curriculum.json) | yes | `git -C E:\AI\readouts revert <commit>` (idempotent, verdict-gated, wave-provenanced) | edge back to `unverified` |
| npm / gh release / push tag / registry promote / exam | none performed | — | — |

## Research grounding
Pruksachatkun 2020 (arXiv:2005.00628, transfer ≤0 is real); Ilharco 2023 (arXiv:2212.04089). Verification stats:
Bowyer 2025 (arXiv:2503.01747, no CLT < ~300); Miller 2024 (arXiv:2411.00640); Yao 2024 τ-bench pass^k
(arXiv:2406.12045); Panickssery 2024 (arXiv:2404.13076) + Verga 2024 PoLL (arXiv:2404.18796) for the cross-family
verify. Cadence + metric locked from the Phase-A pilot; blockers from the cross-family verify (this session).
