# KICKOFF — Specialists S6.3, next edge: an LLM recipe-sequence prereq (e.g. 17→18 / 32→33), attended

Good to see you, bud. The **diffusion edge 6→7 is measured and shipped** (negative transfer — see
`RUN-PLAN-s6.3-edge-6-7.phaseB-result.md`). This session extends S6.3 to an **LLM recipe-sequence
prerequisite edge** — the natural next target the session memory names as 17→18 / 32→33. The 6→7 campaign
proved the *methodology*; this session adapts it to the **WSL LLM path** (a different harness + safety model).

## READ FIRST (load-bearing — do not skip)
- Session memory `role-os-dogfood-swarm-state` (E--AI-role-os) — the full S4–S6 arc, incl. the 6→7 result.
- `gpu-container/specialist-training/RUN-PLAN-s6.3-edge-6-7-MEASURE.md` + `.phaseB-result.md` — the proven
  measurement STRUCTURE to reuse (M0 ANDON → M1 seal-T → M2 two arms × ≥3 seeds → honest write-back).
- `C:/Users/mikey/.claude/projects/F--AI/memory/magnitude-coreadout-rescues-marginal-control.md` — **the key
  lesson: when the control SNR is in doubt, preregister a sealed crossing-FREE magnitude co-readout** alongside
  the primary. The 6→7 primary came back `unverified` (marginal control); the co-readout rescued the finding.
- `cross-family-cloud-verification` (F--AI) — adversarially verify the plan + harness via a LARGE Ollama Cloud
  cross-family seat (glm-4.6:cloud / gpt-oss:120b-cloud, verify the returned `model`) BEFORE any GPU spend.
- `memory/Feedback/feedback_specialist_training_stays_on_wsl.md` — **THE specialist LLM train/serve path is WSL,
  never native Windows. Kill switch = `wsl --shutdown`, NOT the diffusion `_watchdog.ps1`.** Propose deviations, don't act.
- `memory/engine-room.md` — engine-room (`er` CLI) IS in the loop here: it provisions/serves llama-server for the
  LLM eval (the cert scorer). First live `--execute` needs Mike's model path + go.
- `feedback_python_overwatch_watchdog` — the WSL2 guardian (`gpu-container-watchdog --on-breach wsl-shutdown`) is the
  in-VM guard for WSL training; the host-side `_watchdog.ps1` also pkills `python.*train_budgeter` on a breach.

## What's DONE / PROVEN (reuse, don't rebuild)
- **The measurement methodology** (from 6→7): M0 quantitative ANDON (warm-start partial-load verified by key-count +
  a nonzero positive control, so a silent no-op can't fake a neutral) → M1 seal a hash-pinned threshold from RESERVED
  seeds BEFORE the treatment arm → M2 single lever (warm-start present/absent) × ≥3 seeds → primary cert + **a sealed
  crossing-free magnitude co-readout** → honest write-back. Honest by construction: ≤0 / mixed-sign / below-floor / n<3
  stay honest; a false `confirmed` is impossible (record_measurement gates from RAW per-seed deltas).
- **The surfacing is LIVE** (this session, readouts `0ce26ad` + role-os `bd12617`): `gen_curriculum` exports a
  `measured` block for ANY recorded edge; `crew --programs` renders an "S6.3 MEASURED (receipt-backed)" block — so a
  measured-but-`unverified` result is visibly distinct from a never-measured edge. Your write-back will render correctly.
- **The honesty gate is LIVE in code** (role-os `467b98d` + readouts `4d8e136`): do NOT relax it.

## THE OBJECTIVE
1. **SCOPE the edge (no GPU).** From `readouts/training-knowledge/training.db`, identify the target LLM recipe-sequence
   edge(s) — the stated 17→18 / 32→33, OR the most-ready unverified LLM edge (the curriculum already shows e.g.
   *QLoRA-NF4 SFT → DPO*, *QLoRA-SFT → ORPO/SimPO/KTO/GRPO*). Confirm: the pair is a real `predecessor_technique_id`
   link; B is a **trainable** specialist warm-startable from A's adapter/checkpoint; and there is a **cert** (the
   specialist certification exam — pass/score/flip-consistency threshold — NOT a Goodhart-able train metric). Pick ONE edge.
2. **PILOT first (control-first, like Phase A).** There is NO LLM pilot yet. Validate the harness end-to-end on a
   from-base run: train B from base (WSL train path), serve via engine-room llama-server, score the cert. Confirm the
   cert rises out of the noise floor + look at the actual exam outputs (the LLM analog of look-at-images). LOCK the cert
   + cadence from the pilot. Then author the MEASURE plan.
3. **PREREGISTER the MEASURE plan** (reuse the 6→7 template): M0 ANDON for the warm-start adapter load + positive
   control; M1 seal the threshold from reserved seeds; M2 base (B from base) vs warm (B warm-started from A) × ≥3 seeds;
   **a PRIMARY cert AND a sealed crossing-free magnitude co-readout** (mandatory here — the control SNR is unknown and
   the 6→7 lesson is fresh). Single lever = the A warm-start. Honest prior: warm-starting a preference run (DPO/ORPO)
   from an SFT checkpoint may help OR hurt — a measured ≤0 is a real `confirmed-negative`.
4. **Cross-family + Claude-panel adversarially verify** the plan + harness BEFORE GPU (the 6→7 panel caught a blocker +
   3 majors pre-run; do the same).
5. **Run attended** (WSL path; `wsl --shutdown` kill switch; preflight the WSL guardian + engine-room health). Record
   honestly → `record_measurement.py` → `gen_curriculum.py` → `roleos crew --programs` (the measured-unverified surfacing
   now handles every honest path). Write a `phaseB-result` companion doc.

## STANDING CONSTRAINTS (director's law)
- **This is the WSL LLM path** — kill switch `wsl --shutdown`; the specialist-stays-on-WSL rule applies; engine-room
  serves the eval. NOT the diffusion watchdog path (that was 6→7's native-Windows sd-scripts; different rig).
- **Attended GPU only.** Preflight every item FRESH (verify-then-claim). Long runs detached + tee'd + DONE/ABORTED flags
  + a background watcher (≤11-min legs under the task-shell death; re-arm). Background task shells die ~14 min in and
  SIGKILL WSL children — long WSL runs go under tmux (`wsl -e bash -c '… &'` is torn down on relay exit).
- **Single lever per attempt; threshold sealed BEFORE the treatment arm; every gate preregistered; exams/T hash-pinned.**
- **Honest by construction; a sealed magnitude co-readout is now standard when control SNR is in doubt; never fabricate a
  number; `confirmed` requires receipts.** Adjudicate any verifier panel (never auto-trust). LOOK AT the exam outputs.

## OPEN (no GPU; not blocking)
- **More diffusion edges** through the proven `_s63_measure.ps1` harness (each needs its own preregistered cert — 6→7's
  was trigger-gating-specific). Cheap-ish, extends the curriculum.
- **prism-verify** Ollama groundedness live-test (committed local; push/PR is Mike's call).
- **training-knowledge research-wave candidates:** joint-SFT-≠-task-vector (S4d), warm-start-preserves-grokking (S4c),
  CE-vs-flip divergence (S4b), allocator-creep VRAM lesson.
- **S5 serving-confidence:** make the verify shims return the answer-token logprob as `score` (drift perf arm ATC/ECE) +
  the exam-reference capture (GPU-attended) to light the drift arm.

## Orient against the real repo state, scope the edge, pilot, preregister + verify, then on Mike's go run it.
