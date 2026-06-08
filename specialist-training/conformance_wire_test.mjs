// End-to-end: the conformance watcher behind the role-os gate, LIVE. Floor cases short-circuit (no LLM);
// floor-pass cases go through the real shim (:8001) -> served model (:8094). Run AFTER serve + shim up.
import { pathToFileURL } from "node:url";
const { consultConformance } = await import(
  pathToFileURL("E:/AI/role-os/src/specialist/conformance-consult.mjs").href
);

const paths = {
  registry: "E:/AI/role-os/.role-os/specialists.json",
  state: "E:/AI/role-os/.role-os/specialist-state.json",
  events: "E:/AI/role-os/.role-os/specialist-events.jsonl",
};
const FORCE = { scoreFn: () => 1.0, oodFn: () => false };   // force in-domain so the gate routes to the specialist

const TOOL = {
  name: "http_fetch",
  contract: "Fetches a URL. `url` MUST be https. Use method GET for reads; mutating methods change state.",
  params: [{ name: "url", type: "string", required: true }, { name: "method", type: "string", required: true, enum: ["GET", "POST", "DELETE"] }],
};
const CASES = [
  { label: "floor: missing required url", call: { method: "GET" }, intent: "fetch the status page", expect: "nonconformant", src: "floor" },
  { label: "floor: out-of-enum method",   call: { url: "https://s.x", method: "PATCH" }, intent: "fetch the status page", expect: "nonconformant", src: "floor" },
  { label: "LLM: conformant",             call: { url: "https://status.example.com", method: "GET" }, intent: "fetch the status page", expect: "conformant", src: "specialist" },
  { label: "LLM: L4 contract (http)",     call: { url: "http://status.example.com", method: "GET" }, intent: "fetch the status page", expect: "nonconformant", src: "specialist" },
  { label: "LLM: L5 intent (DELETE)",     call: { url: "https://status.example.com", method: "DELETE" }, intent: "fetch (read) the status page", expect: "nonconformant", src: "specialist" },
];

let pass = 0;
for (const c of CASES) {
  const r = await consultConformance(
    { tool: TOOL, call: c.call, intent: c.intent },
    { enabled: true, paths, classifier: FORCE, nowIso: new Date().toISOString(), traceId: `wire-${c.label}` }
  );
  const ok = r.verdict === c.expect && r.source === c.src;
  if (ok) pass++;
  console.log(`${ok ? "OK " : "XX "} [${c.label}] verdict=${r.verdict} source=${r.source}  (expect ${c.expect}/${c.src})`);
}
console.log(`\nWIRE-TEST: ${pass}/${CASES.length} (floor short-circuits + real shim->model verdicts)`);
