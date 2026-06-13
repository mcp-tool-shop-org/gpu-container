# S4c-2 run plan — warm-start joint training (attended)

**Status:** awaiting director schedule (attended run — no unattended campaigns).
**Informed by:** study-swarm `wf_3010a824-e2f` (3 agents, 18 retrieval-backed findings, 2026-06-12).
**Goal:** the first certified cross-trained specialist — budgeter L2 flip ≥0.75 AND conformance gate held, single exam shot, same preregistered gate as attempts #1–3.

## Why the last run stalled (research grounding)

1. **Dilution under-budgeted the transition.** 50/50 mixing gave the budgeter ~600 effective steps — the bare top of its solo 300–600 grokking window — and time-to-grok grows *super-linearly* as per-task exposure shrinks. Power et al. 2022 (arXiv:2201.02177).
2. **The upsampled conformance rows were memorization pressure.** Mixing an algorithmic task with memorization-shaped data suppresses generalization-circuit formation at fixed capacity — the 754 conformance rows repeated to 1633 competed directly with L2 circuit formation on the shared r16 adapter. Huang et al. 2024 (arXiv:2402.15175).
3. **The stall is the expected staggered-grokking signature**, not proof of impossibility; weight decay stays at 0.01 (load-bearing; raising it is known-bad both in-house and in the literature). Xu 2026 (arXiv:2602.18523); Kumar et al. 2023 (arXiv:2310.06110); NeuralGrok 2025 (arXiv:2504.17243).
4. **Protecting the robust skill is nearly free.** 1% rehearsal sufficed for stability across 70 sequential tasks; conformance exceeded its solo parent even at 50% — the uniform mix paid a massive protection premium conformance never needed. Scialom et al. 2022 (arXiv:2205.12393); Dong et al. 2023 (arXiv:2310.05492).
5. **Warm-starting from an already-grokked artifact is the best-supported accelerant.** Post-transition structure drastically accelerates re-training (Grokking Tickets, Minegishi et al., arXiv:2310.19470); transferring representations from an already-generalizing model eliminates the delay (GrokTransfer, Xu et al. 2025, arXiv:2504.13292); the delay is an initialization-basin artifact (Omnigrok, Liu et al. 2022, arXiv:2210.01117). NOTE: warm-start + continued training is a DIFFERENT operation from the failed fusion (which averaged orthogonal parents' weights).

## The design (single new lever: warm-start + asymmetric replay)

- **Init:** LoRA initialized FROM `budgeter-14b600-soup` (the grokked artifact — L2 flip 0.78 lives in these weights). Stage-1 budgeter training is already paid for.
- **Data:** conformance 754 rows + **~20% budgeter replay** (natural rows, NO upsampling of conformance) — the Dong 2023 dual-stage recipe, stage 2. The job is *acquire conformance while preserving L2*, not re-grok from scratch.
- **Recipe:** unchanged otherwise — Qwen3-14B QLoRA, rsLoRA r16/α32, lr 1e-4, wd 0.01, batch1×accum16, seq 1024, `expandable_segments`. Single-lever discipline: optimizer stays vanilla (Grokfast/OrthoGrad are documented FALLBACK levers, not stacked into this run).
- **Steps:** 800 per seed (conformance solo-learns in well under that; replay holds the basin). Two seeds (42, 1337) → soup, per house replication standard.
- **Monitoring:** checkpoint + TRAIN-slice L2 flip proxy every ~100 steps (exam stays sealed); caliper states per checkpoint; watchdog heartbeat-verified before launch; **director present**.
- **Mid-run ANDON:** if the L2 train-proxy regresses >10% from warm-start level for 2 consecutive checks, halt — the replay fraction is wrong, stop burning GPU.
- **Gate:** identical preregistered numbers, single shot, both archived exams (hashes `ebc5416a…` / `cb6de192…`).

**Time:** ~2.5h per seed at the safe geometry (~5h both, can split across two sittings — seed 42 alone is exam-eligible if needed; soup after 1337 catches up).

**Fallback ladder if L2 proxy stalls/regresses (one lever per run, receipts each):** replay 20%→35% → lr 1e-4→5e-5 → Grokfast EMA (α=0.98, λ=2, wd fixed) → synthesize additional L2-rung rows (critical-data-size insurance, Zhu et al. 2024, arXiv:2401.10463).

## Receipts
- Study-swarm findings: `runs/study-grokking-mixing.json` (18 findings, all retrieved=true)
- Attempts #1–3 in the all-attempts ledger (role-os `.role-os/specialist-events.jsonl`)
- Prior run receipts: `certify/joint-soup-{budgeter,conformance}.json`, RESULTS.md S4c section
