#!/usr/bin/env bash
# Verifier (L4 Groundedness) specialist — REAL run, two seeds, the BUDGETER RECIPE VERBATIM.
# Reuses train_budgeter.py (now data-parametric via BUDGETER_DATA) — same proven config that earned the
# budgeter's 0.944/0.866: Qwen3-14B (QLoRA 4-bit), rsLoRA r16/alpha32, lr 1e-4, wd 0.01 DEFAULT,
# batch4 x grad_accum4 (eff 16) + gradient_checkpointing, 600 steps (~6 epochs, the grokking budget).
# Output to ext4 ~/bp-runs -> copy to E: adapters. Soup the two seeds (soup_adapters.py), serve the
# rsLoRA at llama.cpp --lora scale 4. WSL path ONLY (the rig-safety kill switch is wsl --shutdown).
#
# DO NOT run this bare. Launch it UNDER the host-side watchdog from WINDOWS so a thermal/power/host-mem
# breach nukes the VM (the only kill switch that reaches WSL training):
#
#   python -m gpu_container.watchdog run --on-breach wsl-shutdown \
#       --power-max 100 --temp-max 87 --host-mem-max 80 --interval 10 \
#       --peaks-out E:/AI/prism-verify/specialist/dataset/train_peaks.json \
#       -- wsl -d Ubuntu -- bash -lc 'bash /mnt/e/AI/gpu-container/specialist-training/train_verifier.sh'
#
# (--power-max 100: efficient 14B training legitimately draws ~95% power at a SAFE ~73C; the default 95
#  aborts good runs. --temp-max 87 is the real guard. RESULTS.md finding #5.)
# PRECONDITIONS: dataset audit PASS + director eyeball; Ollama VRAM FREED (`ollama stop <model>` — never
# train while Ollama holds the card); nothing else serving on the 5090 (never train + serve concurrently).
set -euo pipefail
source ~/bp-env/bin/activate
export BUDGETER_BASE="${BUDGETER_BASE:-Qwen/Qwen3-14B}"
export BUDGETER_TAG="${BUDGETER_TAG:-verifier-14b600}"
export BUDGETER_DATA="${BUDGETER_DATA:-/mnt/e/AI/prism-verify/specialist/dataset/verifier_train_sft.jsonl}"
export BUDGETER_STEPS="${BUDGETER_STEPS:-600}"
test -f "$BUDGETER_DATA" || { echo "MISSING SFT: $BUDGETER_DATA (run build_verifier_dataset.py first)"; exit 2; }
mkdir -p /mnt/e/AI-Models/adapters
echo "=== VERIFIER TRAIN base=$BUDGETER_BASE tag=$BUDGETER_TAG steps=$BUDGETER_STEPS data=$BUDGETER_DATA ==="
for SEED in 42 1337; do
  echo "=== SEED $SEED START $(date +%H:%M:%S) ==="
  rm -rf "$HOME/bp-runs/budgeter-$BUDGETER_TAG-seed$SEED"   # clear any partial from an aborted run
  python /mnt/e/AI/gpu-container/specialist-training/train_budgeter.py "$SEED" "$BUDGETER_STEPS"
  rm -rf "/mnt/e/AI-Models/adapters/budgeter-$BUDGETER_TAG-seed$SEED"
  cp -r "$HOME/bp-runs/budgeter-$BUDGETER_TAG-seed$SEED" "/mnt/e/AI-Models/adapters/budgeter-$BUDGETER_TAG-seed$SEED"
  echo "=== SEED $SEED DONE $(date +%H:%M:%S) ==="
done
echo "ALL_SEEDS_DONE — next: soup_adapters.py then convert to gguf + serve @ --lora scale 4"
