# gpu-container: how it works

Mapped at 2026-10-01 from commit 6873773 by Atlas 1.24.0.

## What this is

10 parts, mostly Python (33 files), JavaScript (3), CSS (2), TypeScript (2) and Astro (1). Work enters through 10 doors; the busiest is CI, which reaches 3 parts. It publishes to PyPI, gpu-container to npm, and a container image. It deploys a site to GitHub Pages. People run gpu-container, gpu-container-concentration, gpu-container-plan, gpu-container-profile, gpu-container-receipt and gpu-container-watchdog.

## What changed since the last map

This is the first map.

## What comes in

1. **CI.** On a pull request touching 9 paths; on a push touching 9 paths; or by hand. Runs gpu_container/watchdog.py, scripts/verify.py and tests/; checks gpu_container/.
2. **Release.** When a release is published; or by hand. Runs gpu_container/profiler/cli.py; builds gpu_container/__main__.py; checks gpu_container/; packs LICENSE, README.md and pyproject.toml into an image.
3. **Deploy site to GitHub Pages.** On a push to main touching 2 paths; or by hand. Runs site/astro.config.mjs and site/src/.
4. **gpu-container** (a command people run, from npm/package.json). Runs npm/bin/gpu-container.js.
5. **gpu-container** (a command people run, from pyproject.toml). Runs gpu_container/__main__.py.
6. **gpu-container-concentration** (a command people run). Runs gpu_container/planner/concentration_cli.py.
7. **gpu-container-plan** (a command people run). Runs gpu_container/planner/cli.py.
8. **gpu-container-profile** (a command people run). Runs gpu_container/profiler/cli.py.
9. **gpu-container-receipt** (a command people run). Runs gpu_container/planner/receipt_cli.py.
10. **gpu-container-watchdog** (a command people run). Runs gpu_container/watchdog.py.

## What happens through CI

1. The workflow runs gpu_container/watchdog.py in gpu_container, scripts/verify.py in scripts and tests/ in tests; it checks gpu_container/ in gpu_container.

## Who reads the results

CI writes nothing this map can see.

## The other doors

**Release** runs gpu_container/profiler/cli.py, checks gpu_container/, packs LICENSE, README.md and pyproject.toml into an image, publishes to PyPI, gpu-container to npm, and a container image, and builds gpu_container/__main__.py into binaries for darwin-arm64, linux-x64 and win-x64 and uploads them to the release.

**Deploy site to GitHub Pages** runs site/astro.config.mjs and site/src/, and deploys the site.

**gpu-container** (a command people run, from npm/package.json) runs npm/bin/gpu-container.js.

**gpu-container** (a command people run, from pyproject.toml) runs gpu_container/__main__.py.

**gpu-container-concentration** (a command people run) runs gpu_container/planner/concentration_cli.py.

**gpu-container-plan** (a command people run) runs gpu_container/planner/cli.py.

**gpu-container-profile** (a command people run) runs gpu_container/profiler/cli.py.

**gpu-container-receipt** (a command people run) runs gpu_container/planner/receipt_cli.py.

**gpu-container-watchdog** (a command people run) runs gpu_container/watchdog.py.

## What breaks what

- **gpu_container** is imported by 1 part (scripts), and by 1 more only from tests, is run as a child process by 1 part (scripts), and sits on the path of 8 doors.
- **tests** is run as a child process by 1 part (scripts) and sits on the path of 1 door.

## What tends to change together

- **gpu_container/__init__.py** and **npm/bin/gpu-container.js** changed together in 4 of 6 commits, though neither part imports the other.

Confidence is low: fewer than 20 source files reach 10 revisions in the window.

Window: 180 days; a pair counts from 3 shared commits, since 0 source files reach 10 revisions; the floor rises to 10 when 25 do.

## What no test touches

- **npm** is imported by no test.
- **scripts** is imported by no test.

## Written but never read

No place this map can see is written, so none goes unread.

## Helpers that look duplicated

No two parts export a helper that looks alike.

## Generated, never hand-edited

Nothing in this repository writes to a tracked place this map can see.

## Hand-authored

People write .claude/, .github/, assets/, docs/, the repository root and site/; 4 writes with paths built at run time may land here.

## Where to start

.github/workflows/ci.yml → gpu_container/watchdog.py → gpu_container/errors.py

Read those in order to follow one pull request end to end.

## What this map cannot see

- 2 imports could not be resolved: `.claude/hooks/pre-tool-use.mjs` imports `../../E:/AI/role-os/src/hooks.mjs`, which is not in this repository; `gpu_container/__main__.py` imports a path built at run time.
- 4 writes and 5 reads use paths built at run time and are not named here.
- 11 writes and 12 reads go to a path their caller passes, not to this repository.
- Statistics confidence is low: fewer than 20 source files reach 10 revisions in the window.

Regenerate with `npx --yes @dogfood-lab/atlas map`.
