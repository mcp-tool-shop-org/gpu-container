# Scorecard

> Snapshot of the Ship Gate audit. Full narrative + path to v1.0.0: [RELEASE_ASSESSMENT.md](RELEASE_ASSESSMENT.md).

**Repo:** gpu-container
**Date:** 2026-06-04
**Type tags:** `[all]` `[pypi]` `[container]` `[cli]`
**shipcheck audit:** 14 checked · 8 gaps · 15 skipped · **64% pass rate**

## Assessment

| Category | Score | Notes |
|----------|-------|-------|
| A. Security | 9/10 | SECURITY.md + README threat model; no secrets, no network egress, no telemetry (verified); host-kills opt-in. |
| B. Error Handling | 5/10 | Documented domain exit codes everywhere; missing structured error shape (B1) + `--debug`/global handler (B3). |
| C. Operator Docs | 8/10 | README/CHANGELOG/LICENSE/`--help` current; thorough docs/; only formal log levels (C5) open. |
| D. Shipping Hygiene | 6/10 | verify script + clean wheel/sdist + `python_requires`; CI (D3) + version/tag (D2) pending; dependabot SKIP per org rule. |
| E. Identity (soft) | 3/10 | Description set; logo, homepage+topics, landing page open; translations SKIP (tool repo). |
| **Overall** | **31/50** | Close. Gaps are mostly mechanical or release-step. |

## Key Gaps

1. **B1** — structured error shape (`code`/`message`/`hint`) across the 5 CLIs (lightweight fix).
2. **B3** — no raw stack without `--debug` (shared top-level handler + flag).
3. **D2 + D3** — version/tag bump to v1.0.0 (release step) and CI (`ci.yml` drafted, commit pending).

## Remediation Priority

| Priority | Item | Estimated effort |
|----------|------|-----------------|
| 1 | Commit Track-C closes (SECURITY/CHANGELOG/verify/ci.yml/threat model) + push CI | trivial (decision) |
| 2 | B3 (`--debug` + global handler), then B1 (structured errors); ratify B2 | S → M |
| 3 | v1.0.0 bump + tag + visibility decision; soft polish (logo, homepage/topics, landing page) | release step |

## Post-Remediation

Re-run `npx @mcptoolshop/shipcheck audit` after Priority 1–2; hard gates A–D should clear (E is soft). Update the README scorecard to the post-fix result at release.
