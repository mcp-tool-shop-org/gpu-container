// End-to-end wiring proof: the budgeter behind the role-os fail-open gate.
// Case 1 (in-domain) → gate routes to the specialist (real call through the /verify shim).
// Case 2 (OOD)       → gate fails open to the DETERMINISTIC baseline (not Claude), per the kickoff.
// Run: node wire_test.mjs   (registry pinned to role-os/.role-os via the paths arg)
import { pathToFileURL } from "node:url";
const { dispatchSpecialist } = await import(
  pathToFileURL("E:/AI/role-os/src/specialist/dispatch.mjs").href
);

const paths = {
  registry: "E:/AI/role-os/.role-os/specialists.json",
  state: "E:/AI/role-os/.role-os/specialist-state.json",
  events: "E:/AI/role-os/.role-os/specialist-events.jsonl",
};

// the fail-open fallback IS the deterministic baseline (not Claude) for the budgeter
const deterministic = (input) => ({
  spend_weighted: Math.max(Math.round((input.context_tokens || 0) * 1.5), 50000),
  source: "deterministic-baseline",
});

const input = { context_tokens: 20000, steps: 8, output_estimate: 2000 };

async function run(label, classifier) {
  const { result, receipt } = await dispatchSpecialist({
    role: "Token Budget Analyst",
    input,
    claudeFn: async (i) => deterministic(i),
    agreeFn: (s, c) =>
      Math.abs((s?.spend_weighted ?? 0) - (c?.spend_weighted ?? 0)) <= 0.25 * (c?.spend_weighted ?? 1),
    traceId: `wire-${label}`,
    nowIso: new Date().toISOString(),
    paths,
    classifier,
  });
  console.log(`\n[${label}]`);
  console.log(`  result  = ${JSON.stringify(result)}`);
  console.log(`  receipt = ${JSON.stringify(receipt)}`);
}

await run("in-domain", { scoreFn: () => 1.0, oodFn: () => false });
await run("ood", { scoreFn: () => 0.0, oodFn: () => true });
