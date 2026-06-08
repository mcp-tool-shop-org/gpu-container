# Sycophancy watcher v0.2 train launcher — 2 seeds, under the rig-safety watchdog. Reuses
# train_verifier.sh VERBATIM (data-parametric). v0.2 = the L4-expanded dataset (392 L4 records vs v1's
# 214; 1148 train) to lift the agreement-precision rung (v1 OOD L4 flip 0.595). batch2/accum8 for the
# ~530-590 tok seqs. PRECONDITIONS: dataset audit PASS; 5090 CLEAR (serve stopped, ollama clear); never
# train + serve concurrently.
$ErrorActionPreference = 'Stop'
$dir = 'E:/AI/prism-verify/specialist/dataset'
$log = "$dir/train_sycophancy_v02.console.log"
$bash = 'BUDGETER_TAG=sycophancy-14b-v0.2 ' +
        "BUDGETER_DATA=/mnt/e/AI/prism-verify/specialist/dataset/sycophancy_v02_train_sft.jsonl " +
        'BUDGETER_BATCH=2 BUDGETER_ACCUM=8 ' +
        'bash /mnt/e/AI/gpu-container/specialist-training/train_verifier.sh'

Write-Host "=== sycophancy v0.2 train START (2 seeds 42/1337) ==="
python -m gpu_container.watchdog run --on-breach wsl-shutdown `
  --power-max 100 --temp-max 87 --host-mem-max 80 --interval 10 `
  --peaks-out "$dir/train_peaks_sycophancy_v02.json" `
  --log "$dir/train_sycophancy_v02.watchdog.log" `
  -- wsl -d Ubuntu -- bash -lc $bash 2>&1 | Tee-Object -FilePath $log
Write-Host "=== watchdog exited (code $LASTEXITCODE) ==="
