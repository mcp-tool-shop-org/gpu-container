# Scorecard

> Snapshot of the Ship Gate audit. Full narrative + path to v1.0.0: [RELEASE_ASSESSMENT.md](RELEASE_ASSESSMENT.md).

**Repo:** gpu-container
**Date:** 2026-06-04 (post B-gate)
**Type tags:** `[all]` `[pypi]` `[container]` `[cli]`
**shipcheck audit:** 17 checked · 4 gaps · 16 skipped · **81% pass rate** · **BETA-READY**

## Assessment

| Category | Score | Notes |
|----------|-------|-------|
| A. Security | 9/10 | SECURITY.md + README threat model; no secrets, no network egress, no telemetry (verified); host-kills opt-in. |
| B. Error Handling | 8/10 | Structured `GpuContainerError` shape + `--debug`/global guard across all 5 CLIs; domain exit codes ratified. |
| C. Operator Docs | 9/10 | README/CHANGELOG/LICENSE/`--help` current; thorough docs/; log-levels SKIP-justified (no secrets). |
| D. Shipping Hygiene | 8/10 | verify script, clean wheel/sdist, `python_requires`, **CI green** (tests + pip-audit). Only version/tag (D2) pending the v1.0.0 release. |
| E. Identity (soft) | 3/10 | Description set; logo, homepage+topics, landing page open; translations SKIP (tool repo). |
| **Overall** | **37/50** | Hard gates A–D all pass except D2 (the release-step tag). Beta-ready. |

## Remaining gaps (4)

1. **D2** (hard) — version in manifest matches tag → resolves at the v1.0.0 bump + tag (release step).
2. **E1** (soft) — logo in README header.
3. **E3** (soft) — landing page (gated on release intent).
4. **E4** (soft) — GitHub homepage + topics (`gh repo edit`).

## Path

All hard gates clear at the v1.0.0 tag (after tomorrow's dogfood swarm). The soft E items are polish and don't block ship.
