# KICKOFF — Specialists S6.3 GPU measurement campaign (edge 6→7, attended)

Good to see you, bud. This session **runs the GPU measurement** that turns the 6→7 prerequisite edge from
`unverified` into a receipted `confirmed` / `confirmed-negative`. The design is fully preregistered + cross-family
adversarially verified; **the harness scaffolding from the Phase-A pilot exists**; this is the attended GPU execution.

## READ FIRST (load-bearing — do not skip)
- `gpu-container/specialist-training/RUN-PLAN-s6.3-edge-6-7-MEASURE.md` — **v3, the preregistered measurement** (M0–M3,
  sealed cert, decision rules, compensators). This is the contract; do not deviate without a new preregistration.
- `gpu-container/specialist-training/RUN-PLAN-s6.3-edge-6-7.phaseA-result.md` — what Phase A validated + the readout lock.
- `C:/Users/mikey/.claude/projects/F--AI/memory/MEMORY.md` (canonical index) → open `cross-family-cloud-verification`
  (the EXTERNAL_VERIFIER seat: a LARGE Ollama Cloud model via `ollama_chat`, verify the returned `model`), the
  rig-awareness block (drives C+E only; F:/AI → E:/AI), and `feedback_python_overwatch_watchdog`.
- Session memory `role-os-dogfood-swarm-state` (E--AI-role-os) — the full S4–S6 arc.

## What's DONE (do not rebuild)
- **Phase A pilot** (control-first): harness validated end-to-end (train → checkpoint → dual gen → SigLIP score;
  images confirm the numbers; gating visually unambiguous). Readout **LOCKED gating-primary**, cert =
  **`siglip_paired_div`, step-0-relative** (a bake-off on the pilot images + the adversarial verify chose the *paired*
  metric over the unpaired centroid-gap to defeat a Goodhart path). Gating peaks ~step 150–200 then declines.
- **Honesty enforcement is LIVE in code** (role-os `467b98d` consumer + readouts `4d8e136` producer): a false
  `confirmed` can no longer be written or rendered. record_measurement.py computes the verdict from the RAW per-seed
  deltas (n≥3 + consistent sign + magnitude floor); role-os re-checks; tested 5/5 end-to-end. **Do not relax this gate.**
- Harness on disk in `E:\AI\training`: `_s63_pilot.ps1` (pilot orchestrator — the TEMPLATE), `_s63_eval_pilot.py`,
  `_s63_gating_metrics.py` (SigLIP bake-off), `_eval_prompts.txt` (trig) / `_eval_prompts_notrig.txt` (no-trigger),
  `_watchdog.ps1`. Native-Windows sd-scripts venv: `E:\AI\training\sd-scripts\.venv\Scripts\python.exe`.

## THE OBJECTIVE — run M0 → M3 (per the MEASURE plan v3)
1. **M0 — foundation + warm-start partial-load (quantitative ANDON).** Train `s63_foundation_unet16` (tech-6 recipe at
   **alpha16**, UNet-only, 600 steps, seed 42). Then a 1-step tech-7 `--network_weights` smoke: ASSERT loaded UNet lora
   pairs == the U-Net module count (≈722), missing_keys == exactly `lora_te*`, **unexpected_keys == []**; PLUS a
   positive control (foundation-loaded step-0 gen MUST differ numerically from a cold net). Either fails → HALT (a
   silent strict-load no-op would make the foundation arm == from-base and fake a "confirmed-neutral").
2. **M1 — seal T.** Run **two reserved from-base seeds (98, 99)**, fine cadence, score `gating_signal`; `T = 3 ×
   max-checkpoint pooled-SEM`. Write `_s63_measure_threshold.json` (T + sha256) BEFORE any foundation-arm scoring.
3. **M2 — the two arms (single lever = foundation), seeds {42, 1337, 7}.** base = tech-7 from base; foundation =
   tech-7 `--network_weights s63_foundation_unet16`. Cadence **5,10,15,25,50,75,100,125,150,175,200**. Per checkpoint:
   gen trig+notrig (same seed) → `gating_signal = paired_div(step) − paired_div(step0)` for that arm.
   `steps_to_gating_cert` = first **sustained** crossing (≥2 consecutive ≥ T). Report both arms' step-0 paired_div.
4. **M3 — verdict + write-back.** `per_seed_steps_saved_frac = [seed42, seed1337, seed7]`, `magnitude_floor` =
   the bootstrap noise floor. Build `measurement.json` (shape in `record_measurement.py` header) →
   `python scripts/record_measurement.py <file>` → `python scripts/gen_curriculum.py` → `roleos crew --programs`
   shows the edge `confirmed` / `confirmed-negative` / stays `unverified` (all paths honest). The edge renders as
   `tech-6(alpha16-variant)→tech-7` (provenance — it is NOT plain 6→7). Record `foundation_steps=600` (net budget).

**You must WRITE two new harness scripts** (the pilot ones are templates, not reusable as-is): `_s63_measure.ps1`
(foundation + 2 arms × 3 seeds, the fine cadence, the warm-start `--network_weights`) and `_s63_measure_score.py`
(paired_div step-0-relative `gating_signal`, the sustained crossing + a bootstrap crossing CI for reporting). The
pilot's `_s63_pilot.ps1` / `_s63_eval_pilot.py` / `_s63_gating_metrics.py` show every primitive (gen command, SigLIP
embed, paired_div, the env). Reuse them.

## STANDING CONSTRAINTS (director's law — unchanged)
- **Attended GPU only.** Preflight before ANY run, each item observed FRESH: launch `_watchdog.ps1` via pwsh (Start-Process
  detached — it survives the ~14-min task-shell teardown), verify HEARTBEAT age <10s then again ~15s later; `powercfg
  /change standby-timeout-ac 0`; confirm ComfyUI is not holding VRAM (`nvidia-smi`); long runs detached + tee'd log +
  DONE/ABORTED flags + a background watcher (poll the flags, ≤11-min legs to stay under the task-shell death; re-arm).
- **This is the NATIVE-WINDOWS diffusion path** (sd-scripts), NOT the WSL LLM path — its kill switch is `_watchdog.ps1`,
  not `wsl --shutdown` (the watchdog already guards `sd-scripts\.venv\Scripts\python.exe`). **engine-room is NOT in the
  loop here** — it serves llama-server (the LLM edges 17→18/32→33); the diffusion cert is the local SigLIP scorer.
- **Single lever per attempt; sealed threshold BEFORE the foundation arm; every gate preregistered; exams/T hash-pinned.**
- **`$env:PYTHONUTF8='1'; $env:HF_HOME='E:\AI-Models\hf-cache'`** always. `--sdpa` NEVER xformers (Blackwell).
  `--caption_extension .txt` (kohya silently ignores .txt otherwise). Run the A0-style 1-step smoke first (caption read
  16/16, naming, peak VRAM via the watchdog csv) before any long detached run — it caught real bugs in Phase A.
- **Honest by construction:** a measured ≤0 is a real `confirmed-negative`, not a failure; mixed-sign / below-floor /
  n<3 stay `unverified`. n=3 is a DIRECTIONAL signal, not significance — the visible `n_receipts` carries the honesty.
  Never fabricate a number; `confirmed` requires receipts.

## OPEN (no GPU; not blocking)
- **prism-verify** Ollama groundedness live-test (committed local only) — push/PR is Mike's call.
- **training-knowledge research-wave candidates:** joint-SFT-≠-task-vector-addition (S4d), warm-start-preserves-grokking
  (S4c), CE-vs-flip divergence (S4b), allocator-creep VRAM lesson.
- **S5 serving-confidence:** make the verify shims return the answer-token logprob as `score` so the drift perf arm
  (ATC/ECE) goes live; + the exam-reference capture (GPU-attended) to light the drift arm.

## Orient against the real repo state, then preflight, then on Mike's go run M0.
