#!/usr/bin/env python
"""CAT calibration for cross-training (specialists S4b) — learn per-adapter mixing weights
on TRAIN data only; the archived certification exams are never touched (Goodhart guard).

LoRA-Soups CAT, 2-parameter form: the fused update is
    y = Wx + lam_A * s * B_A A_A x + lam_B * s * B_B A_B x        (s = alpha/sqrt(r) = 8, rsLoRA)
with lam_A, lam_B the ONLY trainable parameters, optimized by CE on a 50/50 interleave of the
two parents' TRAIN SFT sets. The lam=1 endpoint is the measured failed bracket (2026-06-12).

vector-caliper capture per eval checkpoint (probe batch held out of calibration batches):
  geometry.effectiveDimension  participation ratio of PCA eigenvalues of the last-token
                               hidden-state cloud (final layer, fp32, probe batch)
  geometry.anisotropy          top eigenvalue / smallest nonzero eigenvalue
  geometry.spread              mean pairwise L2 distance
  geometry.density             n / (1 + mean nearest-neighbor distance)   [proxy]
  uncertainty.entropy          mean next-token Shannon entropy (bits) at the answer's first
                               token position                              [native]
  uncertainty.margin           mean (p1 - p2) at the same position         [native]
  uncertainty.calibration      std of probe per-sample answer-token accuracy [dispersion proxy]
  performance.accuracy         mean token-level top-1 accuracy on answer tokens (teacher-forced)
  performance.loss             mean CE on answer tokens
States JSON -> runs/cat-calibration-states.json (vector-caliper createModelState contract).

Usage: python calibrate_cat.py [--steps 150] [--batch 2] [--eval-every 25] [--lr 0.02]
"""
import argparse, json, os, random
os.environ.setdefault("HF_HOME", "/mnt/e/AI-Models/hf-cache")
import torch
from safetensors.torch import load_file
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

AD = "/mnt/e/AI-Models/adapters"
PARENT_A = f"{AD}/budgeter-14b600-soup"            # Token Budget Analyst
PARENT_B = f"{AD}/conformance-14b-soup-v0.2"       # Tool-Call Conformance
TRAIN_A = "/mnt/e/AI/gpu-container/specialist-training/data/puzzles_train_sft.jsonl"
TRAIN_B = "/mnt/e/AI/role-os/tools/conformance-dataset/conformance_train_sft.jsonl"
OUT_DIR = "/mnt/e/AI/gpu-container/specialist-training/runs"
RSLORA_SCALE = 8.0  # alpha/sqrt(r) = 32/4, the trained forward semantics of both parents
N_PROBE_PER_TASK = 12
SEED = 42

ap = argparse.ArgumentParser()
ap.add_argument("--steps", type=int, default=150)
ap.add_argument("--batch", type=int, default=2)
ap.add_argument("--eval-every", type=int, default=25)
ap.add_argument("--lr", type=float, default=0.02)
ap.add_argument("--seq", type=int, default=1024)
args = ap.parse_args()
random.seed(SEED); torch.manual_seed(SEED)
dev = "cuda"

print("[load] Qwen3-14B 4-bit", flush=True)
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-14B")
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-14B",
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                                           bnb_4bit_quant_type="nf4"),
    device_map={"": 0}, attn_implementation="sdpa",
)
model.eval()
for p in model.parameters():
    p.requires_grad_(False)

# ── attach the two frozen LoRA branches with learnable mixing scalars ─────────────────────
lam = torch.nn.Parameter(torch.tensor([1.0, 1.0], device=dev))  # [lam_A, lam_B], init = failed bracket

def branches(state):
    out = {}
    for k in state:
        if k.endswith(".lora_A.weight"):
            mod = k[: -len(".lora_A.weight")].replace("base_model.model.", "")
            A = state[k].to(dev, torch.bfloat16)
            B = state[k.replace(".lora_A.", ".lora_B.")].to(dev, torch.bfloat16)
            out[mod] = (A, B)
    return out

bA = branches(load_file(os.path.join(PARENT_A, "adapter_model.safetensors")))
bB = branches(load_file(os.path.join(PARENT_B, "adapter_model.safetensors")))
assert set(bA) == set(bB)
modules = dict(model.named_modules())
hooks = []
for name, (A1, B1) in bA.items():
    A2, B2 = bB[name]
    lin = modules[name]
    def mk(A1=A1, B1=B1, A2=A2, B2=B2):
        def hook(mod, inp, out):
            x = inp[0]
            d1 = torch.nn.functional.linear(torch.nn.functional.linear(x, A1), B1)
            d2 = torch.nn.functional.linear(torch.nn.functional.linear(x, A2), B2)
            return out + RSLORA_SCALE * (lam[0] * d1 + lam[1] * d2)
        return hook
    hooks.append(lin.register_forward_hook(mk()))
print(f"[hooks] {len(hooks)} modules wired with learnable (lam_A, lam_B)", flush=True)

# ── data: 50/50 interleave; probes held out of the calibration stream ─────────────────────
def load_sft(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def to_chat(row):
    msgs = row.get("messages")
    if not msgs:  # tolerate {prompt, completion} / {instruction, output}
        user = row.get("prompt") or row.get("instruction") or row.get("input")
        asst = row.get("completion") or row.get("output") or row.get("response")
        msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": asst}]
    return msgs

dsA, dsB = [list(map(to_chat, load_sft(p))) for p in (TRAIN_A, TRAIN_B)]
random.shuffle(dsA); random.shuffle(dsB)
probes = dsA[:N_PROBE_PER_TASK] + dsB[:N_PROBE_PER_TASK]
poolA, poolB = dsA[N_PROBE_PER_TASK:], dsB[N_PROBE_PER_TASK:]
print(f"[data] A train {len(poolA)} / B train {len(poolB)} / probes {len(probes)}", flush=True)

def encode(msgs):
    # teacher-forced full conversation; labels only on the assistant span.
    # apply_chat_template(tokenize=True) returns tokenizers.Encoding on this transformers
    # version — go via string + explicit tokenize for plain int lists.
    prompt_txt = tok.apply_chat_template(msgs[:-1], add_generation_prompt=True, tokenize=False)
    full_txt = tok.apply_chat_template(msgs, add_generation_prompt=False, tokenize=False)
    prompt_ids = tok(prompt_txt, add_special_tokens=False).input_ids
    full_ids = tok(full_txt, add_special_tokens=False).input_ids
    full_ids = full_ids[: args.seq]
    labels = [-100] * len(full_ids)
    for i in range(min(len(prompt_ids), len(full_ids)), len(full_ids)):
        labels[i] = full_ids[i]
    return full_ids, labels, min(len(prompt_ids), len(full_ids) - 1)

def batch_ce(batch_msgs):
    enc = [encode(m) for m in batch_msgs]
    maxlen = max(len(e[0]) for e in enc)
    pad = tok.pad_token_id or tok.eos_token_id
    ids = torch.full((len(enc), maxlen), pad, dtype=torch.long)
    lab = torch.full((len(enc), maxlen), -100, dtype=torch.long)
    att = torch.zeros((len(enc), maxlen), dtype=torch.long)
    for i, (f, l, _) in enumerate(enc):
        ids[i, : len(f)] = torch.tensor(f); lab[i, : len(l)] = torch.tensor(l); att[i, : len(f)] = 1
    out = model(input_ids=ids.to(dev), attention_mask=att.to(dev), labels=lab.to(dev))
    return out.loss

# ── caliper capture ────────────────────────────────────────────────────────────────────────
@torch.no_grad()
def capture_state(step):
    feats, accs, ents, margins, losses = [], [], [], [], []
    for m in probes:
        f, l, ans_start = encode(m)
        ids = torch.tensor([f], device=dev)
        out = model(input_ids=ids, labels=torch.tensor([l], device=dev), output_hidden_states=True)
        losses.append(out.loss.float().item())
        feats.append(out.hidden_states[-1][0, -1].float().cpu())
        logits = out.logits[0].float()
        ans_idx = [i for i, t in enumerate(l) if t != -100]
        if ans_idx:
            pred = logits[[i - 1 for i in ans_idx]].argmax(-1)
            gold = torch.tensor([l[i] for i in ans_idx])
            accs.append((pred.cpu() == gold).float().mean().item())
            p = torch.softmax(logits[ans_idx[0] - 1], -1)
            top2 = torch.topk(p, 2).values
            ents.append(float(-(p * (p + 1e-12).log2()).sum()))
            margins.append(float(top2[0] - top2[1]))
    X = torch.stack(feats).numpy()
    import numpy as np
    Xc = X - X.mean(0)
    ev = np.linalg.eigvalsh(np.cov(Xc.T))[::-1]
    ev = ev[ev > 1e-9]
    eff_dim = float(ev.sum() ** 2 / (ev ** 2).sum())
    aniso = float(ev[0] / ev[-1]) if len(ev) > 1 else 1.0
    dists = np.sqrt(((X[:, None] - X[None, :]) ** 2).sum(-1))
    spread = float(dists[np.triu_indices(len(X), 1)].mean())
    nn = np.partition(dists + np.eye(len(X)) * 1e9, 0, axis=1)[:, 0]
    return {
        "id": f"cat-step-{step}", "time": step,
        "geometry": {"effectiveDimension": eff_dim, "anisotropy": aniso,
                     "spread": spread, "density": float(len(X) / (1 + nn.mean()))},
        "uncertainty": {"entropy": float(np.mean(ents)), "margin": float(np.mean(margins)),
                        "calibration": float(np.std(accs))},
        "performance": {"accuracy": float(np.mean(accs)), "loss": float(np.mean(losses))},
        "metadata": {"source": "budgeter x conformance CAT calibration (Qwen3-14B 4-bit, RTX 5090)",
                     "version": "1.0.0",
                     "tags": [f"n={len(X)}", "last-token-hidden", "native-uncertainty",
                              f"lam_A={lam[0].item():.4f}", f"lam_B={lam[1].item():.4f}"]},
    }

# ── calibration loop ───────────────────────────────────────────────────────────────────────
opt = torch.optim.Adam([lam], lr=args.lr)
states, lam_log = [], []
states.append(capture_state(0))
print(f"[probe@0] loss={states[-1]['performance']['accuracy']:.3f}acc/{states[-1]['performance']['loss']:.3f}ce lam=({lam[0].item():.3f},{lam[1].item():.3f})", flush=True)
for step in range(1, args.steps + 1):
    batch = [random.choice(poolA) if i % 2 == 0 else random.choice(poolB) for i in range(args.batch)]
    loss = batch_ce(batch)
    opt.zero_grad(); loss.backward(); opt.step()
    with torch.no_grad():
        lam.clamp_(0.0, 2.0)
    lam_log.append({"step": step, "lam_A": lam[0].item(), "lam_B": lam[1].item(), "ce": float(loss)})
    if step % args.eval_every == 0 or step == args.steps:
        st = capture_state(step)
        states.append(st)
        print(f"[probe@{step}] acc={st['performance']['accuracy']:.3f} ce={st['performance']['loss']:.3f} "
              f"effDim={st['geometry']['effectiveDimension']:.2f} spread={st['geometry']['spread']:.2f} "
              f"lam=({lam[0].item():.4f},{lam[1].item():.4f})", flush=True)

os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "cat-calibration-states.json"), "w") as f:
    json.dump(states, f, indent=1)
with open(os.path.join(OUT_DIR, "cat-lambda-trajectory.json"), "w") as f:
    json.dump(lam_log, f, indent=1)
print(f"FINAL lam_A={lam[0].item():.6f} lam_B={lam[1].item():.6f}", flush=True)
print("states -> runs/cat-calibration-states.json ; lambda -> runs/cat-lambda-trajectory.json", flush=True)
