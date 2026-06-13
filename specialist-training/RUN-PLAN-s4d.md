# S4d run plan — untraining experiment, design A (attended)

**Status:** preregistered 2026-06-12 BEFORE any merge or eval; director present, go given.
**Question:** after JOINT training, do the parent task vectors remain linearly recoverable?
Concretely: does subtracting the conformance task vector from the scratch-joint adapter
RECOVER budgeter L2 (the grokked, fragile rung)?
**Substrate:** `budgeter-conformance-joint-soup` (attempt #3 — trained from scratch on the
50/50 mix; exam L2 0.722/0.463, budgeter flip 0.669). The only jointly-trained adapter NOT
warm-started from a parent, so negation here is an experiment, not algebra. (On linear
merges negation is exact by construction — S4b note; on the warm-started s4c2 soup,
"subtract acquisition" reduces to interpolation toward the budgeter parent. This substrate
is the clean one.)

## Standards compliance

| Standard | Score | Evidence |
|---|---|---|
| PIN_PER_STEP | 2 | Exact commands pinned below; proxy item selection deterministic (`random.Random(7)`, same 30 pairs as S4c); parent adapters + λ values named; reports written per merge. |
| ANDON_AUTHORITY | 2 | Reference control runs FIRST in the proxy; REF flip < 0.867 halts the run before any negated number is read. Log-stall monitor (no new bytes > 20 min → investigate). |
| NAMED_COMPENSATORS | 2 | No irreversible actions: registry untouched, no publish, no exam unless separately triggered. Undo = `rm -rf` the two merged adapter dirs (owner: this session). GPU spend bounded ~1 h, director-accepted. |
| DECOMPOSE_BY_SECRETS | 2 | Merge op (cross_train.py), eval harness (l2_proxy.py), and receipts (RESULTS.md + ledger) are separate, already-shipped modules; this plan only composes them. |
| UNCERTAINTY_GATED_HUMANS | 2 | Attended run; the sealed-exam step does NOT auto-fire — proxy outcome goes to the director with contrastive framing before any exam. |
| EXTERNAL_VERIFIER | 2 | Grader is deterministic regex scoring vs gold answers (not the model judging itself); exams remain sovereign over any proxy claim. |

## Design (single lever: negation coefficient λ)

Negated adapter: `ΔW(joint-soup) − λ·ΔW(conformance-14b-soup-v0.2)`, λ ∈ {0.5, 1.0},
via `cross_train.py --method add --lam-a 1.0 --lam-b -λ`. Rank 32 (sum of parent ranks —
SVD there is lossless; r16 truncation would corrupt the result, residual was 0.41+ in S4).

**Serving-scale parity (the trap, fixed in design):** all parents are r16/α32/rsLoRA →
PEFT-effective scale 32/√16 = **8**. The proxy loads via PEFT, NOT llama.cpp, so the prior
runs' `--alpha 64` GGUF convention does NOT apply — at r32 it would load 64/√32 ≈ 11.3,
1.41× over-driven. The merged config must carry **α = 8·√32 = 45.254834** (`use_rslora`
true, copied from parent A). Post-merge check: load each merged adapter, print its scaling,
assert ≈ 8.0 before any eval.

## Measurements (one proxy run, 4 adapters, exam sealed)

L2 TRAIN proxy (`l2_proxy.py`, 30 contrast pairs, thinking enabled), in this order:

1. `ref`   = budgeter-14b600-soup — harness control. S4c measured 0.967/0.933 on these pairs.
2. `base`  = budgeter-conformance-joint-soup — the un-negated baseline.
3. `neg05` = λ=0.5 negation.
4. `neg10` = λ=1.0 negation.

Caveat acknowledged up front: the proxy is TRAIN-split (joint-soup saw these rows in
training), so it is a basin/recovery signal, not a generalization claim — exams stay
sovereign. No conformance train-proxy exists; conformance removal is unmeasured at this
stage by design.

## Preregistered decision rules (before any number is seen)

- **Harness gate (ANDON):** REF flip ≥ 0.867 (within 2 pairs of S4c's 0.933) or halt —
  do not interpret anything downstream.
- **Recovery signal (H1):** flip(neg_best) ≥ flip(base) + 0.10 (≥ 3 pairs). Direction of
  the dose-response (0.5 vs 1.0) is part of the finding.
- **No-recovery (H0):** both λ within ±0.10 of base — joint training entangled the skills;
  the parent vector is no longer a clean removal handle. **Honest prior: this is the
  expected outcome** — S4b showed L2's grokked circuit survives no tested weight-space
  superposition; negation is also a weight-space perturbation.
- **Collapse:** flip(neg10) ≤ flip(base) − 0.10 — negation damages L2 too (the conformance
  vector overlaps structure L2 depends on in the joint substrate). A different, equally
  receipted entanglement finding.
- **Ceiling contingency:** if flip(base) ≥ 0.90 the proxy cannot show recovery (train-split
  memorization); report degradation behavior only and put the exam decision to the director.
- **Exam trigger (director-gated, not automatic):** flip(neg_best) ≥ 0.80 AND recovery
  signal → propose single-shot budgeter + conformance exams on neg_best (the conformance
  exam then measures removal completeness). Receipted as `untraining-experiment`, NOT
  `certification-attempt` — nothing here registers; no λ-tuning against exams (Goodhart).

## Commands (WSL, bp-env; pinned)

```bash
source ~/bp-env/bin/activate
cd /mnt/e/AI/gpu-container/specialist-training
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# merges (~minutes each) + reports
python cross_train.py /mnt/e/AI-Models/adapters/joint-soup-neg-conf-l05 \
  /mnt/e/AI-Models/adapters/budgeter-conformance-joint-soup \
  /mnt/e/AI-Models/adapters/conformance-14b-soup-v0.2 \
  --method add --lam-a 1.0 --lam-b -0.5 --rank 32 --alpha 45.254834 \
  --report runs/untrain-neg05.json
python cross_train.py /mnt/e/AI-Models/adapters/joint-soup-neg-conf-l10 \
  /mnt/e/AI-Models/adapters/budgeter-conformance-joint-soup \
  /mnt/e/AI-Models/adapters/conformance-14b-soup-v0.2 \
  --method add --lam-a 1.0 --lam-b -1.0 --rank 32 --alpha 45.254834 \
  --report runs/untrain-neg10.json

# proxy sweep under tmux (≈1 h), tee'd log + done-flag
bash run_s4d_proxy.sh   # ref → base → neg05 → neg10, logs/s4d_proxy.log, .DONE flag
```

Preflight (each observed fresh, never assumed): watchdog HEARTBEAT age < 10 s twice 15 s
apart; `powercfg /change standby-timeout-ac 0`; tmux session (task shells die ~14 min in);
docker NOT required (no exam in this phase).

## Receipts

- `runs/untrain-neg05.json`, `runs/untrain-neg10.json` (compatibility readout + merge report)
- `logs/s4d_proxy.log` (full proxy output, tee'd)
- RESULTS.md S4d section (whatever the outcome — failure is a designed outcome)
- role-os all-attempts ledger: events kind `untraining-experiment` (role Token Budget
  Analyst; mirrored to Tool-Call Conformance only if exams run)
- Research grounding inherited from the design lock (findings 10–13: Ilharco
  arXiv:2212.04089 negation; TIES interference readout; small-scale fragility) — no new
  study-swarm; the question and method were preregistered in the S4 design.
