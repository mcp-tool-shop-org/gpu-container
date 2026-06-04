# Release-readiness assessment — gpu-container

**Date:** 2026-06-04 · **Audited at:** `main` (Phase 4) · **Repo:** `mcp-tool-shop-org/gpu-container` (**PRIVATE**)
**Method:** `npx @mcptoolshop/shipcheck` (init + audit) against the 31-item Ship Gate, plus direct verification (secrets scan, packaging build, `--help`, GitHub metadata).

> **This report is the deliverable.** The release itself — making the repo public, bumping to v1.0.0, tagging, and any publish — is a **separate, owner-approved step**. Nothing in this assessment changed repo visibility or published anything.

## Verdict

**Not yet v1.0.0-ready, but close, with a clear path.** `shipcheck audit` reports **64%** (14 checked · 8 gaps · 15 skipped). The product is functionally strong and the security/packaging/docs posture is good; the remaining hard-gate gaps are **2 release-step items** (version/tag, CI commit) and **3 code/justify decisions** (structured errors, `--debug`, log levels). Of those three, two are genuinely worth doing and one is a reasonable documented-SKIP.

## Scorecard

### Objective (shipcheck audit, 2026-06-04)

| | Count |
|---|---|
| Checked | 14 |
| Gaps (unchecked) | 8 |
| Skipped (non-applicable / justified) | 15 |
| **Pass rate** | **64%** |

### Category assessment (/10)

| Category | Score | Notes |
|---|---|---|
| A. Security | 9 | SECURITY.md filled; README threat model; **no secrets, no network egress, no telemetry** (verified); host-kills are opt-in. |
| B. Error Handling | 5 | Meaningful, documented exit codes everywhere; but no structured error shape (B1) and no `--debug`/global handler (B3). |
| C. Operator Docs | 8 | README/CHANGELOG/LICENSE/`--help` all current; docs/ is thorough (Track B). Only formal log levels (C5) missing. |
| D. Shipping Hygiene | 6 | verify script, clean wheel+sdist, `python_requires` done; CI (D3) + version/tag (D2) pending; dependabot SKIP per org rule. |
| E. Identity (soft) | 3 | Description set; logo, landing page, homepage+topics still open; translations SKIP (tool repo). |
| **Overall** | **31/50** | Hard-gate axes average ~7/10; the gaps are well-understood and mostly mechanical. |

## What's strong (no action needed)

- **Security posture is genuinely clean** — scanned: no hardcoded secrets; **zero outbound network** in the package (the only subprocesses are local `nvidia-smi`/`fio`/`llama-*`/`wsl`/`docker`); no telemetry. Dangerous host actions are opt-in via `--on-breach`.
- **Packaging is clean** — `python -m build` produces a valid sdist + wheel; `requires-python = ">=3.10"`.
- **Docs are thorough** — README (front-door), CLI reference, quickstart, architecture, MoE-lane, de-risk methodology, ADR-0001; `--help` accurate for all 5 commands; 0 broken internal links.
- **A verify script exists and passes** — `python scripts/verify.py` runs the 85-test suite + a 5-command CLI smoke.

## Gap list

| # | Item | Gate | Severity | Effort | Recommendation |
|---|---|---|---|---|---|
| 1 | **Structured error shape** (`code`/`message`/`hint`/…) | B1 (hard) | Medium | ~M | A lightweight `GpuContainerError(code, message, hint)` + consistent stderr formatting across the 5 CLIs. Errors today are `ERROR: <msg>` + exit codes — clear but unstructured. **Fix (lightweight).** |
| 2 | **No raw stack traces without `--debug`** | B3 (hard) | Medium | ~S | Add a shared top-level `try/except` in each `main()` that prints a clean one-liner and exits non-zero unless `--debug` is set. Common paths are already guarded; this catches the unexpected (e.g. malformed input JSON). **Fix.** |
| 3 | **Logging levels** (silent/normal/verbose/debug) | C5 (hard) | Low | ~S | No secrets exist to redact (local tool); the JSON→stdout / human→stderr split already separates machine/human output. **Document-justify as SKIP**, or add a minimal `--quiet`/`--verbose`. Lowest priority. |
| 4 | **Version matches git tag** | D2 (hard) | — | trivial | **Release step:** bump `0.1.0 → 1.0.0` and tag `v1.0.0` at release. v0.x promotes to v1.0.0 (never patch-bump). Gated on the release decision. |
| 5 | **Dependency scanning in CI** | D3 (hard) | Low | done-pending-commit | `.github/workflows/ci.yml` is **drafted** (pytest matrix 3.11/3.12 + `pip-audit`). Resolves the moment it's committed + pushed. Gated on the Actions-spend decision (private org repo). |
| 6 | **Logo in README header** | E1 (soft) | Low | ~S | Generate one (the `make-image` path). Doesn't block ship. |
| 7 | **Landing page** | E3 (soft) | Low | ~M | The Starlight handbook (full-treatment Phase 3). **Gated on release intent** — deferred until you decide public/v1.0.0. |
| 8 | **GitHub metadata: homepage + topics** | E4 (soft) | Low | trivial | Description is set; homepage + topics are empty. Fix: `gh repo edit mcp-tool-shop-org/gpu-container --homepage <url> --add-topic llm,moe,gpu,inference,vram,offload,llama-cpp` (an outward change — left for you). |

### One item to ratify, not fix

- **Exit-code convention (B2):** marked **SKIP** because the CLIs deliberately use **domain ANDON verdict codes** (`plan` 0/3 · `receipt` 0/3/4/2 · `concentration` 0/5/2 · `watchdog` 0/5/7), documented in [docs/cli.md](docs/cli.md), rather than shipcheck's generic `0/1/2/3`. These are richer and more useful for this product (a refusal vs a ship vs a bandwidth-model error are distinct, scriptable outcomes). **Please ratify** this divergence (it's intentional) or ask for the generic convention.

## Path to v1.0.0

1. **Commit the Track-C closes** (this session, on disk now): `SECURITY.md`, `CHANGELOG.md`, `SHIP_GATE.md`, `SCORECARD.md`, README "Privacy & safety", `scripts/verify.py`, `.github/workflows/ci.yml`, this report. → closes A1/A2/A4/C2/C3/D1.
2. **Decide CI** — commit + push `ci.yml` (accepts the Actions-spend on the private org repo). First green run closes **D3** and gives you the `gh run list` signal shipcheck wants.
3. **Address B-gates** — implement B3 (`--debug` + global handler, small) and B1 (lightweight structured errors, medium); ratify B2; document-justify or implement C5.
4. **Soft polish** (optional for "whole"): logo (E1), GitHub homepage+topics (E4), and — if releasing publicly — the Starlight landing page/handbook (E3).
5. **Release step (owner-approved):** flip visibility to public *(if that's the intent — canonical-ownership puts tools in the public org)*, bump `0.1.0 → 1.0.0`, tag `v1.0.0`, update the README scorecard to the post-fix audit result, then publish (PyPI/ghcr only if you want those channels).

After steps 1–3, a re-run of `shipcheck audit` should clear all **hard** gates (A–D); E is soft and doesn't block.

## Closed this session (on disk, uncommitted)

`SECURITY.md` (filled), README "Privacy & safety" (A2/A4), `CHANGELOG.md`, `scripts/verify.py` (D1, runs green), `.github/workflows/ci.yml` (drafted), `SHIP_GATE.md` + `SCORECARD.md` + this `RELEASE_ASSESSMENT.md`. None committed — awaiting your go.

## Decisions reserved for you

- **Release intent / visibility** (gate C0): the repo is PRIVATE. "Release" for a tool repo means public org + v1.0.0 — **not done without your explicit go.**
- **CI commit** (Actions spend on a private org repo) — step 2 above.
- **B-gate scope**: fix B1+B3 (recommended) vs justify; ratify B2; C5 fix-vs-justify.
- **GitHub metadata** (`gh repo edit`) — an outward change, left for you.

## CI assessment (detail)

The repo has **no CI today**. The drafted [`.github/workflows/ci.yml`](.github/workflows/ci.yml) is right-sized per the org GitHub-Actions rules: **paths-gated** (`pyproject.toml`, `gpu_container/**`, `tests/**`, `scripts/**`, `.github/workflows/**`), `workflow_dispatch` fallback, `concurrency` with `cancel-in-progress`, `ubuntu-latest` only, a **2-version matrix** (3.11/3.12) running `scripts/verify.py`, plus a small `pip-audit` dependency-scan job (3 jobs total, ≤6). One workflow file (≤2). No release/publish workflow is included (add one only if you want PyPI/ghcr publishing). Committing it consumes org Actions minutes — hence it's gated on your decision.
