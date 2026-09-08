# RUN-PLAN — S6.3 edge 6→7 (SDXL UNet-only → +TE/trigger/reg-gating) · Phase A: control-first

**Status:** preregistered 2026-06-13 BEFORE any eval; director present, go given; design choice = **"control-first, then lock"**.
**Edge:** technique 6 `sdxl-style-lora-unet-only-blackwell-5090` → technique 7 `sdxl-style-lora-te-trigger-reg-gating-blackwell-5090`. KB encodes it: `predecessor_technique_id=6, stage_order=2`.
**Campaign question:** does having the predecessor's capability present reduce GPU-steps-to-cert for the successor? `steps_saved_frac = (base − foundation)/base` over `n_receipts` (write-back schema in `readouts/training-knowledge/scripts/record_measurement.py`). Honest prior: transfer is pair-specific and can be ≤0 (Pruksachatkun 2020) — a measured non-positive delta is a real result.
**Phase A question (THIS plan):** which readout — **style-fidelity** (CLIP-sim-to-centroid) or **trigger-gating** (with−without-trigger gap) — rises cleanly out of the eval noise floor on real rig data? **Lock the measurement readout + sealed threshold AFTER Phase A. No `confirmed` write in Phase A** — the pilot is harness validation.

## Why control-first (director's call) + two facts that shaped it
- **Noise floor:** prior SDXL waves found style-LoRA fidelity *clusters within the eval noise floor* once past undertraining (SEM ~0.017; KICKOFF-finish-measuring.md). A naive "steps-to-cert" crossing is noisy unless the threshold is sealed against a real curve — hence: see the curve first.
- **Engine de-conflation:** 6→7 is a **diffusion** edge. Training = native-Windows **kohya/sd-scripts** (a batch trainer, not a launchable server); cert = a **CLIP-sim** scorer (`_eval_ckpt.py`/`_s63_eval_pilot.py`). **engine-room is NOT in the loop** (its live `--execute` serves llama-server, for the *LLM* edges 17→18/32→33). No first-live-`--execute` risk here.
- **Native Windows is the blessed diffusion path, not a 197 deviation:** `feedback_specialist_training_stays_on_wsl` governs the **LLM** specialist adapters (WSL `train_budgeter`, kill = `wsl --shutdown`). The diffusion harness is native-Windows by design, with its own kill switch = `_watchdog.ps1` (`feedback_python_overwatch_watchdog`). This run uses that established path.
- **Foundation must be trained fresh:** on-disk SDXL adapters (`stdstyl_te_lora_v*`) are wave-4 TE-on/alpha16 configs, not the tech-6 UNet-only/alpha8 floor. The measurement phase trains its own alpha-matched foundation. (Phase A does not need it.)

## Standards compliance
| Standard | Score | Evidence |
|---|---|---|
| PIN_PER_STEP | 2 | Every command pinned below (model, seed=42, dim/alpha/LR/steps/cadence, scorer model `openai/clip-vit-base-patch32`); held-out prompts frozen in `_eval_prompts{,_notrig}.txt`. To 3: emit a per-run lock with the resolved sd-scripts commit + base-model sha256. |
| ANDON_AUTHORITY | 3 | A0 smoke is the literal first-live-path ANDON test (caption-read 16/16, naming, VRAM); `_watchdog.ps1` aborts on temp≥87C / VRAM≥31200MiB / RAM≥90% ×3; a non-resolving readout is reported honestly, not forced. |
| NAMED_COMPENSATORS | 3 | Phase A has NO irreversible external calls (see compensators table) — every artifact is `rm`-able; nothing registers/publishes/pushes. Watchdog clean-stop = create `_watchdog_STOP`. |
| DECOMPOSE_BY_SECRETS | 3 | Harness scripts live with the harness (`E:\AI\training`); plan + eventual `measurement.json` + receipts live with the campaign (`gpu-container/specialist-training`); scorer is independent of the trainer; gating hidden behind the dual-prompt-file seam. |
| UNCERTAINTY_GATED_HUMANS | 3 | The readout fork was put to the director contrastively BEFORE authoring (chose control-first); attended run; the readout + threshold LOCK is a director gate after the curves are seen; `confirmed` requires receipts. |
| EXTERNAL_VERIFIER | 2 | Cert scorer (CLIP ViT-B/32) is a different model family from the SDXL generator; reference = the fixed 16-img stdstyl centroid + a no-LoRA base floor. To 3: re-check a locked delta on an independent eval seed before writing `confirmed`. |

## Harness (all local — pinned)
- **Trainer:** `E:\AI\training\sd-scripts\.venv\Scripts\python.exe` (torch 2.12.0+cu130), `sdxl_train_network.py` / `sdxl_gen_img.py`. `--sdpa` (NEVER xformers on Blackwell). `--caption_extension .txt` (kohya silently ignores `.txt` otherwise → trains the bare class token).
- **Base:** `E:\AI-Models\ComfyUI_windows_portable\ComfyUI\models\checkpoints\sd_xl_base_1.0.safetensors`.
- **Dataset:** `dataset_stdstyl\10_neutralset` (16 img+cap, trigger `stdstyl`) ✓; reg `reg_stdstyl\10_object` (16) ✓ (gating, measurement phase).
- **Cert scorer:** `_s63_eval_pilot.py` — CLIP ViT-B/32 sim to the stdstyl cyanotype centroid + CMMD; `HF_HOME=E:\AI-Models\hf-cache`.
- **Held-out:** `_eval_prompts.txt` (trigger) / `_eval_prompts_notrig.txt` (no trigger) — 10 subjects × 2 seeds = 20, none overlap the training set.

## Phase A design (single config; NO transfer lever yet — harness validation)
- **A0 smoke** (foreground, ~2 min): a 1-step tech-7-from-base train. ANDON gates below.
- **A1 pilot** (detached via `Start-Process`, ~45 min, `_s63_pilot.ps1`): base floor (no-LoRA, trig+notrig) → tech-7-from-base 600 steps `--save_every_n_steps 100` constant-LR grad-ckpt → per-checkpoint dual eval grids.
- **A2 score** (`_s63_eval_pilot.py`): fidelity & gating curves vs step → `_s63_pilot_eval.json` + look-at-images (LOOK-AT-IMAGES rule — open a contact sheet, don't eyeball-from-numbers).
- **A3 lock**: curves + looked-at images → director; lock readout + sealed threshold; preregister the measurement arms as `RUN-PLAN-s6.3-edge-6-7-MEASURE.md` (the single lever there = foundation present vs absent, alpha-matched warm-start vs base).

## Preregistered decision rules (before any number is seen)
- **A0 ANDON (halt the pilot if any fail):** train log prints `caption ... 16/16` (not "No caption file found"); exit 0; a checkpoint `.safetensors` is written (note its naming); peak VRAM during the step (from `_watchdog_log.csv`) **< 28000 MiB**.
- **Fidelity readout VIABLE iff:** trained-step `fidelity_trig` exceeds the base-floor `fidelity_trig` by **≥ 3×SEM** AND rises ~monotonically across steps (clean signal out of noise).
- **Gating readout VIABLE iff:** best-checkpoint `gating_gap` **≥ 3×SEM** AND base-floor `gating_gap` ≈ 0 (style appears only with the trigger).
- **Lock rule:** BOTH viable → prefer **gating** (the true new-capability prerequisite test); only fidelity → use fidelity with the stated shared-UNet-component limitation; NEITHER → report the edge as not-cleanly-measurable-by-CLIP-proxy (honest), propose an alternate cert (e.g. SigLIP2 `_p2_gate_siglip.py`, or steps-to-asymptote-fraction) to the director.
- **Pilot numbers do NOT write the edge.** No `confirmed` from Phase A.

## Commands (pinned)
```powershell
# Preflight (each observed fresh): watchdog HEARTBEAT age <10s ×2 (15s apart); powercfg standby=0; ComfyUI NOT holding VRAM.
# Watchdog launch (detached, survives task-shell death):
Start-Process pwsh -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','E:\AI\training\_watchdog.ps1' `
  -WindowStyle Hidden -RedirectStandardOutput E:\AI\training\_wd_stdout.txt -RedirectStandardError E:\AI\training\_wd_stderr.txt

# A0 smoke (FOREGROUND, ~2 min):
$env:PYTHONUTF8='1'; $env:HF_HOME='E:\AI-Models\hf-cache'; Set-Location E:\AI\training\sd-scripts
E:\AI\training\sd-scripts\.venv\Scripts\python.exe sdxl_train_network.py `
  --pretrained_model_name_or_path E:\AI-Models\ComfyUI_windows_portable\ComfyUI\models\checkpoints\sd_xl_base_1.0.safetensors `
  --train_data_dir E:\AI\training\dataset_stdstyl --output_dir E:\AI\training\output --output_name s63_smoke `
  --network_module networks.lora --network_dim 16 --network_alpha 16 `
  --unet_lr 1e-4 --text_encoder_lr 1e-4 --learning_rate 1e-4 --optimizer_type AdamW --lr_scheduler constant `
  --max_train_steps 1 --save_every_n_steps 1 --mixed_precision bf16 --save_precision bf16 --sdpa --cache_latents `
  --gradient_checkpointing --resolution 1024,1024 --train_batch_size 1 --caption_extension .txt `
  --save_model_as safetensors --seed 42 --max_data_loader_n_workers 0
# inspect: caption read count in the log; Get-ChildItem E:\AI\training\output\s63_smoke* ; tail _watchdog_log.csv for peak VRAM.

# A1 pilot (DETACHED, ~45 min):
Start-Process pwsh -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','E:\AI\training\_s63_pilot.ps1' `
  -WindowStyle Hidden -RedirectStandardOutput E:\AI\training\_s63_pilot.out -RedirectStandardError E:\AI\training\_s63_pilot.err
# monitor: _s63_pilot.log (step markers) + _s63_pilot.DONE / _s63_pilot.ABORTED + _watchdog_log.csv (range-crossing, never exact-match).

# A2 score:
$env:PYTHONUTF8='1'; $env:HF_HOME='E:\AI-Models\hf-cache'
E:\AI\training\sd-scripts\.venv\Scripts\python.exe E:\AI\training\_s63_eval_pilot.py
```

## Compensators (NO skip — Phase A asserted to have no irreversible external calls)
| Action | Reversible? | Undo (owner: this session) | Post-rollback state |
|---|---|---|---|
| Train pilot adapters → `output\s63_*` | yes | `Remove-Item E:\AI\training\output\s63_*` | no adapters; nothing registered |
| Gen eval grids → `eval_grid_ckpt*` | yes | `Remove-Item E:\AI\training\eval_grid_ckpt*,...notrig* -Recurse` | no grids |
| Launch watchdog (PID) | yes | `Set-Content E:\AI\training\_watchdog_STOP ''` (clean stop) | watchdog exits, heartbeat removed |
| Registry / npm / git push / exam | **none performed** | — | — |

No `gh release`, no `npm publish`, no `git push`, no exam, no registry write, no curriculum write occur in Phase A. The write-back (`record_measurement.py` → `curriculum.json`) happens ONLY after the measurement phase locks and is itself `git revert`-able + idempotent.

## Receipts
- `_s63_pilot_train.log`, `_s63_pilot.log`, `eval_grid_ckpt*` / `eval_grid_ckpt_notrig*` grids, `_s63_pilot_eval.json`, `_watchdog_log.csv` (the health receipt) — all under `E:\AI\training`.
- This RUN-PLAN + a `RUN-PLAN-s6.3-edge-6-7.phaseA-result.md` (the lock decision) under `gpu-container/specialist-training`.
- role-os all-attempts ledger: event kind `measurement-pilot` (role context = the diffusion training-programs edge), NOT `certification-attempt` — Phase A registers nothing.

## Research grounding (inherited)
Pruksachatkun 2020 (transfer pair-specific, can be ≤0); the KICKOFF-finish-measuring noise-floor finding; tech-6/7 DB receipts (verified=1, with the noted citation caveats on tech-7's DreamBooth-PPL analogy). No new study-swarm — the question + method were preregistered in `design/s6.3-measurement-plan.md` (study-swarm wf_9b6208e9-b97).
