#!/usr/bin/env bash
# Token Budget Analyst — REAL run, two seeds, via the Python Trainer API. Model-parametric:
# BUDGETER_BASE / BUDGETER_TAG select the base (default Qwen3-14B for the arithmetic rungs L1/L2,
# where a 4B sat at chance). 14B: batch1 x grad_accum16 (eff 16), rsLoRA r16/alpha32, no-packing,
# 300 steps (~3 epochs over 1633). Output to ext4 ~/bp-runs -> copy to E: adapters.
# Serve the rsLoRA adapter at llama.cpp --lora scale 4 (converter bakes alpha/r, not alpha/sqrt(r)).
set -euo pipefail
source ~/bp-env/bin/activate
export BUDGETER_BASE="${BUDGETER_BASE:-Qwen/Qwen3-14B}"
export BUDGETER_TAG="${BUDGETER_TAG:-14b}"
mkdir -p /mnt/e/AI-Models/adapters
for SEED in 42 1337; do
  echo "=== SEED $SEED START $(date +%H:%M:%S) base=$BUDGETER_BASE tag=$BUDGETER_TAG ==="
  rm -rf "$HOME/bp-runs/budgeter-$BUDGETER_TAG-seed$SEED"   # clear any partial from an aborted run
  python /mnt/e/AI/gpu-container/specialist-training/train_budgeter.py "$SEED" "${BUDGETER_STEPS:-600}"  # 600 = grokking budget for L2
  rm -rf "/mnt/e/AI-Models/adapters/budgeter-$BUDGETER_TAG-seed$SEED"
  cp -r "$HOME/bp-runs/budgeter-$BUDGETER_TAG-seed$SEED" "/mnt/e/AI-Models/adapters/budgeter-$BUDGETER_TAG-seed$SEED"
  echo "=== SEED $SEED DONE $(date +%H:%M:%S) ==="
done
echo "ALL_SEEDS_DONE"
