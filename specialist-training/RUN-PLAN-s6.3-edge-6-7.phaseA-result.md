# S6.3 edge 6→7 — Phase A result (harness validated; readout LOCKED gating-primary)

**Date:** 2026-06-13, attended (director present). **Pilot:** `_s63_pilot.ps1` (detached, native-Windows
sd-scripts, watchdog-guarded). Clean run 13:15→13:48, no abort/trip, peak VRAM 19.4 GB / 73 °C.
Receipts: `E:\AI\training\{_s63_pilot.log,_s63_pilot_train.log,_s63_pilot_eval.json,_s63_gating_metrics.json}`
+ `eval_grid_ckpt*` / `eval_grid_ckpt_notrig*`. **No edge written — Phase A is harness validation.**

## Harness validated end-to-end
train → checkpoint (every 100) → dual gen (trig + notrig, `sdxl_gen_img.py`) → score. **Look-at-images
confirms the CLIP numbers** (subject: sailing ship, seed 42):
- step 0 (no LoRA): soft desaturated **photo** — unstyled (fid 0.652).
- step 100 (trigger): vintage **textured illustration** — style emerged (fid 0.716).
- step 600 (trigger): clean **ink/pencil line-drawing** on paper — strong style (fid 0.714).
- step 600 (NO trigger): **sepia photograph** — reverts to near-base → **gating works, visually obvious**.

## Curves (n=20 held-out/step)
- **Fidelity (CLIP sim-to-centroid):** base 0.652 → trained ~0.71–0.75. Base→trained +0.094 (~6.8×SEM),
  but **saturates by step 100 then plateaus in noise** (range 0.709–0.746 ≈ 2.5×SEM). The style (shared
  UNet component) is acquired fast; the 100-step cadence is blind to the 0–100 rise where transfer lives.
- **Gating (winner = `siglip_centroid_gap`):** see bake-off below. Base ≈ 0, **peaks +0.106 @ step 200,
  then declines** (overtraining bleeds style into the no-trigger output — matches the tech-7 recipe note).

## Gating-metric bake-off (`_s63_gating_metrics.py`, re-score of pilot images, no new GPU)
| metric | base floor | best (trained) | separation |
|---|---|---|---|
| clip_centroid_gap | −0.006 | +0.075 @400 | 2.8×SEM (marginal) |
| clip_paired_div | +0.081 | +0.175 @200 | 3.6×SEM (high base — trigger perturbs untrained) |
| **siglip_centroid_gap** | **−0.022** | **+0.106 @200** | **7.6×SEM ★ LOCKED** |
| siglip_paired_div | +0.072 | +0.179 @200 | 5.7×SEM (high base) |

## Lock decision (director, 2026-06-13): GATING-PRIMARY, fine cadence
- **Cert metric (sealed):** `siglip_centroid_gap` = SigLIP2-so400m (`google/siglip2-so400m-patch16-512`)
  mean sim(trig-gen, cyanotype-centroid) − mean sim(notrig-gen, centroid), n=20 held-out subjects.
- **Why:** measures the capability tech-7 actually ADDS (gating), at 7.6×SEM with a ~0 base floor —
  the truest 6→7 prerequisite test, now lifted out of CLIP's noise.
- **Readout:** steps-to-gating-cert = first checkpoint where `siglip_centroid_gap` ≥ a sealed threshold
  on the RISING side (peak-then-decline doesn't affect first-crossing). Threshold candidate: 0.06
  (> 3×SEM≈0.04, comfortably below the +0.106 peak) — finalize in the MEASURE plan from the from-base curve.
- **Cadence:** every ~20 steps to ~200–240 (the action is 0–200; 100-step cadence was blind to it).

## Carried to the measurement arms (`RUN-PLAN-s6.3-edge-6-7-MEASURE.md`, to author)
- **Single lever:** foundation present vs absent. Foundation = **alpha-matched** (alpha16) UNet-only
  tech-6 adapter on stdstyl, warm-started into tech-7 via `--network_weights` (alpha-match avoids the
  alpha8→alpha16 2× scale distortion). **Verify the partial load** (UNet loads, TE random-init) with a
  1-step warm-start smoke that prints missing/unexpected keys — BEFORE the arms.
- **Honest hypothesis (preregister):** warm-starting the UNet pre-loads style applied UNCONDITIONALLY,
  so the TE must learn to SUPPRESS style without the trigger → foundation may make gating HARDER
  (negative steps_saved_frac). A measured ≤0 is a real Pruksachatkun-style result, not a failure.
- **steps_saved_frac** = (base_steps_to_gating_cert − foundation_steps_to_gating_cert) / base, n_receipts seeds.
