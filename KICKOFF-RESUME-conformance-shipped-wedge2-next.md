# Resume kickoff — oversight fleet: wedge #1 SHIPPED + live, wedge #2 next (advisor session)

You are the advisor continuing a long, productive run. Conformance wedge #1 is **shipped to main and
live-wired**; this prompt orients a fresh context to continue. **Read the memory FIRST, then pick a
"Next step" with Mike — the task list is the live tracker.** Authored 2026-06-07 (work below landed
2026-06-06).

## Rig (overrides any F:/AI path you read)
Robot rig: Omen 45L, **RTX 5090 (32 GB)** + Core Ultra 9 285K (Xe iGPU "GPU.0" + "AI Boost" NPU) + 64 GB.
Drives **C and E only — no D:/F:/G:**. Every `F:/AI/...` in memory → read as `E:/AI/...`. **AI-Models is on
`E:/AI-Models/`** (NOT D: — the global note is wrong for this rig; verified). WSL2 distro = `Ubuntu`;
training venv `~/bp-env`. **Do NOT tell Mike to rest / take a break / enjoy the win** (standing etiquette
rule — he has corrected it; end on work status or a plain ack).

## Read first (canonical memory: `C:/Users/mikey/.claude/projects/F--AI/memory/`)
- `MEMORY.md` — index (mission frame + rig topology at the top).
- `oversight-specialist-mint-strategy.md` — **START HERE.** The wedge strategy + the full "Delivered
  2026-06-06" section: wedge #1 conformance (v1 mint → v0.2 finetune → v0.3 floor → ship → live seam),
  the verifier-v2 lesson, the sidecar, the recipe knob. The v0.3 + rollout + live-seam paragraphs are the
  current frontier.
- `prism-verify.md` (v1.2.x state) · `workflow-standards.md` (the six; EXTERNAL_VERIFIER, fail-open) ·
  `research-grounded-advisor-protocol.md` (study-swarm trigger — fire for a new product layer like wedge #2).
- Repo dirs: `E:/AI/role-os/` (the watcher lives here now) · `E:/AI/prism-verify/` ·
  `E:/AI/gpu-container/specialist-training/` · `E:/AI/npu-sidecar/`.

## Where things stand (verified end of 2026-06-06)
- **prism-verify 1.2.1 + role-os 2.7.1 shipped** earlier; both live, CI green.
- **Oversight wedge #1 = tool-call conformance: SHIPPED to main + LIVE SEAM WIRED.** role-os `main` HEAD
  `9985994`. Four functional commits across 3 merges, **CI verified green each time** (npm ci/test/verify,
  node 18+22). Full suite **1377**.
  - **The mint:** Qwen3-14B QLoRA soup, served llama.cpp `--lora scale 4`. v1 (`conformance-14b-soup`) is
    the SERVED adapter/ceiling. v0.2 was a finetune that lifted the EXAM (L4 0.90/0.80→0.969/0.938) but did
    NOT generalize (independent OOD dogfood: v0.2 == v1, even +2 false-conformants) — **kept v1, did not
    promote v0.2.** The lesson (2nd time an exam overstated generalization): the OOD dogfood is mandatory.
  - **v0.3 = the deterministic CONTRACT FLOOR (the win).** Diagnosis: residual misses are COMPUTABLE
    contracts (sum-to-cap, additive bounds, cardinality, string-index) an LLM does unreliably at any
    training volume. Added `contractFloor` + a constraint DSL to `role-os/src/specialist/conformance-consult.mjs`
    (kinds: `cmp` w/ `{len}` operands, `sum`, `present`, `requires`, `distinct`, `member` w/ `{state}`,
    `char_at` w/ 1-based `offset`). **On the same OOD set: floor catches all 7 of v1's false-conformants,
    0 false-positives → combined OOD false-conformants 7 → 0, with ZERO retraining.** Fail-safe: only ever
    PROVES a violation, defers to the LLM when it can't, no-op for unannotated tools.
  - **Rollout (the per-tool catalog):** `tools/conformance-dataset/tool-constraints.json` (name →
    {constraints, state_struct}), grown safely by `build_tool_constraints.mjs` (drops any constraint that
    flags a tool's known-good call) + CI-enforced by `test/tool-constraints.test.mjs` (0 conformant FP).
    Seed = 90 corpus tools blind-authored (workflow): 119 constraints / 65 tools, floor owns 54% (57/106)
    of the trained violations deterministically; the rest are genuinely-semantic → the LLM.
  - **LIVE SEAM:** `onPreToolUse` (`src/hooks.mjs`) runs the floor against `.claude/role-os/tool-contracts.json`
    and attaches an **ADVISORY** verdict on a proven nonconformant call — **never denies, never throws,
    no-op when uncatalogued.** The generated PreToolUse hook does the same best-effort. Hot path is
    model-free; LLM ceiling stays opt-in (`ROLEOS_CONFORMANCE_CONSULT`, default OFF).
  - **WIRED BUT DORMANT:** the live catalog `.claude/role-os/tool-contracts.json` ships EMPTY. The watcher
    fires the instant a real tool gets an entry. The 90-tool corpus catalog is the *reference vocabulary*
    (generic names like `git_create_commit`), NOT keyed by real tool names yet.
- **iGPU embeddings sidecar — LIVE on `:8093`** (`E:/AI/npu-sidecar/npu_sidecar_server.py`, GPU.0,
  Qwen3-Embedding-0.6B, dim 1024). Resident until reboot; restart with that script.
- **Flags all OFF** (`ROLEOS_CONFORMANCE_CONSULT`, `ROLEOS_BUDGET_CONSULT`, `PRISM_LOCAL_VERIFIER_ENDPOINT`).
  GPU idle (no docker serve; only the iGPU sidecar). Adapters on `E:/AI-Models/adapters/`:
  `conformance-14b-soup` (v1, served/rollback), `conformance-14b-soup-v0.2` (shelved, did-not-generalize),
  `verifier-14b600-soup` (v1 verifier), `budgeter-14b600-soup`.
- **Branches pruned:** the two conformance feature branches (merged) are gone local+remote. Left:
  `cutover/dogfood-lab-testing-os` (unmerged), `feat/budget-production-consult` (Mike's stash attached —
  DO NOT TOUCH the stash), `token-budget-dataset` (merged, pre-existing — Mike may want it pruned).

## Next steps (talk with Mike first — flips, publishes, and now-live-traffic decisions are Mike-gated)
1. **Finish wedge #1's internal-first loop (advisor's lean).** The strategy is INTERNAL-FIRST — polish
   through use. Populate `.claude/role-os/tool-contracts.json` for 1–2 of the studio's OWN repos with REAL
   tool names (built-ins + `mcp__server__tool` schemas + their computable contracts), each validated
   against a known-good call with the guard (`build_tool_constraints.mjs` pattern). Then the advisory
   watcher runs on friendly traffic and accrues the certified receipts that ARE the moat.
2. **Wedge #2: sycophancy** — the next mint in the strategy order (a prism-verify lens; cross-family is the
   whole value prop). **Fire the study-swarm protocol** before designing (it's a new product layer). Then
   wedge #3: citation (thin adaptation of verifier-v2 + a deterministic DOI/arXiv resolver).
3. **Verifier-v2.1** (#8, in_progress) — the voice-invariance retry that didn't generalize. The v0.3 lesson
   reframes it: the un-learnable part may belong in a deterministic check, not more finetune.
4. **Sidecar follow-ups** (#12) — rerank (`bge-reranker-base-int8-ov`) + a small judge; NPU static-shape
   tuning (needs npuw reshape); wire role-os/repo-knowledge to offload embeddings to `:8093`.
5. **Ops/housekeeping** — dataset publish (#6, deferred to Mike's HF trusted-publishing); Ollama
   0.24.0→0.30.6 (#10, `winget upgrade Ollama.Ollama`); prune `token-budget-dataset` + central site sync (#9).

## Reuse — do NOT re-derive
- **The mint recipe + scripts:** `gpu-container/specialist-training/` — `RESULTS.md`, `train_verifier.sh`
  (data-parametric via `BUDGETER_DATA`/`BUDGETER_TAG`; + `BUDGETER_BATCH`/`BUDGETER_ACCUM`, default 4/4),
  `train_conformance_v0.2.ps1` (the watchdog-wrapped 2-seed launcher to clone), `soup_adapters.py`,
  `certify_conformance.ps1`, `dogfood_conformance.ps1`/`.py`.
- **The conformance dataset machinery:** `role-os/tools/conformance-dataset/` — `config/conformance_puzzles/
  corpus_tools+corpus_l4/audit/build` (contrast groups, flip-consistency, audit HARD GATE, tool-atomic
  split), `author_l4.py` + `validate_l4.py` (author + mechanically label-check a new rung), `certify_conformance.py`.
- **The OOD generalization gate (mandatory before promoting any specialist version):** `ood/fresh_cases.jsonl`
  (49 independent cases) + `ood_floor_eval.mjs` (floor proof) + `dogfood_conformance.py` (served-model
  head-to-head). The `conformance-ood-probe` + `conformance-constraint-author` + `tool-constraint-rollout`
  workflows regenerate the fresh sets / blind-author constraints.
- **The floor + catalog API:** `conformance-consult.mjs` exports `schemaFloor`, `contractFloor`,
  `withToolConstraints`, `consultConformance`; `hooks.mjs` exports `loadToolContracts`, `conformanceAdvisory`.
- **Watchdog launch (the ONLY WSL kill switch):** `python -m gpu_container.watchdog run --on-breach
  wsl-shutdown --power-max 100 --temp-max 87 --host-mem-max 80 --interval 10 --peaks-out <f> -- wsl -d
  Ubuntu -- bash -lc '<env> bash /mnt/e/AI/gpu-container/specialist-training/train_verifier.sh'`.

## Gotchas (load-bearing)
- **Exam ≠ generalization.** Twice now a held-out exam reported a lift that an independent OOD dogfood
  killed (verifier-v2 voice, conformance v0.2). ALWAYS run the OOD dogfood before promoting/serving.
- **LLM rungs plateau on computation.** Push computable contracts to the deterministic floor; reserve the
  model for the genuinely-semantic residue. That's the v0.3 win and the wedge's moat.
- **Long-sequence datasets OOM at batch4** (98% VRAM): `BUDGETER_BATCH=2 BUDGETER_ACCUM=8` (eff batch 16).
  Measure seq length first (`packing=False` pads to batch-max). Conformance ~600 tok needed batch2.
- **Never train + serve concurrently on the 5090.** The iGPU sidecar (GPU.0) is fine alongside a 5090 train.
- **NPU:** OpenVINO sees it but the embedding model's dynamic shape fails on `intel_npu` → use **GPU.0
  (iGPU)**. **IPEX-LLM is archived (2026-01) — use OVMS/OpenVINO.** WSL2 can't see the NPU. System Python is
  3.14 (no openvino wheels) → use the 3.12 venv at `E:/AI/npu-sidecar/.venv`.
- **uv-Windows trampoline bug:** run via `uv run python -m mypy/pytest/ruff` (not `uv run mypy`).
- **Cross-family gate** (`synth.py`): Ollama on the WINDOWS host; `qwen3.6` is a reasoning model → keep
  `"think": false`.
- **README front-door doctrine** + the `readme-front-door-lint.py` PostToolUse hook: value-prop only on
  READMEs; technical detail → CHANGELOG/handbook. **Translations BEFORE any publish** (`node
  E:/AI/polyglot-mcp/scripts/translate-all.mjs <readme>`).
- **role-os CI:** paths-gated (`src/**`,`test/**`,`package.json`,`bin/**`,`starter-pack/**`,`.github/**`);
  `npm test` + `npm run verify` on node 18+22. Run `npm run verify` locally before merging (pre-empt red CI).
  Data files under `tools/` are NOT a CI path.
- **Mike-gated:** commits/pushes, npm/PyPI/HF publishes, the three consult flips, AND — now that the seam is
  live — populating a real `.claude/role-os/tool-contracts.json` on any repo (it changes live advisory
  behavior). Don't auto-do them. The watcher is advisory + fail-open, so even when on it can't block a call.
- `.polyglot-cache.json` churn + the `feat/budget-production-consult` stash are Mike's — never stage/touch.

## Standing decisions
Oversight fleet is **internal-first** (polish through use, accrue certified receipts, then decide on
exposure). Wedge order: **conformance ✓ (shipped+live) → sycophancy → citation.** The moat is the
deterministic floor + the leakage-audited, flip-consistency-CERTIFIED minting PROCESS + role-os/prism
native decorrelation distribution — **NOT the weights, NOT a bigger model.** Embed where you have
distribution; do not start an oversight-SaaS against Galileo/Patronus. v1 conformance + v1 verifier stay
served; v0.2 conformance + v2 verifier are shelved negatives kept as diagnoses.
