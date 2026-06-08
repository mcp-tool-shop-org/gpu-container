#!/usr/bin/env python3
"""Dogfood the served verifier (the prism flip) through prism's EXACT provider contract.

Hits llama.cpp :8092 (verifier-14b600-soup @ scale 4) with the LocalVerifierProvider's system prompt
+ EVIDENCE/CLAIM retemplate + verdict parse, on a small labeled set. The decisive question for the
PRISM_LOCAL_VERIFIER_ENDPOINT flip: does the known meaning-preserving-paraphrase over-flagging
(false 'unsupported' on a faithful active/passive or lexical paraphrase) bite on realistic citations?
"""
import json, re, time, urllib.request

ENDPOINT = "http://localhost:8092/v1/chat/completions"
SYS = ("You are a Groundedness Verifier. Given EVIDENCE and a CLAIM, decide whether the evidence "
       "supports the claim. Check every load-bearing part of the claim against the evidence. Answer "
       "'supported' (every part traces to the evidence), 'unsupported' (some part is contradicted or "
       "not present in the evidence), or 'abstain' (the evidence is silent — insufficient to judge). "
       "Reason briefly, then give the one-word verdict.")

# (category, evidence, claim, expected)
CASES = [
    ("direct-supported",   "The system achieved 99.4% accuracy on the held-out set.",        "The system achieved 99.4% accuracy on the held-out set.",      "supported"),
    ("direct-supported",   "Thorne acquired Velora in 2019.",                                "Thorne acquired Velora in 2019.",                              "supported"),
    ("paraphrase-supported","The 2021 study reported a 23% reduction in inference latency.",  "Inference latency dropped by 23% in the 2021 study.",          "supported"),
    ("paraphrase-supported","Velora was acquired by Thorne in 2019.",                         "Thorne acquired Velora in 2019.",                              "supported"),
    ("paraphrase-supported","The treatment lowered mortality by 15%.",                        "Mortality fell 15% under the treatment.",                      "supported"),
    ("paraphrase-supported","Researchers observed that the catalyst doubled the yield.",      "The yield was doubled by the catalyst, the researchers found.","supported"),
    ("direction-reversed",  "Velora was acquired by Thorne in 2019.",                         "Velora acquired Thorne in 2019.",                              "unsupported"),
    ("direction-reversed",  "Group A outperformed Group B on the benchmark.",                 "Group B outperformed Group A on the benchmark.",               "unsupported"),
    ("value-contradicted",  "The study reported a 23% reduction in latency.",                 "The study reported a 50% reduction in latency.",               "unsupported"),
    ("value-contradicted",  "The model scored 88% accuracy.",                                 "The model scored 95% accuracy.",                               "unsupported"),
    ("abstain-silent",      "The 2021 study reported a 23% reduction in latency.",            "The study also reduced memory usage by 30%.",                  "abstain"),
    ("abstain-silent",      "Thorne acquired Velora in 2019.",                                "Thorne acquired Velora to enter the European market.",         "abstain"),
]


def verdict_of(ev, claim):
    user = f"EVIDENCE:\n{ev}\n\nCLAIM:\n{claim}"
    body = json.dumps({"messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": user}],
                       "max_tokens": 512, "temperature": 0.1}).encode()
    req = urllib.request.Request(ENDPOINT, body, {"Content-Type": "application/json"})
    txt = json.loads(urllib.request.urlopen(req, timeout=90).read())["choices"][0]["message"]["content"]
    tail = txt.split("</think>")[-1].lower()
    for v in ("unsupported", "abstain", "supported"):
        if v in tail:
            return v
    return None


def main():
    rows, by_cat = [], {}
    for cat, ev, claim, exp in CASES:
        got = verdict_of(ev, claim)
        ok = (got == exp)
        rows.append((cat, exp, got, ok, claim))
        by_cat.setdefault(cat, [0, 0])
        by_cat[cat][1] += 1
        if ok:
            by_cat[cat][0] += 1
        mark = "OK " if ok else "XX "
        print(f"{mark} [{cat:20}] exp={exp:11} got={str(got):11} | {claim[:55]}")
    n = len(rows); correct = sum(1 for r in rows if r[3])
    print(f"\nOVERALL: {correct}/{n} = {correct/n:.2f}")
    print("BY CATEGORY:")
    for cat, (c, t) in by_cat.items():
        print(f"  {cat:22} {c}/{t}")
    # the decisive number for the flip:
    ps = by_cat.get("paraphrase-supported", [0, 0])
    print(f"\nPARAPHRASE-SUPPORTED correct: {ps[0]}/{ps[1]}  "
          f"(false-unsupported on faithful paraphrases = the flip's risk)")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n({time.time()-t0:.0f}s, served verifier @ :8092 scale 4)")
