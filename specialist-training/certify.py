#!/usr/bin/env python
"""Budgeter certification scorer — query a served adapter on the held-out puzzle exam, score per-rung
accuracy (self-checkable; no human grading), bootstrap 95% CIs. Run against base + each seed; a rung
is 'earned' only when accuracy clears the bar with non-overlapping CIs across BOTH seeds AND the lower
rungs don't regress. Stdlib only.
Usage: python certify.py --endpoint http://127.0.0.1:8081 --exam <puzzles_exam.jsonl> --label seed42 [--out f.json]"""
import argparse, collections, json, re, random, urllib.request

SYS = ("You are a Token Budget Analyst for an LLM agent studio. You reason about the token "
       "economics of agent dispatches under this cost model (weighted tokens): input ×1, "
       "cache-write ×1.25, cache-read ×0.1, output ×5. Work through the numbers, then "
       "give a short, exact answer.")


def query(endpoint, prompt, timeout=120):
    body = json.dumps({"messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": prompt}],
                       "max_tokens": 320, "temperature": 0.1}).encode()
    req = urllib.request.Request(endpoint + "/v1/chat/completions", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def parse_answer(text):
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def correct(pred, gold, level):
    p, g = _norm(pred), _norm(gold)
    if level == 2:                                   # which-costs-more -> A / B
        m = re.search(r"\b([ab])\b", p)
        return bool(m) and m.group(1) == g.strip()
    if level == 4:                                   # starved-or-healthy -> match the distinctive word
        return ("starved" in p) if "starved" in g else ("headroom" in p)
    return g in p                                    # L1 driver / L3 fit|split / L5 component


def bootstrap_ci(hits, n_iter=2000):
    n = len(hits)
    if n == 0:
        return (0.0, 0.0, 0.0)
    acc = sum(hits) / n
    rng = random.Random(0)
    samp = sorted(sum(hits[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_iter))
    return (acc, samp[int(0.025 * n_iter)], samp[int(0.975 * n_iter)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--exam", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    puzzles = [json.loads(l) for l in open(a.exam, encoding="utf-8") if l.strip()]
    by_level, errors = {}, 0
    groups = collections.defaultdict(list)        # pair_id -> per-member correctness
    group_level = {}
    for i, p in enumerate(puzzles):
        try:
            ans = parse_answer(query(a.endpoint, p["prompt"]))
            ok = correct(ans, str(p["answer"]), p["level"])
        except Exception:
            ok, errors = False, errors + 1
        by_level.setdefault(p["level"], []).append(1 if ok else 0)
        if p.get("pair_id"):
            groups[p["pair_id"]].append(1 if ok else 0)
            group_level[p["pair_id"]] = p["level"]
        if (i + 1) % 25 == 0:
            print(f"  [{a.label}] {i+1}/{len(puzzles)} scored", flush=True)

    res = {"label": a.label, "n": len(puzzles), "query_errors": errors, "rungs": {}}
    for lvl in sorted(by_level):
        acc, lo, hi = bootstrap_ci(by_level[lvl])
        glist = [g for pid, g in groups.items() if group_level[pid] == lvl]   # flip-consistency: whole group correct
        flip = round(sum(1 for g in glist if all(g)) / len(glist), 3) if glist else None
        res["rungs"][str(lvl)] = {"n": len(by_level[lvl]), "acc": round(acc, 3),
                                  "ci95": [round(lo, 3), round(hi, 3)], "flip_consistency": flip}
    allhits = [h for hs in by_level.values() for h in hs]
    res["overall"] = round(sum(allhits) / len(allhits), 3) if allhits else 0.0
    res["flip_consistency_overall"] = (round(sum(1 for g in groups.values() if all(g)) / len(groups), 3)
                                       if groups else 0.0)
    print(json.dumps(res, indent=2))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=2)


if __name__ == "__main__":
    main()
