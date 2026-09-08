# Resume kickoff — oversight fleet + verifier-v2.1 (advisor session, post-compaction)

You are the advisor continuing a long, productive session (2026-06-06). This prompt orients a fresh
context. **Read the memory FIRST, then pick a "Next step" — the task list is the live tracker.**

## Rig (overrides any F:/AI path you read)
Robot rig: Omen 45L, **RTX 5090 (32 GB)** + Core Ultra 9 285K (Xe iGPU "GPU.0" + "AI Boost" NPU) + 64 GB.
Drives **C and E only — no D:/F:/G:**. Every `F:/AI/...` in memory → read as `E:/AI/...`. **AI-Models is on
`E:/AI-Models/`** (NOT D: — the global note is wrong for this rig; verified). WSL2 distro = `Ubuntu`;
training venv `~/bp-env`. Don't tell Mike to rest / take a break (standing etiquette rule).

## Read first (canonical memory: `C:/Users/mikey/.claude/projects/F--AI/memory/`)
- `MEMORY.md` — index (the mission frame + rig topology are at the top).
- `oversight-specialist-mint-strategy.md` — THE strategy + the "Delivered 2026-06-06" section (wedge #1
  conformance watcher, the v2.1 plan, the sidecar, the recipe knob). **Start here.**
- `prism-verify.md` (v1.2.x state + dogfood verdict + CI lesson) · `workflow-standards.md` (the six;
  EXTERNAL_VERIFIER, fail-open) · `research-grounded-advisor-protocol.md` (study-swarm trigger).
- Repo dirs: `E:/AI/prism-verify/`, `E:/AI/role-os/`, `E:/AI/gpu-container/specialist-training/`,
  `E:/AI/npu-sidecar/`.

## Where things stand (verified end of 2026-06-06)
- **SHIPPED + live:** prism-verify **1.2.1** (PyPI+npm) and role-os **2.7.1** (npm), CI green. Docs to the
  front-door doctrine; translations refreshed.
- **Oversight wedge #1 = conformance watcher: minted → certified (0.98 acc / 0.96 flip on a 10-UNSEEN-tool
  exam, GENERALIZES) → wired into role-os's fail-open gate → live-verified 5/5 end-to-end.** Design =
  deterministic schema floor (L1-3) + LLM ceiling (L4 semantic-contract, L5 intent). Weak rung L4
  (0.9/0.8, 2 false-conformants/10). Advisory + fail-open to ABSTAIN (never `conformant`). role-os suite
  green (1347). Manifest `role-os/tools/conformance-dataset/conformance-v1.json`.
- **iGPU embeddings sidecar LIVE on `:8093`** (`E:/AI/npu-sidecar/npu_sidecar_server.py`, GPU.0,
  Qwen3-Embedding-0.6B, dim 1024). Resident — survives until reboot; restart with that script.
- **Verifier-v2 voice fix: attempt #1 did NOT generalize** — v1 (`verifier-14b600-soup`) stays served, the
  prism local-verifier flip stays OFF.
- **Flags all OFF** (`PRISM_LOCAL_VERIFIER_ENDPOINT`, `ROLEOS_BUDGET_CONSULT`, `ROLEOS_CONFORMANCE_CONSULT`).
  GPU idle, no docker serves running (only the iGPU sidecar). Adapters on `E:/AI-Models/adapters/`:
  `verifier-14b600-soup` (v1/rollback), `verifier-14b600-v2-soup` (shelved), `conformance-14b-soup`,
  `budgeter-14b600-soup`.
- **Uncommitted but on-disk (commit only when Mike asks):** the conformance wiring in role-os
  (`tools/conformance-dataset/`, `src/specialist/conformance-consult.mjs` + test, `.role-os/specialists.json`
  edit, manifest), the verifier-v2 dataset in prism, the shims/wire-tests + `train_budgeter.py` knob in
  gpu-container. **Two stashes are Mike's** (prism uv.lock, role-os harvester) — don't touch.

## Next steps (open tasks — confirm with Mike which to run; flips & publishes are Mike-gated)
1. **Verifier-v2.1** (the voice-invariance retry — the one thing that didn't generalize). Rebuild the voice
   corpus BIGGER + far more DIVERSE (real-world names, common nouns, many verbs) + BIDIRECTIONAL
   (active-evidence groups) + a 3-way "two surface-different supporteds vs one reversed" pin +
   role-explicit reasoning. Generators already wired: `prism-verify/specialist/dataset/puzzles.py`
   (`voice_group`) + `corpus_voice.json`. Then audit → train (batch4 OK, short seq) → soup → certify →
   re-dogfood (`gpu-container/specialist-training/dogfood_verifier.py`). Goal: paraphrase-supported ≥3/4
   while keeping direction-reversed 2/2.
2. **Conformance v0.2 + activate/commit.** Lift L4 (more + more-diverse semantic-contract data in
   `role-os/tools/conformance-dataset/corpus_tools.json`). Commit the wiring (suite green). Activate
   internal-first = serve `conformance-14b-soup.gguf` :8094 + `conformance_shim.py` :8001 +
   `ROLEOS_CONFORMANCE_CONSULT=1` (Mike's call).
3. **Sidecar follow-ups.** Add the rerank pipeline (`OpenVINO/bge-reranker-base-int8-ov`, `TextRerankPipeline`)
   + a small judge; wire role-os/repo-knowledge to offload embeddings to `:8093`. (NPU static-shape tuning
   = perf-per-watt follow-up; iGPU works now.)
4. **Dataset publish** — DEFERRED to Mike's HF trusted-publishing setup. Plan ready:
   `prism-verify/specialist/dataset/PUBLISH_PLAN.md` (verifier set → HF, canaried, exam withheld; budgeter HOLD).
5. **Ollama 0.24.0 → 0.30.6** — `winget upgrade Ollama.Ollama` (GPU idle, no model resident).
6. **Housekeeping** — delete merged local branches (prism `feat/specialist-verifier-lens`, role-os
   `feat/budget-production-consult`); the uv.lock churn (Mike's); central marketing-site Sync if
   landing/handbook changed materially.

## Reuse — do NOT re-derive
- **Recipe + scripts:** `gpu-container/specialist-training/RESULTS.md`, `train_verifier.sh` (data-parametric
  via `BUDGETER_DATA`/`BUDGETER_TAG`; now also `BUDGETER_BATCH`/`BUDGETER_ACCUM`, default 4/4),
  `soup_adapters.py`, `certify_verifier.py`/`certify_conformance.py`(.ps1), `serve_verifier.ps1`.
- **Watchdog launch (the only WSL kill switch):** `python -m gpu_container.watchdog run --on-breach
  wsl-shutdown --power-max 100 --temp-max 87 --host-mem-max 80 --interval 10 --peaks-out <f> -- wsl -d
  Ubuntu -- bash -lc '<env> bash /mnt/e/AI/gpu-container/specialist-training/train_verifier.sh'`.
- **Dataset machinery** (per specialist): config/puzzles/corpus/audit/build — contrast groups scored by
  flip-consistency; `audit.py` is the HARD GATE (flip-ready, no torn group, no evidence leak); split
  TOOL/GROUP-atomically so the held-out exam measures generalization.

## Gotchas (load-bearing)
- **Long-sequence datasets OOM at batch4** (98% VRAM): use `BUDGETER_BATCH=2 BUDGETER_ACCUM=8`. Measure seq
  length first (`packing=False` pads to batch-max, not 1024). The verifier (~300 tok) is fine at batch4;
  conformance (~600 tok) needed batch2.
- **Never train + serve concurrently** on the 5090; tear serves down before training. The watchdog clean-kills
  on breach (`wsl --shutdown`) — re-launch restarts WSL.
- **NPU:** OpenVINO sees it, but the embedding model's dynamic shape fails on `intel_npu` even with
  pad_to_max_length → use **GPU.0 (iGPU)**. **IPEX-LLM is archived (2026-01) — use OVMS/OpenVINO.** WSL2
  cannot see the NPU (Windows-host only). System Python is 3.14 (no openvino wheels) → use the 3.12 venv at
  `E:/AI/npu-sidecar/.venv`.
- **uv-Windows trampoline bug:** run via `uv run python -m mypy/pytest/ruff` (not `uv run mypy`).
- **Cross-family gate** (`synth.py`): Ollama on the WINDOWS host; `qwen3.6` is a reasoning model → keep
  `"think": false`.
- **README front-door doctrine** (`feedback_readme_is_a_front_door.md` + the `readme-front-door-lint.py`
  PostToolUse hook): value-prop only; technical detail → CHANGELOG/handbook. **Translations BEFORE publish.**
- **Mike-gated:** commits/pushes, npm/PyPI/HF publishes, and the three consult flips. Don't auto-do them.
- Examples must match the real code surface (read `--help`/the code before documenting a command/flag).

## Standing decisions
Oversight fleet is **internal-first** (polish through use, then exposure). Wedge order:
**conformance ✓ → sycophancy → citation**. The moat is the certified MINTING PROCESS + role-os/prism
native-decorrelation distribution, NOT the weights — embed, don't sell-as-SaaS. v1 verifier stays served
until v2.1 proves the voice fix generalizes.
