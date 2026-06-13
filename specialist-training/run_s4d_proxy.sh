#!/usr/bin/env bash
# S4d proxy sweep (RUN-PLAN-s4d.md). ref runs FIRST = ANDON harness control:
# REF flip < 0.867 -> halt, do not interpret downstream numbers.
set -uo pipefail
source ~/bp-env/bin/activate
cd /mnt/e/AI/gpu-container/specialist-training
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
rm -f logs/s4d_proxy.DONE
python l2_proxy.py 30 \
  ref:/mnt/e/AI-Models/adapters/budgeter-14b600-soup \
  base:/mnt/e/AI-Models/adapters/budgeter-conformance-joint-soup \
  neg05:/mnt/e/AI-Models/adapters/joint-soup-neg-conf-l05 \
  neg10:/mnt/e/AI-Models/adapters/joint-soup-neg-conf-l10 \
  2>&1 | tee logs/s4d_proxy.log
RC=${PIPESTATUS[0]}
echo "rc=$RC" > logs/s4d_proxy.DONE
