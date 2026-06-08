#!/usr/bin/env python3
"""Verify the redesigned curriculum: answer balance, contrast-pair flips, no flip-pair split leakage."""
import json, collections
D = "/mnt/e/AI/role-os/tools/token-budget-dataset/dataset/v0.1/puzzles"
recs = [json.loads(l) for l in open(f"{D}/puzzles.jsonl")]

by = collections.defaultdict(collections.Counter)
for r in recs:
    by[r["level"]][str(r["answer"])[:20]] += 1
print("=== answer balance ===")
for lvl in sorted(by):
    tot = sum(by[lvl].values())
    print(f"L{lvl} (n={tot}): " + " | ".join(f"{a}={100*c//tot}%" for a, c in by[lvl].most_common(4)))

groups = collections.defaultdict(list)
for r in recs:
    if r.get("pair_id"):
        groups[r["pair_id"]].append(r)
flipped = sum(1 for g in groups.values() if len({p["answer"] for p in g}) > 1)
leaky = sum(1 for g in groups.values() if len({p["split"] for p in g}) > 1)
print("\n=== contrast pairs ===")
print(f"groups={len(groups)}  with-distinct-answers={flipped}  cross-split-LEAK={leaky}")
print(f"total={len(recs)}  contrast-flagged={sum(1 for r in recs if r.get('contrast'))}")
for lvl in sorted(by):
    lg = [g for g in groups.values() if g and g[0]['level'] == lvl]
    lf = sum(1 for g in lg if len({p['answer'] for p in g}) > 1)
    print(f"  L{lvl}: {len(lg)} groups, {lf} with a flip")
