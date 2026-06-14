# S6.3 edge 6→7 — Phase B result (the measurement: M0→M3, attended)

**Date:** 2026-06-13, attended (director present), ~6 GPU-hr on the RTX 5090. **Harness:**
`E:\AI\training\_s63_measure.ps1` (orchestrator) + `_s63_measure_score.py` (scorer), native-Windows
sd-scripts, `_watchdog.ps1`-guarded. **Contract:** `RUN-PLAN-s6.3-edge-6-7-MEASURE.md` (v3).
**Commits:** readouts `0ce26ad` + role-os `bd12617` (pushed to main).

## Verdict — NEGATIVE TRANSFER (the honest-hypothesis prediction, confirmed)

Warm-starting tech-7 (`sdxl-style-lora-te-trigger-reg-gating`) from an **unconditional-style UNet
foundation** (tech-6 recipe at alpha16, UNet-only, 600 steps, seed 42) makes trigger-**gating WEAKER,
not cheaper**. The foundation's style is applied regardless of the trigger, so the TE cannot learn to
*suppress* style on the no-trigger prompt — gating fails.

- **Primary cert (steps-to-gating-cert): `unverified`.** All 3 foundation arms **censored** (gating_signal
  went *negative* and never reached T); 2/3 from-base arms gated by step 50. With the foundation arm
  never crossing, "steps saved" is undefined → n=0 → unverified. (Recorded honestly; the edge stays unverified.)
- **Sealed magnitude co-readout (director's call, sealed pre-M2, sha `7a194185`): `foundation-gates-weaker`.**
  n=3, per-seed plateau deltas (found−base) = **−0.099 / −0.042 / −0.070**, median −0.070, clears the
  control-noise floor 0.015 by ~4.5×. **Total separation**: every base plateau is positive (0.02–0.08),
  every foundation plateau is negative. This crossing-free readout rescued the directional finding the
  brittle steps-to-cert could not quantify.

## M0 — quantitative ANDON (PASSED)
- Foundation safetensors: **722 UNet LoRA modules, 0 TE keys** (UNet-only confirmed).
- 1-step warm-start smoke: `_IncompatibleKeys` missing = **792 keys, all `lora_te*`** (= 264 TE modules,
  random-init), unexpected = **[]** (UNet fully loaded). The partial load is real.
- Positive control: SigLIP `1−cos`(base_step0, found_step0) = **0.107** (≫ 0.02 floor) — the foundation
  genuinely changes the image; no silent strict-load no-op.

## M1 — sealed threshold (BEFORE the foundation arm)
- **T = 0.04048** = 3 × max-over-cadence pooled-SEM of the from-base gating signal over the two reserved
  seeds {98, 99} (hash-pinned, write-once). Note: seed 98 gated @150, seed 99 **censored** — the from-base
  control is itself marginal/noisy near T at 200 steps (an important caveat surfaced at this checkpoint).

## M2 — the two arms (single lever = foundation), seeds {42, 1337, 7}, cadence 5..200
| seed | base steps-to-cert | foundation steps-to-cert | base plateau | foundation plateau |
|---|---|---|---|---|
| 42 | **50** (gated) | censored (negative) | +0.079 | −0.021 |
| 1337 | censored (marginal control) | censored (negative) | +0.020 | −0.021 |
| 7 | **50** (gated) | censored (negative) | +0.057 | −0.013 |

Foundation step-0 paired_div 0.105 vs base 0.072 (the styled-UNet intercept — controlled by the
step-0-relative subtraction). Goodhart diagnostic: foundation notrig reverts to base **less** (cos
0.916–0.919) than base (0.939–0.950) — the unconditional style leaks into notrig, which is *why* gating
is weaker.

## Look-at-images (the non-negotiable confirmation — same subject, seed 42, step 200)
- **base / trig** → styled blue-grey illustration ; **base / notrig** → **sepia photograph** (reverts → gating works).
- **foundation / trig** → ink line-drawing ; **foundation / notrig** → **also a line-drawing sketch** (stays styled → gating failed).

## Write-back (director chose "unverified + magnitude note") + surfacing
- Edge recorded `unverified` (n=0) in `training.db` with the full negative-transfer `verifier_note`
  (`record_measurement.py`; copy-tested on a db copy first, real db then written; git-revertable).
- **Surfacing slice shipped:** `gen_curriculum.py` now exports a `measured` block for ANY edge
  `record_measurement` wrote (the verdict lives in the note) → role-os `buildCurriculum` threads it +
  counts `measured_unverified`; `roleos crew --programs` renders a dedicated **"S6.3 MEASURED
  (receipt-backed)"** block. The 6→7 edge now shows `unverified, measured (S6.3 — see below)` — visibly
  distinct from a never-measured edge. role-os suite 1544/1541 (+3 tests, 0 fail).

## Key lesson (new, in memory)
A crossing-based steps-to-cert readout is **brittle when the from-base CONTROL is itself marginal**
(near-T, ~50% censoring). A **sealed crossing-free magnitude co-readout** (mean plateau gating, foundation
vs base) rescues the directional finding at **zero extra GPU cost** — preregister it alongside the primary
whenever the control SNR is in doubt.

## Pre-run verification (no GPU spend wasted)
Both harness scripts were **cross-family + Claude-panel adversarially verified before any GPU run**
(Workflow `wf_5d4b5e82`, 4 lenses): found 1 blocker (filename-timestamp pairing → fixed to **metadata
(subject,seed) keying**), 2 majors (CENSOR sentinel leaking into the saved-frac ratio → **censoring-as-
missing**; floor `a is not b` identity bug → **index-based pairs**), and the M0-gate bypass on resume →
**M0.ANDON.PASSED sentinel**. All fixed + unit-tested pre-run; cloud seat glm-4.6 + gpt-oss:120b model-verified.

## Receipts
`E:\AI\training\_s63m\`: `_s63_measure_aggregate.json` (curves + crossings + CIs + magnitude), sealed
`_s63_measure_threshold.json` (T, sha `9d0d1a8d`) + `_s63_measure_magnitude_spec.json` (sha `7a194185`),
`_s63_measure_runlock.json` (sd-scripts `068bcd7`, base + foundation sha256), `measurement.json`, all
eval grids (the visual receipts — retained). Foundation adapter `output\s63_foundation_unet16.safetensors` retained.
