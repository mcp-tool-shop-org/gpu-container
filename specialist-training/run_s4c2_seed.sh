#!/usr/bin/env bash
# S4c-2 one-seed runner (attended). Usage: bash run_s4c2_seed.sh <seed> [steps]
set -uo pipefail
source ~/bp-env/bin/activate
cd /mnt/e/AI/gpu-container/specialist-training
SEED="${1:?seed}"
STEPS="${2:-800}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
rm -rf "$HOME/bp-runs/budgeter-s4c2-seed$SEED"
python train_s4c2.py "$SEED" "$STEPS" 2>&1 | tee "logs/s4c2_seed$SEED.log" | tail -3
RC=${PIPESTATUS[0]}
if [ "$RC" -eq 0 ]; then
  rm -rf "/mnt/e/AI-Models/adapters/budgeter-s4c2-seed$SEED"
  cp -r "$HOME/bp-runs/budgeter-s4c2-seed$SEED" "/mnt/e/AI-Models/adapters/budgeter-s4c2-seed$SEED"
  echo "SEED_${SEED}_DONE"
else
  echo "SEED_${SEED}_FAILED rc=$RC"
fi
exit "$RC"
