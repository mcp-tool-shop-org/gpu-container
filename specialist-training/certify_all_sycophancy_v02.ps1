# Sycophancy v0.2 certification: seed42 / seed1337 / soup -> convert -> serve (lora scale 4) -> score the
# SAME held-out exam as v1 (sycophancy_v02_exam_records.jsonl == the v1 exam domains) via certify_sycophancy.py.
# For the SOUP, also score the SAME OOD set (sycophancy_ood.jsonl) in the same serve -> the v1-vs-v0.2 L4
# comparison is apples-to-apples. Results -> certify/sycophancy-v02-<label>.json. GPU free; never serve while training.
$ErrorActionPreference = 'Continue'
$img  = 'ghcr.io/ggml-org/llama.cpp:full-cuda'
$exam = '/mnt/e/AI/prism-verify/specialist/dataset/sycophancy_v02_exam_records.jsonl'
$ood  = '/mnt/e/AI/prism-verify/specialist/dataset/sycophancy_ood.jsonl'
$cert = '/mnt/e/AI/prism-verify/specialist/dataset/certify_sycophancy.py'
$snapHash = (wsl -d Ubuntu -- bash -lc 'ls /mnt/e/AI-Models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/ 2>/dev/null | head -1').Trim()
$snap = "/models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/$snapHash"
$port = 8091
$seed42 = 'budgeter-sycophancy-14b-v0.2-seed42'; $seed1337 = 'budgeter-sycophancy-14b-v0.2-seed1337'
$soup = 'sycophancy-14b-v0.2-soup'
New-Item -ItemType Directory -Force -Path 'E:\AI\prism-verify\specialist\dataset\certify' | Out-Null

function Serve($adapter) {
  docker rm -f scertserve 2>$null | Out-Null
  if (-not (Test-Path "E:\AI-Models\adapters\$adapter.gguf")) {
    Write-Host "[$adapter] converting -> GGUF"
    docker run --rm -v E:/AI-Models:/models -e HF_HUB_OFFLINE=1 --entrypoint python3 $img `
      /app/convert_lora_to_gguf.py "/models/adapters/$adapter" --base $snap `
      --outfile "/models/adapters/$adapter.gguf" 2>&1 | Select-Object -Last 2
  }
  docker run -d --name scertserve --gpus all -v E:/AI-Models:/models -p "${port}:${port}" `
    --entrypoint /app/llama-server $img -m /models/gguf/Qwen3-14B-Q4_K_M.gguf `
    --lora-init-without-apply --lora "/models/adapters/$adapter.gguf" `
    --host 0.0.0.0 --port $port -ngl 99 -c 2048 --jinja | Out-Null
  for ($i=0; $i -lt 60; $i++) { try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; break } catch { Start-Sleep -Seconds 2 } }
  try { Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null } catch {}
}
function Score($label, $data) {
  Write-Host "[$label] scoring @ $port"
  wsl -d Ubuntu -- bash -lc "python3 $cert --endpoint http://localhost:$port --exam $data --label $label --out /mnt/e/AI/prism-verify/specialist/dataset/certify/$label.json"
}

Serve $seed42;   Score 'sycophancy-v02-seed42'   $exam; docker rm -f scertserve 2>$null | Out-Null
Serve $seed1337; Score 'sycophancy-v02-seed1337' $exam; docker rm -f scertserve 2>$null | Out-Null
Serve $soup;     Score 'sycophancy-v02-soup' $exam; Score 'sycophancy-v02-ood-soup' $ood; docker rm -f scertserve 2>$null | Out-Null
Write-Host 'ALL_SYCOPHANCY_V02_CERTIFY_DONE'
