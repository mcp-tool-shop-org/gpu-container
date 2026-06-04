# Ship Gate

> No repo is "done" until every applicable line is checked.
> Copy this into your repo root. Check items off per-release.

**Tags:** `[all]` every repo · `[npm]` `[pypi]` `[vsix]` `[desktop]` `[container]` published artifacts · `[mcp]` MCP servers · `[cli]` CLI tools
**This repo:** `[all]` `[pypi]` `[container]` `[cli]` (5 console scripts) — audited 2026-06-04.

---

## A. Security Baseline

- [x] `[all]` SECURITY.md exists (report email, supported versions, response timeline) (2026-06-04)
- [x] `[all]` README includes threat model paragraph (data touched, data NOT touched, permissions required) (2026-06-04 — "Privacy & safety")
- [x] `[all]` No secrets, tokens, or credentials in source or diagnostics output (2026-06-04 — scanned clean)
- [x] `[all]` No telemetry by default — state it explicitly even if obvious (2026-06-04 — no network egress in code; stated in README + SECURITY)

### Default safety posture

- [x] `[cli|mcp|desktop]` Dangerous actions (kill, delete, restart) require explicit `--allow-*` flag (2026-06-04 — host-level kills are opt-in via `--on-breach wsl-shutdown|docker-stop|kill`; defaults are `alert`/`kill-job`-soft, never a host kill)
- [x] `[cli|mcp|desktop]` File operations constrained to known directories (2026-06-04 — writes only to user-specified output paths; no traversal)
- [ ] `[mcp]` Network egress off by default — SKIP: not an MCP server (and verified: zero outbound network in the package)
- [ ] `[mcp]` Stack traces never exposed — structured error results only — SKIP: not an MCP server (CLI analog tracked at B3)

## B. Error Handling

- [ ] `[all]` Errors follow the Structured Error Shape: `code`, `message`, `hint`, `cause?`, `retryable?` — GAP: CLIs emit `ERROR: <message>` to stderr + exit codes, but not the `{code, message, hint, cause?, retryable?}` shape. See RELEASE_ASSESSMENT.md (P1).
- [ ] `[cli]` Exit codes: 0 ok · 1 user error · 2 runtime error · 3 partial success — SKIP: deliberately uses domain ANDON verdict codes documented in docs/cli.md (plan 0/3, receipt 0/3/4/2, concentration 0/5/2, watchdog 0/5/7) — a richer, stable scriptable contract. Flagged for ratification in RELEASE_ASSESSMENT.md.
- [ ] `[cli]` No raw stack traces without `--debug` — GAP: common error paths are guarded, but there is no top-level handler or `--debug` flag, so an unexpected exception (e.g. a malformed input file) can surface a traceback. See RELEASE_ASSESSMENT.md (P1).
- [ ] `[mcp]` Tool errors return structured results — server never crashes on bad input — SKIP: not an MCP server
- [ ] `[mcp]` State/config corruption degrades gracefully (stale data over crash) — SKIP: not an MCP server
- [ ] `[desktop]` Errors shown as user-friendly messages — no raw exceptions in UI — SKIP: not a desktop app
- [ ] `[vscode]` Errors surface via VS Code notification API — no silent failures — SKIP: not a VS Code extension

## C. Operator Docs

- [x] `[all]` README is current: what it does, install, usage, supported platforms + runtime versions (2026-06-04 — refreshed in Track B)
- [x] `[all]` CHANGELOG.md (Keep a Changelog format) (2026-06-04)
- [x] `[all]` LICENSE file present and repo states support status (2026-06-04 — MIT LICENSE; support status in SECURITY.md)
- [x] `[cli]` `--help` output accurate for all commands and flags (2026-06-04 — argparse-generated; verified + smoke-tested by scripts/verify.py)
- [ ] `[cli|mcp|desktop]` Logging levels defined: silent / normal / verbose / debug — secrets redacted at all levels — GAP (low priority): no formal `--quiet`/`--verbose`/`--debug`; de-facto split is JSON→stdout, human notes→stderr; no secrets exist to redact (local tool). See RELEASE_ASSESSMENT.md (P2).
- [ ] `[mcp]` All tools documented with description + parameters — SKIP: not an MCP server
- [ ] `[complex]` HANDBOOK.md: daily ops, warn/critical response, recovery procedures — SKIP: not a background daemon / stateful service; operational guidance lives in docs/quickstart.md + docs/cli.md

## D. Shipping Hygiene

- [x] `[all]` `verify` script exists (test + build + smoke in one command) (2026-06-04 — scripts/verify.py; runs the suite + a 5-command CLI smoke, `--build` adds the wheel/sdist)
- [ ] `[all]` Version in manifest matches git tag — PENDING RELEASE: manifest is 0.1.0, no tag yet; resolves at the v1.0.0 bump + tag (D2 in RELEASE_ASSESSMENT.md)
- [ ] `[all]` Dependency scanning runs in CI (ecosystem-appropriate) — PENDING: .github/workflows/ci.yml drafted (pip-audit job), awaiting the commit/Actions-spend decision
- [ ] `[all]` Automated dependency update mechanism exists — SKIP: org GitHub-Actions rule forbids dependabot unless explicitly requested; deps are minimal (optional psutil/numpy/nvidia-ml-py, dev pytest)
- [ ] `[npm]` `npm pack --dry-run` includes: dist/, README.md, CHANGELOG.md, LICENSE — SKIP: not an npm package
- [x] `[npm]` `engines.node` set · `[pypi]` `python_requires` set (2026-06-04 — requires-python = ">=3.10")
- [x] `[npm]` Lockfile committed · `[pypi]` Clean wheel + sdist build (2026-06-04 — `python -m build` produced gpu_container-0.1.0 sdist + wheel cleanly)
- [ ] `[vsix]` `vsce package` produces clean .vsix with correct metadata — SKIP: not a VS Code extension
- [ ] `[desktop]` Installer/package builds and runs on stated platforms — SKIP: not a desktop app

## E. Identity (soft gate — does not block ship)

- [ ] `[all]` Logo in README header — GAP (soft): no logo yet
- [ ] `[all]` Translations (polyglot-mcp, 8 languages) — SKIP: tool repo; translations are a marketing-repo convention
- [ ] `[org]` Landing page (@mcptoolshop/site-theme) — GAP (soft): none yet; gated on release intent (Starlight handbook)
- [ ] `[all]` GitHub repo metadata: description, homepage, topics — PARTIAL: description set; homepage + topics empty (fix: `gh repo edit` — see RELEASE_ASSESSMENT.md)

---

## Gate Rules

**Hard gate (A–D):** Must pass before any version is tagged or published.
If a section doesn't apply, mark `SKIP:` with justification — don't leave it unchecked.

**Soft gate (E):** Should be done. Product ships without it, but isn't "whole."

**Checking off:**
```
- [x] `[all]` SECURITY.md exists (2026-02-27)
```

**Skipping:**
```
- [ ] `[pypi]` SKIP: not a Python project
```
