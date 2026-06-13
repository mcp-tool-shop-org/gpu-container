#!/usr/bin/env node
// S4d untraining-experiment -> role-os all-attempts ledger (one event, Token Budget Analyst).
// No conformance mirror: no exam ran (proxy-only, sealed exams untouched). Idempotent.
import { appendFileSync, readFileSync } from "node:fs";

const LEDGER = "E:/AI/role-os/.role-os/specialist-events.jsonl";

const event = {
  kind: "untraining-experiment",
  role: "Token Budget Analyst",
  ts: "2026-06-13T03:51:03.342Z",
  data: {
    experiment: "S4d-design-A",
    substrate: "budgeter-conformance-joint-soup-20260612",
    question:
      "after joint SFT, are the parent task vectors linearly recoverable? subtract the conformance task vector from the from-scratch joint adapter, re-proxy budgeter L2",
    method:
      "dW(joint) - lambda*dW(conformance-14b-soup-v0.2) via cross_train.py --method add --lam-a 1.0 --lam-b -lambda, rank 32, alpha 45.254834, use_rslora (effective scale 8.0)",
    lambda_sweep: [0.5, 1.0],
    merge_residuals: { neg05: 0.0025, neg10: 0.0019 },
    compatibility: { mean_cosine: 0.0741, sign_agreement_on_overlap: 0.6404, mean_overlap_jaccard: 0.1305 },
    proxy: { harness: "l2_proxy.py", n_pairs: 30, split: "TRAIN", thinking: true, sealed_exam_opened: false },
    gate_preregistered: {
      andon: "ref flip >= 0.867",
      H1_recovery: "neg_best >= base+0.10",
      H0_no_change: "both within +/-0.10 of base",
      collapse: "neg10 <= base-0.10",
      exam_trigger: "neg_best >= 0.80 AND recovery (director-gated)",
    },
    results: { ref: "0.967/0.933", base: "0.733/0.467", neg05: "0.650/0.300", neg10: "0.500/0.000" },
    verdict:
      "COLLAPSE (monotonic) -- H1 and H0 both rejected; neg10 flip 0.000 (acc -> chance 0.500). Joint SFT != task-vector addition: subtracting the conformance direction does not recover the budgeter parent (0.933), it destroys L2. The conformance update is load-bearing for the grokked L2 circuit despite near-orthogonal global task vectors (cosine 0.074) -- entanglement local to the circuit. Extends S4b: L2 survives neither weight-space superposition nor subtraction. No exam fired (neg_best 0.300 << 0.80).",
    receipts: [
      "E:/AI/gpu-container/specialist-training/runs/untrain-neg05.json",
      "E:/AI/gpu-container/specialist-training/runs/untrain-neg10.json",
      "E:/AI/gpu-container/specialist-training/runs/untrain-proxy-results.json",
      "E:/AI/gpu-container/specialist-training/logs/s4d_proxy.log",
      "E:/AI/gpu-container/specialist-training/RESULTS.md",
    ],
    exam_hash_unopened: "ebc5416a8c327d2783c4873292d7185ae3e04d63d3b6e3526bb2ecddedd3f68d",
    grounding: "Ilharco et al. arXiv:2212.04089",
    adapters: [
      "E:/AI-Models/adapters/joint-soup-neg-conf-l05",
      "E:/AI-Models/adapters/joint-soup-neg-conf-l10",
    ],
  },
};

const existing = readFileSync(LEDGER, "utf8");
if (existing.includes('"kind":"untraining-experiment"')) {
  console.log("SKIP: an untraining-experiment event is already present -- not appending again");
} else {
  appendFileSync(LEDGER, JSON.stringify(event) + "\n", "utf8");
  console.log("APPENDED untraining-experiment event to " + LEDGER);
}
