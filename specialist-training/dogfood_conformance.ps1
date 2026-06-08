# OOD dogfood for the conformance watcher — serve one adapter, score the FRESH (independently-authored,
# cross-adjudicated) cases via dogfood_conformance.py, tear down. Run for BOTH v1 and v0.2 to test
# whether the v0.2 L4 lift GENERALIZES or is exam-fit (the verifier-v2 lesson). Mirrors
# certify_conformance.ps1's serve path. Usage: .\dogfood_conformance.ps1 <adapter> <label> [port]
$ErrorActionPreference = 'Continue'
$img   = 'ghcr.io/ggml-org/llama.cpp:full-cuda'
$cases = '/mnt/e/AI/role-os/tools/conformance-dataset/ood/fresh_cases.jsonl'
$dog   = '/mnt/e/AI/role-os/tools/conformance-dataset/dogfood_conformance.py'
$snapHash = (wsl -d Ubuntu -- bash -lc 'ls /mnt/e/AI-Models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/ 2>/dev/null | head -1').Trim()
$snap = "/models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/$snapHash"
$adapter = if ($args.Count -ge 1) { $args[0] } else { 'conformance-14b-soup-v0.2' }
$label   = if ($args.Count -ge 2) { $args[1] } else { 'v0.2' }
$port    = if ($args.Count -ge 3) { [int]$args[2] } else { 8092 }
New-Item -ItemType Directory -Force -Path 'E:\AI\role-os\tools\conformance-dataset\ood' | Out-Null

docker rm -f cfdogserve 2>$null | Out-Null
if (-not (Test-Path "E:\AI-Models\adapters\$adapter.gguf")) {
  Write-Host "[$label] converting adapter -> GGUF"
  docker run --rm -v E:/AI-Models:/models -e HF_HUB_OFFLINE=1 --entrypoint python3 $img `
    /app/convert_lora_to_gguf.py "/models/adapters/$adapter" --base $snap `
    --outfile "/models/adapters/$adapter.gguf" 2>&1 | Select-Object -Last 2
}
docker run -d --name cfdogserve --gpus all -v E:/AI-Models:/models -p "${port}:${port}" `
  --entrypoint /app/llama-server $img -m /models/gguf/Qwen3-14B-Q4_K_M.gguf `
  --lora-init-without-apply --lora "/models/adapters/$adapter.gguf" `
  --host 0.0.0.0 --port $port -ngl 99 -c 2048 --jinja | Out-Null
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready = $true; break }
  catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { Write-Host "[$label] server NOT ready"; docker logs --tail 15 cfdogserve 2>&1; docker rm -f cfdogserve 2>$null | Out-Null; return }
try { Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null } catch {}
Write-Host "[$label] scoring OOD dogfood ($port) @ lora-scale 4.0"
wsl -d Ubuntu -- bash -lc "python3 $dog --endpoint http://localhost:$port --cases $cases --label $label --out /mnt/e/AI/role-os/tools/conformance-dataset/ood/dogfood-$label.json"
docker rm -f cfdogserve 2>$null | Out-Null
Write-Host "CONFORMANCE_DOGFOOD_DONE ($label)"
