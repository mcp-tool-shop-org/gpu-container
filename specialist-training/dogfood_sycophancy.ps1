# Sycophancy OOD dogfood (the MANDATORY generalization gate) — serve the SOUP and score it on the
# INDEPENDENT OOD set (novel domains never in train/exam) with the same cost-asymmetric scorer. This is
# the gate that twice caught over-fit specialists (exam != generalization). Run AFTER the exam cert; GPU free.
$ErrorActionPreference = 'Continue'
$img  = 'ghcr.io/ggml-org/llama.cpp:full-cuda'
$ood  = '/mnt/e/AI/prism-verify/specialist/dataset/sycophancy_ood.jsonl'
$cert = '/mnt/e/AI/prism-verify/specialist/dataset/certify_sycophancy.py'
$adapter = 'sycophancy-14b-soup'
$port = 8091
docker rm -f sdogserve 2>$null | Out-Null
if (-not (Test-Path "E:\AI-Models\adapters\$adapter.gguf")) {
  $snapHash = (wsl -d Ubuntu -- bash -lc 'ls /mnt/e/AI-Models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/ 2>/dev/null | head -1').Trim()
  $snap = "/models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/$snapHash"
  Write-Host "converting $adapter -> GGUF"
  docker run --rm -v E:/AI-Models:/models -e HF_HUB_OFFLINE=1 --entrypoint python3 $img `
    /app/convert_lora_to_gguf.py "/models/adapters/$adapter" --base $snap `
    --outfile "/models/adapters/$adapter.gguf" 2>&1 | Select-Object -Last 2
}
docker run -d --name sdogserve --gpus all -v E:/AI-Models:/models -p "${port}:${port}" `
  --entrypoint /app/llama-server $img -m /models/gguf/Qwen3-14B-Q4_K_M.gguf `
  --lora-init-without-apply --lora "/models/adapters/$adapter.gguf" `
  --host 0.0.0.0 --port $port -ngl 99 -c 2048 --jinja | Out-Null
$ready = $false
for ($i=0; $i -lt 60; $i++) {
  try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready=$true; break }
  catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { Write-Host "server NOT ready"; docker logs --tail 15 sdogserve 2>&1; docker rm -f sdogserve 2>$null | Out-Null; return }
try { Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null } catch {}
Write-Host "[OOD dogfood] scoring $($adapter) on the OOD set @ lora-scale 4.0"
wsl -d Ubuntu -- bash -lc "python3 $cert --endpoint http://localhost:$port --exam $ood --label sycophancy-ood-soup --out /mnt/e/AI/prism-verify/specialist/dataset/certify/sycophancy-ood-soup.json"
docker rm -f sdogserve 2>$null | Out-Null
Write-Host 'OOD_DOGFOOD_DONE'
