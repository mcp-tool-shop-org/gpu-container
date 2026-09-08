# Resume kickoff — oversight fleet: wedges #1+#2 SHIPPED/LIVE, START with a fleet-receipts study-swarm

You are the advisor continuing a long, productive run (2026-06-07/08). The 3-wedge plan is essentially
executed; the frontier is the FLEET / certified-receipts layer. **Read the memory FIRST, then — per Mike's
instruction — START THIS SESSION WITH THE STUDY-SWARM specified below (Section 1), then pick next steps with
Mike.** Authored 2026-06-08.

## Rig (overrides any F:/AI path you read)
Robot rig: Omen 45L, **RTX 5090 (32 GB)** + Core Ultra 9 285K (Xe iGPU "GPU.0" + "AI Boost" NPU) + 64 GB.
Drives **C and E only — no D:/F:/G:**. Every `F:/AI/...` in memory → read as `E:/AI/...`. **AI-Models is on
`E:/AI-Models/`.** WSL2 distro = `Ubuntu`; training venv `~/bp-env`. **Do NOT tell Mike to rest / take a
break / enjoy the win** (standing etiquette — end on work status or a plain ack).

## Read first (canonical memory: `C:/Users/mikey/.claude/projects/F--AI/memory/`)
- `oversight-specialist-mint-strategy.md` — **START HERE.** The top "⚡ CURRENT STATE — 2026-06-08" block is
  the frontier; the dated "Delivered" sections below it have the receipts.
- `research-grounded-advisor-protocol.md` — **the study-swarm protocol; you fire it in Section 1.** Read it
  before writing the dispatch. Step-4 gate is MANDATORY (no finding load-bearing unless verified).
- `prism-verify.md` · `workflow-standards.md` (the six; EXTERNAL_VERIFIER, fail-open).
- Repos: `E:/AI/prism-verify/` (the lens + `prism.probes` + the mint machinery under `specialist/`) ·
  `E:/AI/role-os/` (the conformance watcher + `verify-citations`) · `E:/AI/gpu-container/specialist-training/`.

## 1) FIRST ACTION — fire this study-swarm (research-grounded-advisor protocol)

**Topic: the runtime oversight-FLEET + certified-receipts / assurance layer.** The 3 watchers now exist
(conformance LIVE, sycophancy v1 LIVE + active-probe integrated, citation via prism). The strategy says the
moat is "the leakage-audited, flip-consistency-certified minting PROCESS WITH HELD-OUT RECEIPTS" and
"raise the joint-failure floor and PUBLISH the residual error." So the next product layer is the fleet's
runtime aggregation + the certified-receipt/assurance trail — a genuinely NEW layer → study-swarm fires.

Dispatch one web-research agent per question (single message, parallel; general-purpose agentType for web
access). Each prompt: paper titles + authors + years + arXiv/DOI + URL + one-sentence finding; retrieved-flag
enforced; ~550 words; specificity over breadth. Then synthesize → Step-4 gate (`roleos verify-citations`,
`PRISM_CMD=E:/AI/prism-verify/.venv/Scripts/prism.exe`, `PRISM_DEV=1`; drive the LIBRARY `runCitationGate`
with a big timeout via `prism-verify/design/_run_citation_gate.mjs <dispatch> <out>` because the CLI's 120s×2
is too short, and arXiv rate-limits the TAIL of a >20-citation burst → corroborate residuals via prior receipts
+ WebFetch) → connect findings to architecture → present.

The 5 load-bearing questions (refine with Mike if you like, but these are the spine):
1. **Multi-DUTY aggregation** — how to combine verdicts from decorrelated watchers of DIFFERENT duties
   (conformance + sycophancy + citation) into a joint verdict: panel weighting, MEASURED entanglement vs
   assumed-from-labels, when ≥2-agreement is required, surprising-popularity. (Some anchors already in the
   v0.2 swarm: Verga PoLL 2404.18796, Kuai 2604.07650, Ai 2510.01499 — but cross-DUTY is the new part.)
2. **Joint calibration + the RESIDUAL-ERROR budget** — selective prediction across the fleet, the abstain
   budget, the joint false-clear rate, and how to PUBLISH a defensible residual-error number (the strategy's
   framing). (Anchors: Geifman 1705.08500, Fisch 2208.12084, Badshah 2602.13110, Radharapu 2512.22245.)
3. **Certified-receipt / ASSURANCE-CASE design** — what makes an ML oversight verdict AUDITABLE + defensible:
   assurance cases (GSN), model/system cards, signed replayable receipts, the evidence trail — for an
   internal-first layer that may face EU AI Act high-risk (live Aug 2026) / Colorado AI Act (Jun 2026). What
   is the MINIMAL credible receipt?
4. **Active-probe PRODUCER-ACCESS architecture** — how to safely give a runtime verifier producer access
   (re-querying the model under test): the integration surface, leakage/soundness controls, pinned probes,
   cost, when the extra producer calls are worth it. (The sycophancy active probe needs this to go live.)
5. **Fleet DRIFT + recertification** — keeping small distilled judges healthy in production: drift detection
   (semantic/behavioral/performance), scheduled recert, the one-base-recertifies-the-fleet opex model (the
   strategy's mitigation), and the receipts that prove ongoing validity.

## 2) Where things stand (verified end of 2026-06-08)
- **Wedge #1 conformance — LIVE + pushed, CI green** (role-os + gpu-container `feat/conformance-live-catalog`).
  Generator wire-format bug fixed. Flags OFF.
- **Wedge #2 sycophancy — v1 LIVE** (`prism.lenses.sycophancy` + engine `_verify_sycophancy` branch +
  `SycophancyProvider`, prism-verify `feat/sycophancy-lens-v1`, pushed, CI green; served + e2e-verified).
  Served adapter `sycophancy-14b-soup`, OOD flip 0.82. **v0.2 = clean NEGATIVE** (passive L4 expansion did NOT
  lift L4 → KEEP v1). **v2 ACTIVE PROBE integrated into prism** (`prism.probes`, pushed, CI green) — the
  validated L4 fix. Production flip = `PRISM_SYCOPHANCY_ENDPOINT` (Mike-gated). Serve = `serve_sycophancy.ps1` :8095.
- **Wedge #3 citation — largely SHIPPED** as prism v0.3 citation-verify + `roleos verify-citations` (you'll use
  it as the Step-4 gate above). Confirm the gap before any dedicated citation mint.
- **All mint machinery backed up + pushed**; adapters on E:/AI-Models (HF later). v0.2 kept as the diagnosis.

## 3) Next steps after the swarm (talk with Mike — flips/publishes/serves are Mike-gated)
- The fleet/receipts dispatch from Section 1 → design + (if Mike approves) build the aggregation + receipt layer.
- **Finish the sycophancy active probe:** a producer-supplying entry (`prism probe-sycophancy` CLI / verify
  mode) so an orchestrator with the producer endpoint runs it on live traffic. Module is callable today.
- **The ≥3-lens panel + ≥2-agreement calibrated emission gate** for the sycophancy lens (the v0.2-dispatch design).
- Decide **citation: reuse the prism path vs mint a dedicated specialist** (likely reuse).
- Ops: HF dataset publish (Mike-gated); the 3 consult flips + `PRISM_SYCOPHANCY_ENDPOINT` (Mike-gated).

## 4) Reuse — do NOT re-derive
- **The mint press** (`prism-verify/specialist/dataset/`, now TRACKED): `sycophancy_config.py` + the verifier
  machinery, `build_sycophancy_records.mjs` (OUT_PREFIX + EXCLUDE_TRAIN_DOMAINS), `audit.py` (the hard gate),
  `certify_sycophancy.py` (cost-asymmetric flip-consistency scorer). The OOD gate (`sycophancy_ood.jsonl`) is
  MANDATORY before promoting ANY version — it killed v0.2 honestly.
- **The train/serve/certify scripts** (`gpu-container/specialist-training/`, now tracked on the backup branch):
  `train_verifier.sh` (data-parametric), the watchdog launchers `train_sycophancy{,_v02}.ps1`, `soup_adapters.py`,
  `certify_all_sycophancy{,_v02}.ps1`, `serve_sycophancy.ps1`, `dogfood_sycophancy.ps1`.
- **The dispatch+gate cadence**: `design/sycophancy-{wedge,v0.2}-dispatch.md` + `_run_citation_gate.mjs` + the
  gate-result receipts are the template for the Section-1 dispatch.
- **The active-probe code**: `prism.probes` (capitulation/counterfactual/run_active_sycophancy/HttpProducer/LlmComparator).

## 5) Gotchas (load-bearing)
- **Exam ≠ generalization — run the OOD dogfood before promoting.** 3rd confirmation this run (conformance-v0.2,
  verifier-v2, sycophancy-v0.2 all lifted an exam but failed/flat-lined OOD). **L4 is a passive-lens ceiling →
  the ACTIVE PROBE is the fix, not more passive data.**
- **prism is a SHIPPED strict-CI product** (ruff `src/ tests/` + mypy --strict `src/` + pytest `tests/`, 366
  green). New `src/`+`tests/` code must pass it. **Line-length is 100 — wrap docstrings/comments conservatively
  (I burned several iterations on E501).** CI does NOT lint `specialist/`/`design/` scratch (that's fine).
- **Never train + serve concurrently on the 5090.** Stop `sycophancy-serve` (`docker rm -f`) + `ollama stop` +
  confirm nvidia-smi idle before any train. Train UNDER the watchdog (`--on-breach wsl-shutdown`, temp-max 87).
  Seqs ~530-590 tok → `BUDGETER_BATCH=2 BUDGETER_ACCUM=8`.
- **Step-4 gate mechanics:** arXiv rate-limits the TAIL of a big citation burst (same ~6 fail both runs) — that
  is oracle-transient, NEVER fabrication; corroborate via prior receipts + WebFetch. `not_addressed` = tighten
  the claim to abstract scope (demote specific figures to "(body)" parentheticals).
- **Mike-gated:** commits ok when asked; pushes ok ("push as needed" was granted this run, but re-confirm per
  session); npm/PyPI/HF publishes; the consult flips; `PRISM_SYCOPHANCY_ENDPOINT`. `.polyglot-cache.json` +
  Mike's stashes — never stage/touch.
- **Docker must be up** for serve/certify (`docker_up.ps1`). prism runs via `uv run prism` (uv-Windows: use
  `uv run python -m ...`).

## Standing decisions
Oversight fleet is **internal-first** (polish through use, accrue certified receipts, then decide on exposure).
Wedge order conformance ✓ → sycophancy ✓ → citation (≈done via prism). The moat is the deterministic floor +
the leakage-audited flip-consistency-CERTIFIED minting PROCESS + role-os/prism native decorrelation distribution
— NOT the weights, NOT a bigger model, and (the v0.2 lesson) NOT more passive finetune. Embed where you have
distribution; do not start an oversight-SaaS against Galileo/Patronus. v1 conformance + v1 verifier + v1
sycophancy stay served; v0.2 sycophancy + v2 verifier are shelved negatives kept as diagnoses.
