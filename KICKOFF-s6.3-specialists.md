# KICKOFF — Specialists S6.3 (attended-GPU measurement campaign) + open polish

**State (2026-06-13, end of a long build session).** The whole specialist training-programs layer is
built end-to-end and renders honest provisional states; S6.3 is the attended-GPU phase that fills it
with real numbers. Everything below is committed + pushed unless noted.

## What's done (do not rebuild)

- **S4d — untraining (RESULTS.md S4d, gpu-container `chore/specialist-training-backup` 3599fc4; ledger event `untraining-experiment`).** Subtracting the conformance task vector from the from-scratch joint-soup adapter MONOTONICALLY COLLAPSES budgeter L2 (flip 0.467→0.300→0.000). **Joint SFT ≠ task-vector addition**; cosine 0.074 (near-orthogonal) does NOT imply safe-to-compose. ANDON ref reproduced S4c exactly.
- **S5 — Form (role-os main).** Per-dispatch field-input + OUTPUT logging (`src/specialist/field-log.mjs`, sibling of the events ledger). **Drift detector v1** (`src/specialist/drift.mjs`): research-grounded two-arm gate (`design/specialist-drift-detection.md`, study-swarm wf_e7feeda2-061) — BBSDh G-test on the verdict marginal (categorical, e.g. conformance) OR numeric KS on the scalar output (the budgeter is a REGRESSOR: verdict `{spend_weighted:N}`) + ATC/ECE performance arm; `stale` iff output-drift AND degraded-perf; advisory-only, never auto-fires GPU. **Finding:** the served `score` is a hardcoded constant in the shims — the perf arm is inert until serving returns a real verdict-token logprob.
- **S6.0 — contract (role-os `design/specialist-training-programs.md`).** Study-swarm-grounded (wf_9b6208e9-b97, 22 cited findings) + **Step-4 verified** through `roleos verify-citations` → prism (signed receipt; existence 22/22 + groundedness 14 supported / 0 fabricated, mistral-small:24b). prism signing key provisioned (`prism keygen`, kid ed25519-91914c8d…). The prism groundedness/local-panel bug was diagnosed + fixed (role-os 54f6a32; see memory `prism-citation-groundedness-local-panel`).
- **S6.1 — curriculum graph.** `src/specialist/training-programs.mjs` builder (directional witness fusion + DAG acyclicity gate + transitive reduction + cheapest-chain + evidence ladder). `roleos crew --programs` renders the tech tree. Reads a PUBLISHED `curriculum.json` (role-os stays sqlite-free) — resolves by default via the **sibling** `../readouts/training-knowledge/curriculum.json` (or `ROLEOS_CURRICULUM_PATH` / `.role-os/curriculum.json`). KB side (readouts b7d3424): `technique_edges` table + 8 nullable GUARANTEE columns; `migrate_s6.py` (guarded ALTER) + `gen_curriculum.py`. **74 active techniques / 9 prerequisite edges, all `unverified`.**
- **S6.2 — recipe preview + interference flag.** `roleos crew --preview <slug|name>` surfaces predicted-outcome (mixing-law tier + out-of-band confidence downgrade) + forgetting-risk (replay fraction) from the KB's per-technique `preview` block — honest "awaiting S6.3" until data. Crew sheet shows the reused cross-train cosine as a pre-run interference flag (`record.compatibility`; real: Token Budget Analyst "parent cos 0.0048 … near-orthogonal — a flag, not a proof — see S4d").
- **S6.3 — SET UP (no GPU), not run.** The write-back loop is PROVEN end-to-end: `readouts/training-knowledge/scripts/record_measurement.py` (idempotent upsert of edge transfer-deltas into `technique_edges` + per-technique preview fits) → `gen_curriculum.py` → `curriculum.json` → role-os (a sample edge flipped `provisional → "graph, 1 confirmed"`, then reverted). Run-plan: role-os `design/s6.3-measurement-plan.md`.

Suite: role-os 1536 / 0 fail. Commits this session: role-os `4d529d9`→…→`63925fc`; readouts `b7d3424`/`8534d8e`/`c67afd2`; gpu-container `3599fc4` (backup branch).

## THE OBJECTIVE — S6.3 attended-GPU measurement campaign

Turn the honest `unverified`/`awaiting` states into measured numbers, edge by edge. **The loop is built; this is GPU execution.** Two payloads (see `design/s6.3-measurement-plan.md`):

1. **Edge transfer deltas** — train the successor cert from base (baseline GPU-steps-to-cert) vs from the foundation adapter; `steps_saved_frac = (baseline − withFoundation)/baseline`, over `n_receipts`. Honest prior: transfer is pair-specific and can be ≤0 (Pruksachatkun 2020) — a measured non-positive delta is a real result. A measured edge flips `unverified → confirmed`.
2. **Technique preview fits** — a fitted data-mixing law (predicted loss/steps + calibration scale) + the replay fraction + measured forgetting, from a handful of SMALL calibration runs.

**First targets (one per attended sitting):** the SDXL-UNet-only → SDXL+text-encoder prerequisite edge (densest pair); the QLoRA-NF4-SFT mixing-law/replay fit (anchor on the S4c 20%-replay receipt).

**Write-back:** measured results → a `measurement.json` (shape in `record_measurement.py` header) → `python scripts/record_measurement.py <file>` → `python scripts/gen_curriculum.py` → `roleos crew --programs` shows it confirmed. The measurement scripts live in `gpu-container/specialist-training/` (alongside the S4/S5 harnesses); each run gets its own preregistered `RUN-PLAN-s6.3-<target>.md` before any eval.

**Engine provisioning:** use **engine-room** (`er` CLI, `E:\AI\engine-room`, over the tensor-engine recipe layer) to stand up the inference engine for the LEEP forward-pass + cert eval — `er rig` / `er preflight <recipe>` then `er provision <recipe> --execute --from <dir> --model <gguf>`. **engine-room's live `--execute` has only been dry-run-proven — its first real run needs Mike's model path + go.**

## Standing constraints (director's law — unchanged)

- **Attended GPU runs only** — no unattended campaigns until Mike revokes.
- **Preflight before ANY GPU run, each item observed fresh:** watchdog HEARTBEAT advancing (launch via pwsh; verify age <10s, then again 15s later) · `powercfg /change standby-timeout-ac 0` · `docker info` if exams follow · long runs under tmux + tee'd log + done-flag (task shells die ~14 min in; the WSL2 process survives task-handle teardown but a bare `wsl -e bash -c '… &'` does NOT — use tmux) · range-crossing monitors, never exact-match · any new eval harness runs a known-good REFERENCE control first · dead trainer → read `E:/AI/training/_watchdog_KILL.log` first.
- **Single lever per attempt; preregister every gate BEFORE any eval; exams stay sealed + hash-pinned; every attempt receipted.**
- **`roleos crew --preview`/`--programs` render `unverified`/`awaiting` honestly** — never fabricate a number; `confirmed` requires receipts.

## Open polish (no GPU; pick up anytime)

- **s4c2 cross-trained badge invisible on the crew sheet** — `record.mjs deriveTechniques` reads `certification.current` (active version only); the s4c2 soup is registered-but-not-promoted under both roles, so its earned cross-trained technique doesn't render. Surface version-level techniques, or note the design intent.
- **prism-verify** — the Ollama-backed groundedness live test is committed LOCAL only (`b8b8588`, not pushed; prism-verify main is PR-gated). Push/PR is Mike's call.
- **Wave candidates** (training-knowledge research wave): joint-SFT-≠-task-vector-addition (S4d), warm-start-preserves-grokking (S4c), CE-vs-flip divergence (S4b), allocator-creep VRAM lesson.
- **Swarm Stages B/C/D** on role-os — optional (PAUSE-STATE.md).
- **Serving real confidence** — make the verify shims return the answer-token logprob as `score` so the S5 drift perf arm (ATC/ECE) goes live for the conformance classifier.

## Orient, then standby for go.
