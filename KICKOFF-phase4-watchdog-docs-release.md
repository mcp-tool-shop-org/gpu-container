Kickoff — gpu-container Phase 4: wire/upgrade the watchdog → Doc Delight → Release-readiness assessment

⚠ PREFLIGHT FIRST — non-negotiable
Read KICKOFF-preflight-rig-safety.md (in this repo) BEFORE any GPU/model work, and follow it. The 2026-06-04 gpt-oss-120b incident (host memory 92–98%) is why it exists. The short version, now with the tool that institutionalizes it:

.wslconfig memory cap = 28 GB. NEVER raise it. (Set to 28 GB + autoMemoryReclaim=gradual.)
Models live on E:\AI-Models via a BIND MOUNT (-v "E:/AI-Models/<model>:/models"), never a Docker named volume (those sit in docker_data.vhdx on C:).
A live run must be sized to the rig: N=0 (all-VRAM) is the proven-safe case; a must-offload proof needs a model whose offloaded experts are ≤ ~15 GiB (≤ ~40 GB total quant). gpt-oss-120b / GLM-4.5-Air / Qwen3-235B are paper-only here.
Abort = wsl --shutdown (instant), NOT docker stop. Stop the instant the user flags memory.
NEW (this is Phase 4 Track A): gpu-container-watchdog now exists — RUN IT during any GPU job. One-shot `gpu-container-watchdog --json` (exit 0/5/7) or `--watch --on-breach wsl-shutdown`. It polls GPU power/temp/VRAM + host memory vs thresholds (default abort: host-mem 90%, power 95%, host-free <2 GB). Default action is alert-only; opt into wsl-shutdown for autonomous abort. This is the rig's safety net — use it, don't reinvent the manual monitoring.

Mission
Continue building gpu-container — a model-aware inference memory-placement planner for single-GPU rigs. It profiles the rig + model, emits an explicit VRAM / pinned-RAM / NVMe placement plan across runtimes, proves it with a measured receipt, refuses below ~1 tok/s, and now (a) de-risks the per-expert-cache decision with a measured concentration gate, and (b) defends the rig with a safety control plane. Flagship lane = MoE expert tiering. NOT "Docker VRAM overflow" — CUDA UVM oversubscription is unavailable on Windows/WSL2; explicit declared placement is the moat. Director: Mike — a 1-human + LLM-crew studio; warm, fast, high standards; NOT a traditional solo dev (don't propose RPG-Maker-scale shortcuts).

Phase 4 is consolidation toward a shippable product: harden + wire the watchdog, make the docs delightful and comprehensive, and run a release-readiness assessment. Less new GPU science; more "make what's built honest, safe, documented, and ready."

Rig & paths (load-bearing)
RTX 5090 (Blackwell sm_120, 32 GB VRAM), 64 GB RAM, Windows 11 + WSL2, driver 610.47. Drives C and E only (no D/F/G); every F:/AI/... in memory means E:/AI/...; the F--AI folder under C:/Users/mikey/.claude/projects/ is a project hash — leave it.

WSL2 VM capped at 28 GB (.wslconfig); container sees ~28 GB. Do not raise.
Docker = Linux containers (desktop-linux), WSL2 backend, nvidia runtime. Never Windows containers.
CUDA 12.8 for sm_120 — NOT 13.x. The prebuilt ghcr.io/ggml-org/llama.cpp:full-cuda image is CUDA 12.8.90 ✓ and (verified Phase 3) ships llama-cli, llama-bench, llama-imatrix, llama-eval-callback, + python3 with the `gguf` package; it has gcc/g++/make but NO llama.cpp headers and no cmake/nvcc (so a custom-C harness can't be built in-image — imatrix is the working trace path).
Python 3.14; gpu-container is pip install -e ".[dev,host]" (host extra = psutil+numpy, needed by the watchdog). numpy on host.
Ollama verifiers (study-swarm, if needed): mistral-small:24b, granite4.1:30b. May be down → ollama serve.
⚠ Bash-tool docker mounts of Windows paths need MSYS_NO_PATHCONV=1; prefer PowerShell for docker (no path mangling).
⚠ Git-Bash /tmp ≠ Windows temp — write scratch to E:\AI-Models\... or the repo (gitignored profile*.json/plan*.json/bench*.json/receipt*.json/*.config.json), not /tmp.

State — where Phase 3.5 (this session, 2026-06-04) left it
gpu-container — github.com/mcp-tool-shop-org/gpu-container · E:\AI\gpu-container · REPO IS PRIVATE (Mike made it private 2026-06-04 after the incident; confirm visibility/release intent with him before ANY public/release action). main HEAD = 6860740, all pushed, clean tree (except untracked KICKOFF-*.md). 60 tests green. version 0.1.0.

This session's commits (newest first):
- 6860740 watchdog — the rig-safety control plane (gpu_container/watchdog.py; gpu-container-watchdog).
- 819e495 receipt --trace folds the per-expert routing de-risk verdict into the receipt; README + moe-lane docs surface the CLI; trace path corrected to llama-imatrix.
- 5626551 gpu-container-concentration CLI (the de-risk gate as a command).
- eb18dd7 -fa on fix (current llama.cpp rejects bare -fa).
- 0b63ee8 ADR-0001 empirical de-risk result.
- d384861 activation.py — the concentration de-risk gate (ActivationTrace + analyze_concentration).
- 5e62d19 ADR-0001 — Option B (consume #20757's cache mechanism, contribute the policy).
- 4ce6bbd moe-lane design reconcile (per-expert = runtime cache, not -ot).
Pre-session: 5735772 (M1 recalibration loop), 339aaed (planner), 492eac5 (profiler benches), 0eca183 (profiler skeleton), 4f821e3 (front-door README).

5 CLIs / entry points: gpu-container-profile, -plan, -receipt, -concentration, -watchdog.
Modules: gpu_container/profiler/{cli,hardware,model,schema,cuda_bench,nvme_bench,baseline}.py · gpu_container/planner/{placement,calibration,receipt,receipt_cli,cli,activation,concentration_cli}.py · gpu_container/watchdog.py.
Docs: docs/{architecture,features,constraints,prior-art,feasibility,moe-lane-architecture}.md + docs/decisions/0001-per-expert-cache-build-vs-upstream.md (ADR).

The flagship per-expert decision is RESOLVED + de-risked:
- ADR-0001: Option B — consume llama.cpp #20757's expert-slot cache mechanism, contribute the policy (Least-Stale eviction + cross-layer-gate prefetch), keep calibration/trace/receipt in-product. Never fork the kernel.
- Empirical de-risk: captured a real Qwen3-30B-A3B activation trace via llama-imatrix at N=0, ran the concentration gate → routing is NEAR-UNIFORM on both diverse (~51% of experts for 90% coverage) and narrow single-domain (~45%) workloads → the #20757 per-expert cache is NOT worth building for Qwen3-class load-balanced MoEs. Revisit only for a model/workload that scores cache_helps with a LOW hot_frac (<0.25). The cache build is ON HOLD with evidence — do not re-litigate; re-run the gate per target model (cheap, one N=0 imatrix pass).

readouts KB — E:\AI\readouts · main 58ef83a. docker-knowledge moe-placement lane now 17 findings (5 feasibility + 12 implementation, wave-4, 3-lens verified, 0 fabrications). tensor-engine-knowledge owns engine internals (consult, do NOT re-research). Memory: C:/Users/mikey/.claude/projects/F--AI/memory/gpu-container.md (has the ⚠ RIG SAFETY section + the Phase-3 + de-risk + watchdog records).

Assets on the rig
Docker volume gpc-models holds Qwen3-30B-A3B-Q4_K_M.gguf (17.4 GB, top-8 of 128 experts, 48 layers) — fits VRAM at N=0; C:-backed (read-only use is fine; for any NEW model bind-mount from E:\AI-Models). gpc-bench (ext4, fio). Image gpu-container:latest (profiler). ghcr.io/ggml-org/llama.cpp:full-cuda (CUDA 12.8; has llama-imatrix + python gguf — the trace-capture path). E:\AI-Models exists (designated models/scratch drive); the Phase-3 captrace scratch was deleted.

The three tracks (suggested order; do Track A's wiring before any further GPU runs so they self-monitor)

────────────────────────────────────────────────────────────
Track A — Wire + upgrade the watchdog (the safety control plane)
────────────────────────────────────────────────────────────
The watchdog (gpu_container/watchdog.py) ships as a pollable monitor + a --watch loop (default action alert-only; opt-in wsl-shutdown/docker-stop/kill/command). 10 tests; verified live on idle rig (power 2.4%, host-mem 26.9%). Upgrade it from "a monitor you run beside a job" to "the supervisor a GPU job runs under":

A1. Supervise-a-subprocess mode (the load-bearing wiring): `gpu-container-watchdog run --interval N --on-breach <action> -- <command...>` launches the command, polls metrics in parallel, and on a hard breach runs the action — INCLUDING a new `kill-job` action that terminates the supervised subprocess (a softer abort than nuking the whole VM). This makes "run a GPU job safely" one command, and is how future capture/bench runs should execute. Keep wsl-shutdown for the catastrophic case.
A2. Peak metrics → receipt: record peak power / host-mem / VRAM observed during a supervised bench and embed them in the Receipt (proving the run stayed inside the safe envelope). Wire watchdog peaks into receipt.py/receipt_cli.py (or a thin runner). A receipt should be able to say "decode 302 tok/s; peak host-mem 31%, peak power 41% — safe."
A3. Upgrades: multi-GPU (parse all GPUs, take worst-case — currently first-GPU only); a shipped watchdog.json with the rig defaults (+ a --config example); a rolling sample log / trend (so an AI sees the trajectory, not just the instant); reconcile GPU-VRAM source vs the profiler's pynvml; clearly tag whether psutil is reading the Windows host (run on host) or the WSL2 VM (run in-container) — the incident metric is the HOST, so document/prefer host execution.
A4. Tests + a SAFE supervised smoke: unit-test the run/supervise loop + kill-job (mock the runner). Then one LIVE safe proof: supervise a trivial job (e.g. a tiny N=0 llama-bench or even `nvidia-smi -l`) with a deliberately-low threshold so the watchdog trips and kills the JOB (not the VM) — proving supervise + kill-on-breach end to end, with zero rig risk.
Rig-safety: the watchdog is the net; all Track-A live work is N=0/trivial. Keep None-not-guess (a missing metric is unknown, never 0). Exit codes 0/5/7 stay stable (scriptable contract).

────────────────────────────────────────────────────────────
Track B — Doc Delight (comprehensive, polished, honest docs)
────────────────────────────────────────────────────────────
A lot was built since the Phase-0 docs. Make the docs reflect built reality and delight a reader. README stays the marketing front door (lint hook flags internal process/status — keep methodology/status out of it); docs/ carries the depth.

B1. CLI reference (docs/cli.md): all 5 commands — profile / plan / receipt / concentration / watchdog — synopsis, flags, exit codes (0/3 plan; 0/3/4 receipt; 0/5/2 concentration; 0/5/7 watchdog), worked examples. The product now has a real surface; document it.
B2. Quickstart / walkthrough (docs/quickstart.md): the honest end-to-end story — profile in-container → plan → launch llama.cpp under the watchdog → receipt (with --trace) → recalibrate; plus the de-risk gate; plus "how to run the largest useful model SAFELY." Delightful, copy-pasteable, rig-accurate.
B3. Reconcile the existing docs to built reality: architecture.md (the recalibration loop is built; the de-risk gate + watchdog exist), features.md (the feature set grew — 7 now incl. routing de-risk + watchdog), feasibility.md (the ±10% receipt + de-risk are confirmed live). Remove stale "Phase-0/in-development" framing where it's now done.
B4. The de-risk methodology as a first-class doc (docs/derisk-concentration.md or similar): how the concentration gate works (hot_frac, concentration_score), the imatrix capture path, the real Qwen3 finding (near-uniform → hold #20757), the workload-dependence caveat. Today this lives only in ADR-0001 — give it a proper home + cross-link.
B5. Handbook (Starlight) — GATE on release intent (Track C). If heading to release, the Handbook Playbook (C:/Users/mikey/.claude/projects/F--AI/memory/handbook-playbook.md) sets up a Starlight docs site connecting a landing page to docs (Phase 3 of full-treatment). Otherwise defer.
B6. README polish: keep the front-door doctrine; ensure the 7 features + the Documentation index are current; no internal/process jargon.

Note: translations (the README.{ja,zh,...} flow) are a marketing-repo convention; gpu-container is a tool repo — likely SKIP unless Mike wants them. The advisor may run translations; Sonnet sessions defer.

────────────────────────────────────────────────────────────
Track C — Release-readiness assessment audit
────────────────────────────────────────────────────────────
Assess gpu-container against the release bar and produce a gap list + path to v1.0.0. THE AUDIT IS THE DELIVERABLE — the release itself is a separate, Mike-approved step.

C0. ⚠ CONFIRM RELEASE INTENT WITH MIKE FIRST. The repo is PRIVATE (made private after the incident). "Release" for a tool repo (per canonical-ownership: tools → mcp-tool-shop-org, a public org) likely means making it PUBLIC + v1.0.0. Do NOT change visibility or publish without explicit confirmation. The assessment itself is read-only and can proceed on a private repo.
C1. Run shipcheck (the 31-item gate; hard gates A–D block release). Read C:/Users/mikey/.claude/projects/F--AI/memory/shipcheck.md, then: npx @mcptoolshop/shipcheck init → work SHIP_GATE.md (mark non-applicable as SKIP: reason) → npx @mcptoolshop/shipcheck audit. Assess:
  A Security — SECURITY.md present? threat model in README? no secrets/telemetry (planner is local, no telemetry — likely clean; confirm).
  B Errors — structured shape (code/message/hint)? exit codes for CLIs (present: 0/3, 0/3/4, 0/5/2, 0/5/7 — good). Audit the error outputs.
  C Docs — README ✓, CHANGELOG (create), LICENSE (MIT — confirm file present), --help accurate (argparse — good).
  D Hygiene — a verify script (test runner), version matches tag, dep scanning, clean packaging (python -m build + check; it's a Python package, not npm).
  E — logo, translations (likely SKIP, tool repo), landing page, Starlight handbook (Track B5), GitHub metadata (topics/description/homepage).
C2. Version: bump 0.1.0 → v1.0.0 (shipcheck-product-standards: v0.x promotes to v1.0.0, never patch-bump pre-1.0). Only when Mike greenlights the release.
C3. CI assessment (github-actions rules, NON-NEGOTIABLE): does the repo have a paths-gated ci.yml? If not, add ONE right-sized workflow — on.push.paths [pyproject.toml, gpu_container/**, tests/**, .github/workflows/**] + workflow_dispatch + concurrency (cancel-in-progress) + ubuntu-latest + a single small matrix (Python 3.11/3.12) running pytest. Max 2 workflow files. No release/publish workflow unless Mike wants PyPI.
C4. Output: a release-readiness report (docs/ or a RELEASE_ASSESSMENT.md) — the scorecard, the gaps, the prioritized path to v1.0.0 — reflecting ACTUAL shipcheck results, not estimates.

Rules
Before any Write/Edit: read C:/Users/mikey/.claude/projects/F--AI/memory/MEMORY.md (hook-enforced) + memory/gpu-container.md + KICKOFF-preflight-rig-safety.md.
Honor the preflight's memory-safety rules above everything. RUN gpu-container-watchdog during any GPU job (Track A makes this one command). Stop instantly on a memory warning (wsl --shutdown).
README = marketing front door only (lint hook flags internal process/status). docs/ carries depth.
Repo-first hard rule + canonical-ownership: gpu-container → mcp-tool-shop-org (it's there, private). No visibility/publish change without Mike.
Commit only when Mike asks. gpu-container → main + push; readouts waves → main. Stage explicit files (never git add -A); leave KICKOFF-*.md untracked. End commit msgs with: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>.
Study-swarm (research-grounded-advisor-protocol): Doc Delight + Release audit do NOT trigger it (polish/audit). The watchdog supervise-mode is mechanical. Invoke ONLY if a genuine qualitative design fork appears (e.g., "should peak-metrics live in the receipt or a separate safety-receipt"). Don't re-research engines (tensor-engine-knowledge owns those) or the per-expert decision (resolved + de-risked — ADR-0001).
Workflow-standards: if you author a new .mjs runner / mission / multi-step workflow file, include the "Standards compliance" section (six standards, 0–3). Shipcheck/full-treatment carry their own.
Verify in-container before claiming a number. Keep None-not-guess. Roofline is a CEILING (real is a fraction) — never a point prediction.

First moves
Read MEMORY.md + memory/gpu-container.md (the rig-safety section) + KICKOFF-preflight-rig-safety.md.
cd E:\AI\gpu-container && python -m pytest tests -q → expect 60 green.
Confirm state: git -C E:\AI\gpu-container log --oneline -8 (HEAD 6860740), gh repo view mcp-tool-shop-org/gpu-container --json visibility (PRIVATE), gpu-container-watchdog --json (verdict ok), docker run --rm alpine free -m (~28 GB cap).
Ask Mike: which track first (A watchdog / B docs / C release audit), AND — for Track C — confirm release intent + public/private (gate C0).

Loose ends (ignore / clean as needed)
Untracked scratch in the repo: KICKOFF-phase1-benches.md, KICKOFF-phase2-calibration.md, KICKOFF-phase3-perexpert.md, KICKOFF-preflight-rig-safety.md, this file (KICKOFF-phase4-watchdog-docs-release.md). Leave untracked. readouts: KICKOFF-readouts-product.md, wave-02 _build_raw.py.
LF→CRLF git warnings on Windows are cosmetic.
