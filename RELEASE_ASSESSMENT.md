# Release-readiness assessment — gpu-container

**Date:** 2026-06-04 · **Audited at:** `main` (Phase 4) · **Repo:** `mcp-tool-shop-org/gpu-container` (**PRIVATE**)
**Method:** `npx @mcptoolshop/shipcheck` (init + audit) against the 31-item Ship Gate, plus direct verification (secrets scan, packaging build, `--help`, GitHub metadata).

> **This report is the deliverable.** The release itself — making the repo public, bumping to v1.0.0, tagging, and any publish — is a **separate, owner-approved step**. Nothing in this assessment changed repo visibility or published anything.

## Verdict

**BETA-READY.** After the post-audit B-gate pass, `shipcheck audit` reports **81%** (17 checked · 4 gaps · 16 skipped). **All hard gates A–D pass except D2** (version-matches-tag), which is the v1.0.0 release step itself. The remaining three gaps are all **soft** (logo, landing page, GitHub metadata). Plan: ship as a beta now, dogfood-swarm tomorrow, then bump to v1.0.0 (which closes D2).

*(Audited at 64% pre-fix; this report reflects the current post-fix state. The B-gates — structured errors B1, `--debug`/no-raw-stack B3 — and CI dep scanning D3 were closed this session.)*

## Scorecard

### Objective (shipcheck audit, 2026-06-04, post B-gate)

| | Count |
|---|---|
| Checked | 17 |
| Gaps (unchecked) | 4 (1 hard = the release-step tag · 3 soft) |
| Skipped (non-applicable / justified) | 16 |
| **Pass rate** | **81%** |

### Category assessment (/10)

| Category | Score | Notes |
|---|---|---|
| A. Security | 9 | SECURITY.md filled; README threat model; **no secrets, no network egress, no telemetry** (verified); host-kills are opt-in. |
| B. Error Handling | 8 | **Structured `GpuContainerError` shape** (code/message/hint/cause?/retryable?) + `--debug`/global `guard()` across all 5 CLIs; domain exit codes ratified. |
| C. Operator Docs | 9 | README/CHANGELOG/LICENSE/`--help` all current; docs/ thorough; log-levels SKIP-justified (no secrets to redact). |
| D. Shipping Hygiene | 8 | verify script, clean wheel+sdist, `python_requires`, **CI green** (tests 3.11/3.12 + pip-audit). Only version/tag (D2) pending the v1.0.0 release. |
| E. Identity (soft) | 3 | Description set; logo, landing page, homepage+topics still open; translations SKIP (tool repo). |
| **Overall** | **37/50** | Hard gates A–D all pass except the release-step tag (D2). Beta-ready. |

## What's strong (no action needed)

- **Security posture is genuinely clean** — scanned: no hardcoded secrets; **zero outbound network** in the package (the only subprocesses are local `nvidia-smi`/`fio`/`llama-*`/`wsl`/`docker`); no telemetry. Dangerous host actions are opt-in via `--on-breach`.
- **Packaging is clean** — `python -m build` produces a valid sdist + wheel; `requires-python = ">=3.10"`.
- **Docs are thorough** — README (front-door), CLI reference, quickstart, architecture, MoE-lane, de-risk methodology, ADR-0001; `--help` accurate for all 5 commands; 0 broken internal links.
- **A verify script exists and passes** — `python scripts/verify.py` runs the 85-test suite + a 5-command CLI smoke.

## Resolved this session (post-audit B-gate pass)

| Item | Gate | What landed |
|---|---|---|
| **Structured error shape** | B1 | `gpu_container/errors.py` — `GpuContainerError(code, message, hint, cause?, retryable?)` raised across all 5 CLIs; renders `ERROR [CODE]: msg` + hint/cause. |
| **No raw stack without `--debug`** | B3 | A shared `guard()` wraps every CLI `main()`: an unexpected exception prints one clean line + exit 2; the full traceback only with `--debug`. |
| **Dependency scanning in CI** | D3 | `.github/workflows/ci.yml` committed + pushed; first run **green** (tests 3.11/3.12 via verify.py + a `pip-audit` job). |
| **Exit-code convention (ratified)** | B2 | Domain ANDON codes (`plan` 0/3 · `receipt` 0/3/4/2 · `concentration` 0/5/2 · `watchdog` 0/5/7) are deliberate + documented in [docs/cli.md](docs/cli.md); structured errors exit 2. **SKIP-ratified.** |
| **Logging levels (justified)** | C5 | No secrets to redact (verified); output contract is machine→stdout / human→stderr / `--debug` for tracebacks. **SKIP-justified.** |

## Remaining gaps

| Item | Gate | Severity | Recommendation |
|---|---|---|---|
| **Version matches git tag** | D2 (hard) | — | **Release step:** bump `0.1.0 → 1.0.0` and tag `v1.0.0` at the release (after tomorrow's dogfood swarm). The only hard gate still open — by design, it closes when you cut the tag. |
| **Logo in README header** | E1 (soft) | Low | Generate one (the `make-image` path). Doesn't block ship. |
| **Landing page** | E3 (soft) | Low | The Starlight handbook (full-treatment Phase 3). Gated on release intent. |
| **GitHub homepage + topics** | E4 (soft) | Low | Description is set; homepage + topics empty. Fix (outward, left for you): `gh repo edit mcp-tool-shop-org/gpu-container --homepage <url> --add-topic llm,moe,gpu,inference,vram,offload,llama-cpp`. |

## Path to v1.0.0

1. ✅ **Track-C closes committed + pushed** — SECURITY.md, README "Privacy & safety", CHANGELOG.md, scripts/verify.py, this report (main `5da12d3`). Closed A1/A2/A4/C2/D1.
2. ✅ **CI committed + green** — `.github/workflows/ci.yml` runs tests (3.11/3.12) + pip-audit. Closed D3.
3. ✅ **B-gates landed** — structured errors (B1), `--debug`/guard (B3), B2 ratified, C5 justified. (This commit.)
4. ⏳ **Dogfood swarm (tomorrow)** — exercise the beta; fold in findings.
5. ⏳ **Release step (owner-approved):** bump `0.1.0 → 1.0.0`, tag `v1.0.0` (closes **D2** — the last hard gate); decide visibility (canonical-ownership puts tools in the public org); optional soft polish (logo E1, homepage+topics E4, landing page E3); publish to PyPI/ghcr only if you want those channels.

A re-run of `shipcheck audit` is **81%** with all hard gates A–D passing **except D2**, which closes the moment v1.0.0 is tagged.

## Closed this session

Committed + pushed: `SECURITY.md`, README "Privacy & safety", `CHANGELOG.md`, `scripts/verify.py`, `.github/workflows/ci.yml` (CI green), `SHIP_GATE.md`/`SCORECARD.md`/`RELEASE_ASSESSMENT.md`, and the B-gate code (`gpu_container/errors.py` + `--debug`/`guard` across all 5 CLIs + `tests/test_errors.py`). 92 tests green.

## Decisions reserved for you

- **Release intent / visibility** (gate C0): the repo is PRIVATE. "Release" for a tool repo means public org + v1.0.0 — **not flipped without your explicit go.**
- **v1.0.0 bump + tag** — after tomorrow's dogfood swarm; closes the last hard gate (D2).
- **GitHub metadata** (`gh repo edit` homepage + topics) — an outward change, left for you.
- **Soft polish** — logo (E1), landing page / Starlight handbook (E3) if releasing publicly.

*(Resolved already: CI commit + Actions spend; B-gate scope — B1/B3 fixed, B2 ratified, C5 justified.)*

## CI assessment (detail)

The repo has **no CI today**. The drafted [`.github/workflows/ci.yml`](.github/workflows/ci.yml) is right-sized per the org GitHub-Actions rules: **paths-gated** (`pyproject.toml`, `gpu_container/**`, `tests/**`, `scripts/**`, `.github/workflows/**`), `workflow_dispatch` fallback, `concurrency` with `cancel-in-progress`, `ubuntu-latest` only, a **2-version matrix** (3.11/3.12) running `scripts/verify.py`, plus a small `pip-audit` dependency-scan job (3 jobs total, ≤6). One workflow file (≤2). No release/publish workflow is included (add one only if you want PyPI/ghcr publishing). Committing it consumes org Actions minutes — hence it's gated on your decision.
