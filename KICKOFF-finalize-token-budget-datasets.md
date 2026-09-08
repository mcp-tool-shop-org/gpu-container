# Kickoff — Finalize the Token Budget Analyst datasets (pre-training)

**Goal:** regenerate + verify the datasets so the training session can consume them directly.
~5 minutes, no GPU, no training. Run this, get a clean receipt, hand off.

**Where:** `E:/AI/role-os`, branch `token-budget-dataset`, from `tools/token-budget-dataset/`.

## Steps (run in order)

1. **Refresh the corpus** from all current Claude Code transcripts (picks up any new dispatches):
   ```
   python -m harvester.build
   ```
   → writes `dataset/v0.1/` (corpus + train/audit/exam splits + `manifest.json`). Note the record
   count and `manifest.json → hashes.corpus`.

2. **Regenerate the puzzle curriculum:**
   ```
   python -m harvester.puzzles build
   ```
   → writes `dataset/v0.1/puzzles/` (train + exam + `puzzles_manifest.json`). Note the per-rung counts
   and `puzzles_manifest.json → hash`.

3. **Verify green:**
   ```
   python test_harvester.py
   ```
   → must print **`ALL PASS`** (scrub/ANDON gates, contamination check, join, cost-weighting, freeze,
   puzzle self-checks). If not green, stop and fix before handing off.

4. **Write the handoff receipt** `dataset/v0.1/FINAL_STATUS.md` — a short record the training session
   reads first:
   - corpus: N records + corpus hash
   - puzzles: total + by-rung counts + puzzle hash
   - certification exam = `puzzles/puzzles_exam.jsonl` (M puzzles, self-checking)
   - `test_harvester.py` = ALL PASS
   - date

## Done when
- `harvester.build` + `harvester.puzzles build` ran clean; `test_harvester.py` = **ALL PASS**.
- `FINAL_STATUS.md` exists with the counts + hashes above.
- The training session can point at `dataset/v0.1/` (corpus + `puzzles/` + `puzzles_exam.jsonl`) and go.

## Notes
- **Data is local + gitignored (regenerable)** — nothing to push. The harvester *code* is already
  committed (`c0d6a92`). Only commit if you change code, and only when Mike asks.
- **No GPU, no training here** — that's the next kickoff (`KICKOFF-specialist-training.md`, Track E).
- The authoritative design is `tools/token-budget-dataset/DESIGN.md`.

## Standards (per workflow-standards.md)
Regenerate → verify → receipt. ANDON gates are enforced inside `build.py` (secret re-scan +
exam↔train contamination both hard-fail) — #2 covered. Local files only; compensator = `rm -r
dataset/v0.1/` and re-run; all source transcripts read read-only; **no irreversible external action**
(#3 covered, no-skip clean). PIN_PER_STEP: the manifests pin schema + harvester version + hashes (#1).
