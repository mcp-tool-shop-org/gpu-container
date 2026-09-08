Kickoff — Verifier specialist: dataset build (target repo = prism-verify)

## What this is

Build the **training dataset** for the first specialist — a local-vLLM adapter that becomes
prism-verify's cheap **`local` family lens backend**. **Dataset only. No training.** The corpus is
handed to [[backpropagate]] for training in a later kickoff.

**Read first:** the architectural lock —
`C:/Users/mikey/.claude/projects/F--AI/memory/specialist-tier-architecture.md`. Then prism-verify's
`design/01-research-grounding.md` (Locks 1–4 + the L1–L4 lens taxonomy) and
`design/04-citation-verification.md` (the existing groundedness/citation path this specialist mirrors).

## The scope decision (locked): v0.1 Verifier = prism's L4 Groundedness lens

prism runs four lenses (L1 Contract Completeness, L2 Cross-Boundary Information Flow, L3 Invariant &
Test-Adequacy, **L4 Groundedness / Hallucination**). Do NOT try to train all four. **v0.1 targets L4
only**, because:
- L4 is "does every load-bearing claim trace to a provided source?" — a claim→evidence→{supported |
  unsupported | abstain} task. This is the **exact** MiniCheck setting (Tang et al., EMNLP 2024,
  arXiv:2404.10774), where a 7B fine-tune **already beats GPT-4o at ~400× lower cost**. The research
  is strongest here.
- It's the highest-frequency, cheapest-to-label lens, and prism already produces L4 verdicts with
  receipts — so the labels partly exist.
- It slots into prism's `local` slot without touching Locks 1–4: prism still wraps the local L4
  backend in family-different routing + reasoning-strip + the submodularity guard. The specialist makes
  the `local` lens *cheap and good*; prism keeps the guarantees.

Other lenses (L1/L2/L3) are later specialists, same pipeline.

## The specialist is a distillation target + a calibration target

Two label sources, two jobs:

1. **Distillation (bulk) — via a CAPTURE SINK, not by mining receipts (confirmed 2026-06-04).** The
   persisted receipt is an audit trail: artifact **hashes** (`pre/post_strip_hash`) + verdict +
   `lens_results` — the `CitationResult` triples (claim ↔ `source_abstract`/`supporting_span` ↔
   `finding_match`) are **never stored**. A read-only probe of the live `~/.prism/receipts.db` found
   **5 dev receipts, 0 recoverable L4 text** — receipts are structurally not a corpus. So distillation
   comes from a NEW opt-in **capture sink** in the engine (`prism/eval/harvest.py`, gated by
   `PRISM_HARVEST_PATH`, default OFF) that writes the clean `(claim, evidence_span, verdict)` record at
   verify time *before* strip-to-hash discards it, **plus a backfill** that re-runs `engine.verify` over
   existing artifact sets (code-review / dogfood / design-doc citations) with the sink on. Receipts are
   the **join/provenance index** (`receipt_id`), not the text source. **Extend prism's existing
   `prism-eval-corpus/v1`** (`prism/eval/corpus.py` — it already has the `public`/`fresh` contamination
   split + a `check_corpus_integrity` ANDON gate + ~two dozen authored L4 seed samples), do NOT invent a
   corpus schema. L4 label map: citation `finding_match` SUPPORTED→supported, CONTRADICTED/NOT_ADDRESSED→
   unsupported (RESOLVED only — existence failures train the existence floor, not L4); groundedness-lens
   PASS→supported, FAIL→unsupported, UNCERTAIN→abstain.
2. **Calibration + hard negatives (the gradient).** Distillation alone overfits to prism's easy cases.
   Add:
   - **MiniCheck-style synthetic hard negatives** — Claim-to-Doc (C2D) and Doc-to-Claim (D2C):
     paraphrase a supported claim, then plant a targeted entity / relation / quantifier swap so it
     becomes *plausible-but-unsupported*. These carry the gradient (the MiniCheck result is almost
     entirely from these, not random negatives). Generate locally (see rig-safety).
   - **Ground-truth outcomes** — dogfood-swarm receipts and code-review confirmed/refuted findings
     where the "finding" was a groundedness claim. These are real labels, not synthetic.

## Dataset contract (what to actually produce)

A versioned corpus of records:

```
{ artifact_id, claim, evidence_span, verdict: "supported"|"unsupported"|"abstain",
  hard_negative: bool, source: "prism-receipt"|"minicheck-c2d"|"minicheck-d2c"|"dogfood"|"code-review",
  producer_family, multi_hop: bool }
```

Rules that the research makes non-negotiable:
- **Balance to the inference-time prior, not 50/50.** Most real claims prism sees are supported, so
  the corpus skews `supported`; then **over-sample hard negatives within the unsupported class** (the
  ClaimIQ 2025 / MiniCheck recipe). Document the chosen ratio.
- **Cost-asymmetric framing baked into metadata.** A false "supported" (ships a hallucination) is far
  worse than a false "unsupported" (wastes a generalist call). Tag records so training/eval can weight
  FP:FN ≈ 5:1 against false-confirms (cost-sensitive eval — Wang 2025, arXiv:2510.22016).
- **Tag `multi_hop`.** Small verifiers lag on multi-hop (Seo et al., COLM 2025, arXiv:2506.13342) —
  tag it so the later eval reports multi-hop accuracy separately and we catch the failure early.
- **Two splits, frozen vs rolling:**
  - **Certification exam** — ~500 records, **human-resolved labels**, frozen at v0.1 and never edited.
    This is the level-progression metric set.
  - **Field audit** — a ~200-record slice drawn from production prism receipts *after* each training
    cutoff. Divergence between exam and audit is the overfitting/contamination alarm (DICE — Ye et al.
    2024, arXiv:2406.04197).
- **No contamination.** The exam set must be temporally disjoint from (and never sampled into) the
  training pool. Audit the exam labels with an independent model pass before freezing (Seo et al. found
  ~16% of benchmark labels wrong).

## Eval harness contract (built here as a spec; wired in training kickoff)
- **Primary metric: AUROC** (discrimination first — gate on AUROC ≥ ~0.7), then **AURC** (area under
  risk-coverage) at coverage 0.5/0.7/0.9, then Brier/ECE as calibration addenda only (Lampinen, JAMIA
  2024). Not ECE-as-headline.
- **Sanity floor:** don't regress on a public groundedness benchmark (LLM-AggreFact, the MiniCheck
  bench) and pass prism's existing **prism-on-prism meta-test**.
- A "certification level" is earned only when exam AUROC/AURC improves with non-overlapping bootstrap
  CIs **and** the field audit moves the same direction **and** it replicates across two seeds.

## Standards compliance (per workflow-standards.md — required section)

| # | Standard | Score | Evidence |
|---|---|---|---|
| 1 | PIN_PER_STEP | 3 | Every record pins its `source`, `producer_family`, and (for synthetics) the generator model+prompt hash; the corpus ships with a manifest hash and the exam-set hash is frozen. |
| 2 | ANDON_AUTHORITY | 2 | The label-audit pass halts the freeze if independent-model disagreement on the exam set exceeds a threshold. Remediation to 3: add a contamination check (n-gram/embedding overlap exam↔train) that hard-fails the build (owner: dataset maintainer, target: this kickoff if time permits). |
| 3 | NAMED_COMPENSATORS | 3 | All writes are local versioned dataset files; compensator = delete the version dir / `git revert`. **Reading prism receipts is read-only.** No external irreversible action. |
| 4 | DECOMPOSE_BY_SECRETS | 3 | Separate stages, each hiding one concern: `harvest` (receipt mining), `synth` (C2D/D2C generation), `scrub`, `split` (exam/audit), `manifest`. |
| 5 | UNCERTAINTY_GATED_HUMANS | 3 | The certification-exam labels are **human-resolved** by design — the human checkpoint gates the frozen set, exactly where uncertainty is highest. |
| 6 | EXTERNAL_VERIFIER | 3 | The specialist base is cross-family (non-Claude); it plugs into prism's `local` slot, which is itself only ever selected when family-different from the producer. The independent label-audit pass uses a different model than any generator. |

**Compensators (no-skip check):** local dataset files only. Mining prism's receipt store is read-only.
Synthetic generation runs a local model (no external API write). No publish/release/tag. Nothing here
is irreversible beyond `rm`/`git revert`.

## ⚠ Rig-safety (light GPU only)
Synthetic hard-negative generation (C2D/D2C) and any embedding-based dedup use a **local** model →
light inference, **N=0 / all-VRAM, safe**. Still: read `KICKOFF-preflight-rig-safety.md` (in
gpu-container) and run **`gpu-container-watchdog --watch`** during any local-model batch. Abort =
`wsl --shutdown`. **No training in this kickoff** — if VRAM pressure climbs, you've drifted out of
scope. Prefer a small instruct model (e.g. a Qwen3/Gemma instruct ≤ ~9B at Q4–Q6) for synthesis.

## Rules
- **Repo-first:** prism-verify → `mcp-tool-shop-org` (exists, v1.0.0). Local `E:/AI/prism-verify/`.
  Feature branch, not main. Confirm remote + branch first.
- prism is **Python** (FastAPI, pydantic; `uv`/venv). The harvester/synth/scrub/split are Python; put
  them under a `specialist/dataset/` module (confirm the repo's layout convention first).
- Consider [[repo-dataset]] (the training-data CLI, v1.2.0) for formatting/packaging the corpus into
  backpropagate's expected input shape — confirm what backpropagate consumes before settling the format.
- **Scrub pass:** prism receipts may embed artifacts with secrets/PII — run a scrub before the corpus
  leaves the repo (consistent with prism's own strip ethos). Don't bake credentials into training data.
- Workflow-standards section above is mandatory and kept current.
- Commit only when Mike asks; explicit staging; co-author trailer as in the other kickoffs.

## First moves
1. Read the architectural lock, prism `design/01` + `design/04`, and `MEMORY.md`.
2. `cd E:\AI\prism-verify`; confirm state (remote, branch, tests green via the repo's runner); confirm
   the harvester surfaces — the `engine.verify()` hook point in `core/engine.py`, the existing
   `prism/eval/corpus.py` (`prism-eval-corpus/v1` — extend it), and the `CitationResult`/`LensResult`/
   `FindingMatch` types in `core/types.py`. (Already probed: receipts hold no reusable L4 text — build
   the sink, don't mine the DB.)
3. Confirm what [[backpropagate]] expects as a training-data file (so the corpus targets it directly).
4. Branch. Build `harvest` (mine L4 receipts) first; inspect a real sample before scaling. Then
   `synth` (C2D/D2C), `scrub`, `split` (frozen exam + rolling audit), `manifest`.

## Out of scope
- Training the adapter (→ training kickoff; this produces its input).
- Lenses L1/L2/L3 (later specialists, same pipeline).
- Wiring the trained backend into prism's `local` slot (→ training kickoff, after a certified adapter exists).
