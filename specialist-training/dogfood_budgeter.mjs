// Dogfood the budgeter consult (the ROLEOS_BUDGET_CONSULT flip) through the REAL production seam.
// Three checks: (1) OFF = byte-identical no-op; (2) ON = forecast+receipt attach from the served
// budgeter; (3) fail-open = a backend failure never breaks manifest assembly.
// Run: node dogfood_budgeter.mjs   (budgeter served :8090 + verify_shim :8000 + registry in .role-os)
import { pathToFileURL } from "node:url";

const { consultBudgetForManifest } = await import(
  pathToFileURL("E:/AI/role-os/src/specialist/budget-consult.mjs").href
);
const { deterministicBudget, budgetInputForStep } = await import(
  pathToFileURL("E:/AI/role-os/src/specialist/budget-consult.mjs").href
);

const paths = {
  registry: "E:/AI/role-os/.role-os/specialists.json",
  state: "E:/AI/role-os/.role-os/specialist-state.json",
  events: "E:/AI/role-os/.role-os/specialist-events.jsonl",
};

// A realistic 2-step manifest (systemPrompt length drives the context-token estimate).
const mk = (n) => ({
  runId: "dogfood",
  steps: [
    { stepIndex: 0, maxTurns: 8, systemPrompt: "You are a Backend Engineer. ".repeat(260) }, // ~7.3k chars -> ~2.1k ctx
    { stepIndex: 1, maxTurns: 3, systemPrompt: "You are a Critic Reviewer. ".repeat(90) },   // ~2.4k chars -> ~700 ctx
  ],
});

const clone = (m) => JSON.parse(JSON.stringify(m));
const fmt = (o) => JSON.stringify(o);

// ---- (1) OFF: must be a byte-identical no-op ----
const off = mk();
const offBefore = fmt(off);
await consultBudgetForManifest(off, { enabled: false });
const offUnchanged = fmt(off) === offBefore &&
  off.steps.every((s) => s.budgetForecast === undefined && s.budgetReceipt === undefined);
console.log(`(1) OFF byte-identical no-op: ${offUnchanged ? "PASS" : "FAIL"}`);

// ---- (2) ON: forecast + receipt attach from the served budgeter ----
const on = mk();
await consultBudgetForManifest(on, { enabled: true, paths });
console.log("(2) ON — per-step forecast vs deterministic baseline:");
for (const s of on.steps) {
  const det = deterministicBudget(budgetInputForStep(s, on.steps.length));
  const f = s.budgetForecast || {};
  const spend = f.spend_weighted ?? f.verdict?.spend_weighted ?? null;
  const src = s.budgetReceipt?.source ?? f.source ?? "?";
  const ratio = spend && det.spend_weighted ? (spend / det.spend_weighted).toFixed(2) : "n/a";
  console.log(`   step${s.stepIndex}: forecast=${spend}  deterministic=${det.spend_weighted}  ratio=${ratio}  receipt.source=${src}`);
  console.log(`             receipt=${fmt(s.budgetReceipt)}`);
}
const onAttached = on.steps.every((s) => s.budgetReceipt !== undefined);
console.log(`   forecast+receipt attached on every step: ${onAttached ? "PASS" : "FAIL"}`);

// ---- (3) FAIL-OPEN: a backend failure must never break assembly ----
const fo = mk();
let threw = false;
try {
  await consultBudgetForManifest(fo, {
    enabled: true,
    paths,
    httpFn: async () => { throw new Error("simulated backend down"); },
  });
} catch (e) { threw = true; }
const foIntact = !threw && fo.steps.length === 2 && fo.steps.every((s) => s.budgetReceipt !== undefined);
console.log(`(3) FAIL-OPEN (backend down): never throws + manifest intact + receipts present: ${foIntact ? "PASS" : "FAIL"}`);
for (const s of fo.steps) console.log(`   step${s.stepIndex}: receipt.source=${s.budgetReceipt?.source}  forecast=${fmt(s.budgetForecast)}`);
