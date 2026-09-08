# Kickoff — create `role-os-rollout` on GitHub + connect it to role-os

**Goal:** create the **private** GitHub repo `mcp-tool-shop-org/role-os-rollout`, push the existing local
content (cleaned), and verify role-os's README link resolves — then wire the role-os ↔ rollout connection
as needed. **Single-task scope.** Authored 2026-06-08.

## Rig (overrides any F:/AI path)
Robot rig: drives **C and E only — no D:/F:/G:**. Read every `F:/AI/...` as `E:/AI/...`. Local repo lives at
`E:/AI/role-os-rollout/`. Shell is PowerShell (use the Bash tool for git/gh).

## Why this exists (the defect being fixed)
`role-os`'s README — **live in the published v2.8.0 release, across all 8 locales** — links to
`https://github.com/mcp-tool-shop-org/role-os-rollout` as "a separate private repo" for org-wide rollout
state. **That GitHub repo does not exist** (`gh repo view` → 404), so the link is dead. The two-repo split
(product = `role-os`; operational-state = `role-os-rollout`) was scaffolded **locally** — `E:/AI/role-os-rollout`
is a real git repo with content, commits, and `origin` already set to the rollout URL — but the
`gh repo create` step never happened, so it was never pushable. This kickoff creates the remote and makes
the link real.

## What the repo holds (the role-os ↔ rollout contract)
- **Operational state / governance:** `DECISIONS.md`, `DOCTRINE.md`, `ROLLOUT-DOCTRINE-v1.md`, `QA.md`,
  `WORK-QUEUE.md`, `TRANSITION.md`, `REPO-INDEX.md`.
- **Per-repo packets:** `repos/<repo>/` for ~20 org repos (queue, decisions, audit records, lock packets).
- **`role-os` consumes from it:** per `src/specialist/conformance-consult.mjs` + `src/hooks.mjs`, the
  per-tool **conformance contract catalog** (`tool-contracts.json`) and per-repo knowledge are described as
  "the rollout's per-tool knowledge base." The rollout is also the natural home for per-repo
  `capabilities.json` grant manifests (the new capability-gate, v2.8.0). **role-os = the product; rollout =
  operational state** (README line ~101).

## Repo-first hard rule (must all be true before "done")
GitHub repo exists (org) · local is a git repo (it is) · `origin` correct (it is) · initial clean push visible ·
default branch `main`. Verify with `git remote -v` + `git branch --show-current`.

## Canonical ownership
Org: **`mcp-tool-shop-org`**. **Visibility: PRIVATE** (the README says "separate private repo"; it holds audit
records + operational state — not a public product). No CI needed beyond an optional Pages build for its `site/`.

## ⚠ Load-bearing preflight — the local repo is NOT push-ready
Do NOT push as-is. Current state (verified 2026-06-08):
- **`node_modules` is tracked: ~12,520 files**; `dist/` + `.astro` build artifacts: ~4,171 files (of ~12,741
  total tracked — the repo is ~98% junk, ~151M on disk).
- **No `.gitignore`.**
- Working tree is **dirty** (uncommitted `site/dist/...` deletions).

Pushing now would create a bloated 151M repo whose every clone drags node_modules. **Clean it first.**

## Steps

### 0. Preflight (read-only)
```bash
gh repo view mcp-tool-shop-org/role-os-rollout 2>&1 | head -2   # expect: 404 (does not exist)
cd /e/AI/role-os-rollout && git remote -v && git branch --show-current && git status --short | head
git ls-files | grep -c node_modules                            # expect ~12520
```

### 1. Make it push-ready — RECOMMENDED: clean history (never-pushed → free to do once)
Add a `.gitignore`:
```
node_modules/
dist/
.astro/
.polyglot-cache.json
*.log
.DS_Store
```
Then start history clean (preserves the **current** content of all real docs; drops the junk + bloat — there
is no remote/clone depending on the old history):
```bash
cd /e/AI/role-os-rollout
git checkout -- . 2>/dev/null; git rm -r --cached node_modules dist .astro 2>/dev/null
git checkout --orphan clean-main
git add -A                                  # .gitignore now excludes the junk
git commit -m "chore: role-os-rollout — operational-state repo (clean initial history)"
git branch -D main && git branch -m main
```
**Fallback (preserve history, accept bloat):** `git rm -r --cached node_modules dist .astro && git add .gitignore && git commit -m "chore: untrack node_modules + build artifacts"` — keeps the old commits but the bloat stays in history. Prefer the clean approach.

**Gate:** `git ls-files | wc -l` should now be small (docs + repos/ packets + lean site/src, **no** node_modules/dist).

### 2. Create the private remote
```bash
gh repo create mcp-tool-shop-org/role-os-rollout --private \
  --description "Role OS operational state — rollout queue, decisions, audit records, per-repo lock packets + tool-contract catalogs. role-os is the product; this is operational state."
```
(`origin` is already set to this URL; if `gh repo create` adds a remote, keep the existing `origin`.)

### 3. Push + default branch
```bash
git push -u origin main
gh repo edit mcp-tool-shop-org/role-os-rollout --default-branch main
```

### 4. Verify (repo-first + the link)
```bash
gh repo view mcp-tool-shop-org/role-os-rollout --json name,visibility,defaultBranchRef
# the README link must resolve for an authenticated org member (private repo → 200/redirect, not 404):
gh api repos/mcp-tool-shop-org/role-os-rollout >/dev/null && echo "repo resolves"
```
Note: a PRIVATE repo's README link returns 404 to anonymous/public visitors — confirm with Mike whether the
link should point at a private repo (org-member-only) or whether a small **public** stub is wanted so the
published role-os README link isn't a public 404. **Decision needed (see Open question).**

### 5. Connect to role-os as needed
- Confirm role-os's README link (line ~101) now resolves for the intended audience.
- If role-os should consume the **tool-contract catalog** from the rollout at runtime, wire the path
  (`conformance-consult.mjs` / `hooks.mjs` load `.claude/role-os/tool-contracts.json`); document whether that
  catalog is sourced from `role-os-rollout/repos/<repo>/` or stays per-consuming-repo. Likely **no code
  change** — the rollout is the authoring home; consuming repos get their own `.claude/role-os/*.json`.
- Optional: per-repo `capabilities.json` grant manifests (capability-gate, v2.8.0) authored under the rollout.

## Open question for Mike (uncertainty-gated)
The published role-os README links a **private** repo, so the link is a **public 404** for non-members.
Options: (a) keep it private, accept the public-404 (operational state shouldn't be public); (b) make the repo
public; (c) keep private + soften the README line to not present a clickable public link. **Default: (a)** —
private, operational state stays private; if the public-404 in the shipped README bothers you, (c) is a
one-line README PR + re-translate. Confirm before changing role-os's README.

## Standards compliance (the six — brief)
- **PIN_PER_STEP 2** — exact commands pinned above. **ANDON 2** — the §1 "Gate" (`git ls-files` lean) halts the
  push if junk remains. **NAMED_COMPENSATORS 3** — table below. **DECOMPOSE 2** — clean/create/push/connect are
  separable. **UNCERTAINTY_GATED 3** — the private-vs-public README question is surfaced contrastively.
  **EXTERNAL_VERIFIER 1** — verification is self-checks (gh/git); no different-family check needed for a repo-create.

### Compensators
| Action | Irreversible? | Compensator | Owner |
|---|---|---|---|
| `gh repo create ... --private` | No | `gh repo delete mcp-tool-shop-org/role-os-rollout --yes` | user |
| `git push -u origin main` (clean history) | Mostly | repo is private + freshly created → `gh repo delete` + recreate, or force-push a corrected tree | user |
| role-os README change (if option c) | No (pre-merge) | `git revert <sha> && git push` + re-translate | advisor/user |

## Definition of done
- `gh repo view mcp-tool-shop-org/role-os-rollout` resolves; private; default branch `main`; lean tree (no
  node_modules/dist in `git ls-files`).
- role-os README link resolves for the intended audience (and the private-vs-public decision is made).
- The role-os ↔ rollout connection (tool-contract catalog / capabilities authoring home) is documented or wired.
