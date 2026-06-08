# Sycophancy watcher (wedge #2) train launcher — 2 seeds (42, 1337) of the proven mint, under the
# host-side rig-safety watchdog (the ONLY kill switch that reaches WSL training: --on-breach wsl-shutdown).
# Reuses train_verifier.sh VERBATIM (data-parametric) — only the tag + data path change.
#
# BATCH NOTE: sycophancy (context+response, short NL) sequences are shorter than conformance's ~600-tok
# tool-schemas, so the train_budgeter.py default batch4/accum4 (eff 16) is expected to fit. If a seq-length
# measure shows long tails, prepend 'BUDGETER_BATCH=2 BUDGETER_ACCUM=8 ' (eff 16) to $bash. --power-max 100
# (efficient 14B legitimately draws ~95% power at a SAFE ~74C; the real guard is --temp-max 87).
#
# PRECONDITIONS (verify before running): dataset audit PASS; 5090 CLEAR — `ollama stop` every model
# (prism's mistral-small:24b groundedness run may still hold the card) and no docker serve; the iGPU
# sidecar on GPU.0 is fine alongside a 5090 train. Never train + serve concurrently.
$ErrorActionPreference = 'Stop'
$dir = 'E:/AI/prism-verify/specialist/dataset'
$log = "$dir/train_sycophancy.console.log"
# Measured seq length p99 ~531 tok / max ~590 tok (like conformance ~600) -> batch2/accum8 (eff 16) to
# avoid the batch4 98%-VRAM OOM. RESULTS.md finding #3.
$bash = 'BUDGETER_TAG=sycophancy-14b600 ' +
        "BUDGETER_DATA=/mnt/e/AI/prism-verify/specialist/dataset/sycophancy_train_sft.jsonl " +
        'BUDGETER_BATCH=2 BUDGETER_ACCUM=8 ' +
        'bash /mnt/e/AI/gpu-container/specialist-training/train_verifier.sh'

Write-Host "=== sycophancy train START (2 seeds 42/1337) ==="
python -m gpu_container.watchdog run --on-breach wsl-shutdown `
  --power-max 100 --temp-max 87 --host-mem-max 80 --interval 10 `
  --peaks-out "$dir/train_peaks_sycophancy.json" `
  --log "$dir/train_sycophancy.watchdog.log" `
  -- wsl -d Ubuntu -- bash -lc $bash 2>&1 | Tee-Object -FilePath $log
Write-Host "=== watchdog exited (code $LASTEXITCODE) ==="
