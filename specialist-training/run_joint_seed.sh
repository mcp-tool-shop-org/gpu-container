#!/usr/bin/env bash
# S4c joint retrain, one seed, with an in-VM RAM sampler (debugging the step-100/140 OOM kills).
# Usage: bash run_joint_seed.sh <seed> [steps]
set -uo pipefail
source ~/bp-env/bin/activate
cd /mnt/e/AI/gpu-container/specialist-training
SEED="${1:?seed}"
STEPS="${2:-1200}"
mkdir -p logs

( while true; do
    echo "$(date +%H:%M:%S),$(free -m | awk '/^Mem:/{print $3}'),$(free -m | awk '/^Mem:/{print $6}')" >> logs/joint_ram.csv
    sleep 20
  done ) &
RAMPID=$!
trap 'kill $RAMPID 2>/dev/null' EXIT

rm -rf "$HOME/bp-runs/budgeter-joint-seed$SEED"
# batch1 x accum16: the documented 14B geometry (peak ~18GB = headroom under the watchdog's
# 31.2GB WDDM-paging ceiling). batch2 crept 22.5->30.2GB by step ~140 on the long conformance
# rows and tipped over (watchdog abort receipts 02:41/03:10, 2026-06-12). expandable_segments
# tames the variable-length fragmentation creep.
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
BUDGETER_BASE="Qwen/Qwen3-14B" BUDGETER_TAG=joint BUDGETER_SAMPLES=3300 \
BUDGETER_BATCH=1 BUDGETER_ACCUM=16 \
BUDGETER_DATA=/mnt/e/AI/gpu-container/specialist-training/data/joint_train_sft.jsonl \
python train_budgeter.py "$SEED" "$STEPS" 2>&1 | tee "logs/joint_seed$SEED.log" | tail -3
RC=${PIPESTATUS[0]}
if [ "$RC" -eq 0 ]; then
  rm -rf "/mnt/e/AI-Models/adapters/budgeter-joint-seed$SEED"
  cp -r "$HOME/bp-runs/budgeter-joint-seed$SEED" "/mnt/e/AI-Models/adapters/budgeter-joint-seed$SEED"
  echo "SEED_${SEED}_DONE"
else
  echo "SEED_${SEED}_FAILED rc=$RC"
fi
exit "$RC"
