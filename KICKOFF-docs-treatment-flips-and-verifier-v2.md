# Kickoff — Doc treatment (prism 1.2.0 + role-os 2.7.0) · Verifier v2 (voice-invariance) · flips & housekeeping

Carries over from the **Verifier-#2 + budgeter-default** session (2026-06-06). The code shipped; this
session finishes the **documentation/marketing layer** Mike called for (handbook pages, landing-page
updates, READMEs+translations, repo-knowledge), lands the **honest v2 dataset fix**, and clears the
housekeeping. Do the doc tracks first (fast, high-visibility); Verifier-v2 is the GPU-heavy one.

## What shipped this session (the baseline you're finishing)

- **Verifier specialist #2 (L4 Groundedness)** — dataset (audit PASS, 1,281 records) → trained
  (Qwen3-14B QLoRA, 2 seeds + model-soup) → **certified 0.994 acc / 0.987 flip-consistency, 0.5%
  false-"supported"** (beats the budgeter's 0.944/0.866) → served (llama.cpp @ `--lora scale 4`) →
  **wired into prism's CITATION lens** (NOT the artifact lens) as `LocalVerifierProvider`, opt-in.
  Published in **prism-verify 1.2.0** (PyPI + npm + binaries). Adapter: `E:/AI-Models/adapters/
  verifier-14b600-soup(.gguf)`. Manifest: `prism-verify/specialist/verifier-v1.json`. Design + the
  buildable spec: `prism-verify/specialist/V-D-INTEGRATION.md`. Dataset + scripts:
  `prism-verify/specialist/dataset/`. Training recipe + scripts: `gpu-container/specialist-training/`
  (`train_verifier.sh`, `certify_all_verifier.ps1`, `serve_verifier.ps1`, `soup_adapters.py`, RESULTS.md).
- **Budgeter production consult** — `role-os/src/specialist/budget-consult.mjs`
  (`consultBudgetForManifest` / `buildDispatchManifestWithBudget`), opt-in, fail-open, advisory.
  Published in **role-os 2.7.0** (npm).
- **Both Mike-gated flips remain default-OFF in the shipped packages:** `PRISM_LOCAL_VERIFIER_ENDPOINT`
  (prism) and `ROLEOS_BUDGET_CONSULT` (role-os). Flipping them on is the release decision deferred here.

Known honest limitation (the v2 target): the served verifier **over-flags active/passive relational
paraphrases as `unsupported`** — "Thorne acquired Velora" vs evidence "Velora was acquired by Thorne"
reads as unsupported even though the relation is identical. It's the SAFE direction (a false-*unsupported*
→ REVISE, never a hallucination-pass), but it hurts usability on faithful citations.

---

## Track A — prism-verify 1.2.0 documentation treatment

prism already has a LIVE Starlight handbook + landing page at `mcp-tool-shop-org.github.io/prism-verify`
(repo `site/`, deployed by `pages.yml`, paths-gated to `site/**`). **Update**, don't rebuild.

1. **Handbook page** — add a "Local verifier specialist (citation lens)" page under the handbook that
   documents: `PRISM_LOCAL_VERIFIER_ENDPOINT` / `PRISM_LOCAL_VERIFIER_MODEL`, the verdict mapping
   (supported→supported, unsupported→contradicted, abstain→not_addressed), the fail-open behavior
   (ProviderError → circuit-breaker → hosted/mistral), the recommendation to pair with `PRISM_NLI_FLOOR`,
   and a short "serve your own" pointer (llama.cpp @ scale 4 + the JSON-output contract). Add a sibling
   "L4 harvest sink" page (`PRISM_HARVEST_PATH`) since 1.2.0 shipped it too. Read the **handbook skill**
   + `memory/handbook-playbook.md` first.
2. **Landing page** — surface the new "bring-your-own local verifier" capability on the prism landing
   page; wire the handbook nav to it (the handbook↔landing link is the handbook skill's contract).
3. **README + translations** — add a short feature mention to `README.md` (the local verifier + harvest
   sink). README changes ⇒ **translations run BEFORE any publish** (`node E:/AI/polyglot-mcp/scripts/
   translate-all.mjs prism-verify/README.md` → refreshes `README.{ja,zh,es,fr,hi,it,pt-BR}.md` +
   the language nav). The npm launcher ships `README.*.md`, so if you touch the README, **patch-publish
   1.2.1** (bump `pyproject.toml` + `npm/package.json`, tag, gh release) OR defer the README to the next
   feature release — DECISION for the session. Handbook/landing are Pages deploys and need no bump.
4. **repo-knowledge DB** — update the prism-verify entry to 1.2.0 (Phase-5 of the treatment;
   `repo-knowledge` skill / scan).

## Track B — role-os 2.7.0 documentation treatment

role-os has a site at `mcp-tool-shop-org.github.io/role-os`. **Update** it.

1. **Handbook page** — "Token Budget Analyst — production budget consult": `ROLEOS_BUDGET_CONSULT`,
   `consultBudgetForManifest` / `buildDispatchManifestWithBudget`, the per-step `budgetForecast` +
   `budgetReceipt`, the deterministic fail-open baseline `max(ctx*1.5, 50000)`, advisory semantics, and
   the `roleos specialist rollback` compensator. Cross-link to the existing specialist-tier docs.
2. **Landing page** — note the budget-consult capability; keep the default-off framing explicit.
3. **README + translations** — feature mention; if `README.md` changes, **translations first**, then a
   patch-publish **2.7.1** OR defer (same decision as A.3). role-os `files` ships `README.md`.
4. **repo-knowledge DB** — update the role-os entry to 2.7.0.

## Track C — Verifier v2: voice-invariance dataset pass (GPU-heavy; the honest fix)

Goal: kill the active/passive over-flagging **without** weakening the real relation-direction negative.

1. **Augment the dataset** (in `prism-verify/specialist/dataset/`): add meaning-preserving paraphrase
   **POSITIVES** to the supported class — for relational evidence, generate the SAME relation in BOTH
   voices and label BOTH `supported`. Build them as CONTRAST GROUPS that pin the distinction the model
   conflated: same evidence → **voice-changed-equivalent = supported** vs **direction-reversed =
   unsupported** (e.g. ev "Velora was acquired by Thorne": "Thorne acquired Velora" = supported;
   "Velora acquired Thorne" = unsupported). This is the budgeter lesson applied — surface-near,
   verdict-different, flip-consistency-scored. Re-use `synth.py` (cross-family gate-confirm the
   positives too) + a new `puzzles.py` generator for the voice/direction triple.
2. **Re-audit** (`build_verifier_dataset.py` → `audit.py` MUST PASS) and **director-eyeball** a handful.
3. **Re-train → soup → certify** with the proven recipe **verbatim** (Qwen3-14B, rsLoRA r16/α32, lr 1e-4,
   wd 0.01 default, batch4×accum4 + checkpointing, 600 steps, seeds 42+1337, `soup_adapters.py`).
   **Add voice-invariance cases to the held-out exam** so certification PROVES the fix (a faithful
   active/passive paraphrase now scores `supported`) AND confirms no regression on direction-reversal
   negatives or the cost-asymmetric false-"supported" rate. Watchdog `--power-max 100 --temp-max 87
   --host-mem-max 80`; WSL path only; never train+serve concurrently; ext4 → copy to E:.
4. **Serve + re-wire** — this is the cheap part: the new soup is served the same way; **no prism code
   change** (the `LocalVerifierProvider` is unchanged). Update `verifier-v1.json` to a `verifier-v2`
   version (new `exam_hash`, scores) and re-point the served adapter. Compensator: **version rollback**
   (pointer swap to `verifier-14b600-soup`) — no retrain.
5. Only if the provider contract changes do you republish prism; otherwise v2 is an adapter swap +
   manifest update, no PyPI/npm release.

## Track D — the default-on flips (Mike-gated; stage, don't flip)

Document the exact enable procedure for both so Mike can flip with one command, and (optionally) add a
short "enabling the local verifier / budget consult in production" handbook section:
- prism: `PRISM_LOCAL_VERIFIER_ENDPOINT=http://<serve>:8092` (+ recommend `PRISM_NLI_FLOOR=1`).
- role-os: `ROLEOS_BUDGET_CONSULT=1`.
**Do not flip the defaults** — that's Mike's release call. The handbook should say so.

## Track E — housekeeping (clear the loose ends)

- **Two stashes are Mike's** — prism `stash@{0}` (a `uv.lock` regeneration) and role-os `stash@{0}`
  ("wip harvester edits", 193-line `puzzles.py`). Confirm with Mike before pop/commit/drop; neither
  shipped (lockfile / `tools/` aren't packaged).
- **Untracked dataset dirs** — `prism-verify/specialist/` (dataset, scripts, manifest, V-D doc) and
  `role-os/.role-os/` (registry). DECISION: keep-in-repo (gitignore the heavy `*.jsonl`?), move the
  training artifacts to `gpu-container`, or leave untracked. The integration docs (`V-D-INTEGRATION.md`,
  `verifier-v1.json`) likely belong committed in prism; the raw dataset probably does not ship.
- **Live services** from this session may still be up: `budgeter-serve` (:8090) + `verify_shim.py`
  (:8000). Tear down if idle: `docker rm -f budgeter-serve` + `pkill -f verify_shim.py`. `serve_verifier.ps1`
  / `serve_budgeter.ps1` restand either in ~1 min.
- **Merged feature branches** are local-only — `feat/specialist-verifier-lens` (prism),
  `feat/budget-production-consult` (role-os). Delete after confirming main has everything.
- **Central marketing site** — if the per-tool landing/handbook changed materially, run the Sync +
  overrides on `mcp-tool-shop/mcp-tool-shop` so the aggregator reflects prism 1.2.0 / role-os 2.7.0
  (see `.claude/rules/site-publishing.md`; Sync is manual-only by design).

---

## Apply what's proven — reuse, do NOT re-derive

- Recipe, watchdog, rig-safety, serve-scale-4, bp-env pins, soup-the-correct-way: all in
  `gpu-container/specialist-training/RESULTS.md` + the scripts. `train_verifier.sh` is data-parametric
  (`BUDGETER_DATA`). The 14B HF base is cached; `verifier-14b600-soup` is the rollback target.
- Dataset discipline (flip-consistency truth metric, contrast groups, audit-as-hard-gate, cross-family
  generate-then-gate, fictional/studio facts to force grounding) is baked into the `dataset/` scripts.
- **The cross-family gate runs against Ollama on the WINDOWS host** (run `synth.py` on Windows, or set
  `OLLAMA_HOST` from WSL). `qwen3.6:latest` is a reasoning model — keep `"think": false` in `synth.chat`.
- Treatment/handbook/translation protocols: `memory/handbook-playbook.md`, `memory/full-treatment.md`,
  `memory/translation-workflow.md`, `.claude/rules/site-publishing.md`. Read before acting.

## Standards compliance (the six)

| # | standard | score | evidence |
|---|---|---|---|
| 1 | PIN_PER_STEP | 2 | Recipe/scripts/serve-scale/bp-env pinned in RESULTS.md + scripts; per-record gen/gate prompts fixed in `synth.py`. Local sampling varies (TEMP_GATE=0 mitigates). |
| 2 | ANDON_AUTHORITY | 3 | `audit.py` hard-fails a gamed/leaky dataset (exit 1) before any v2 training; the cross-family gate discards ambiguous records; certification refuses a non-replicating/regressing adapter (now incl. a voice-invariance gate). |
| 3 | NAMED_COMPENSATORS | 3 | Verifier-v2: `roleos`-style **version rollback** = pointer swap to `verifier-14b600-soup`, no retrain. Docs/handbook/landing are Pages deploys (revert commit). A README patch-publish's compensator: the prior published version stays installable; yank only on a real defect. **No skip** — both republish paths (patch-publish, adapter swap) name their undo. |
| 4 | DECOMPOSE_BY_SECRETS | 3 | prism-docs (A) · role-os-docs (B) · verifier-v2 dataset/train/serve (C) · flips (D) · housekeeping (E) are separate boundaries; verifier (prism lens) and budgeter (role-os gate) stay distinct integration secrets. |
| 5 | UNCERTAINTY_GATED_HUMANS | 2 | Director eyeballs the v2 rung samples; the default-on flips are explicitly Mike-gated; the README-bump-vs-defer and dataset-placement decisions are surfaced as forks, not assumed. Held at 2 until the eyeball is a wired interactive checkpoint. |
| 6 | EXTERNAL_VERIFIER | 3 | v2 dataset keeps the cross-family generate-then-gate (Mistral judges Qwen, reasoning hidden); certification uses flip-consistency on a held-out, group-atomic exam incl. the new voice/direction contrast. |

Below-2 remediation: PIN (1→2 ok; raise to 3 by pinning the v2 Ollama gate model + a seed log) and
UNCERTAINTY (2) are tracked, not skipped. **Compensators: no skip** — see #3.

## Definition of done

- **Docs:** prism + role-os handbooks have the new pages, wired to updated landing pages and deployed
  (Pages green); READMEs mention the features with translations refreshed (and either patch-published or
  explicitly deferred); repo-knowledge entries updated to 1.2.0 / 2.7.0; central marketing site synced if
  warranted.
- **Verifier-v2:** dataset `audit.py` PASS (incl. voice/direction contrast) → director eyeball →
  soup re-trained (recipe verbatim) → certification PROVES the active/passive fix AND no regression on
  direction-negatives or false-"supported" → served @ scale 4 → `verifier-v1.json` advanced to v2 (prism
  code unchanged; rollback = pointer swap).
- **Flips:** enable procedures documented; defaults stay OFF (Mike's call).
- **Housekeeping:** stashes resolved with Mike; dataset/artifact placement decided; idle services down;
  merged branches deleted.
