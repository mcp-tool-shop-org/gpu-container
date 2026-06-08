# v0.2 conformance retrain launcher — 2 seeds (42, 1337) of the proven mint, under the host-side
# rig-safety watchdog (the ONLY kill switch that reaches WSL training: --on-breach wsl-shutdown).
# Goal: lift the L4 soft rung (v1 = 0.9 acc / 0.8 flip / 2 false-conformants) with the v0.2 dataset
# (40 new self-contained cross-field relational clauses + 8 STATE-fixed referential tools).
#
# Recipe = v1 VERBATIM except batch2/accum8 (eff batch still 16): the ~600-tok tool-schema sequences
# OOM at batch4 (98% VRAM). --power-max 100 (efficient 14B legitimately draws ~95% power at a SAFE
# ~74C; the real guard is --temp-max 87). Preconditions verified: dataset audit PASS + label-check
# PASS; 5090 clear (no Ollama model, no docker serve); iGPU sidecar is on GPU.0, not the training card.
$ErrorActionPreference = 'Stop'
$log = 'E:/AI/role-os/tools/conformance-dataset/train_v0.2.console.log'
$bash = 'BUDGETER_TAG=conformance-14b-v0.2 ' +
        'BUDGETER_DATA=/mnt/e/AI/role-os/tools/conformance-dataset/conformance_train_sft.jsonl ' +
        'BUDGETER_BATCH=2 BUDGETER_ACCUM=8 ' +
        'bash /mnt/e/AI/gpu-container/specialist-training/train_verifier.sh'

Write-Host "=== conformance v0.2 train START (2 seeds, batch2/accum8) ==="
python -m gpu_container.watchdog run --on-breach wsl-shutdown `
  --power-max 100 --temp-max 87 --host-mem-max 80 --interval 10 `
  --peaks-out E:/AI/role-os/tools/conformance-dataset/train_peaks_v0.2.json `
  --log E:/AI/role-os/tools/conformance-dataset/train_v0.2.watchdog.log `
  -- wsl -d Ubuntu -- bash -lc $bash 2>&1 | Tee-Object -FilePath $log
Write-Host "=== watchdog exited (code $LASTEXITCODE) ==="
