# Conformance watcher certification: convert the soup -> GGUF -> serve (Docker llama.cpp, --lora scale 4
# on :8091) -> score the held-out tool-call conformance exam via certify_conformance.py (cost-asymmetric
# flip-consistency on the 10 UNSEEN tools) -> teardown. Run AFTER soup. Mirrors certify_all_verifier.ps1.
# Out -> role-os/tools/conformance-dataset/certify/<label>.json.  Usage: .\certify_conformance.ps1 [adapter] [label]
$ErrorActionPreference = 'Continue'
$img  = 'ghcr.io/ggml-org/llama.cpp:full-cuda'
$exam = '/mnt/e/AI/role-os/tools/conformance-dataset/conformance_exam_records.jsonl'
$cert = '/mnt/e/AI/role-os/tools/conformance-dataset/certify_conformance.py'
$snapHash = (wsl -d Ubuntu -- bash -lc 'ls /mnt/e/AI-Models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/ 2>/dev/null | head -1').Trim()
$snap = "/models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/$snapHash"
$port = 8091
$adapter = if ($args.Count -ge 1) { $args[0] } else { 'conformance-14b-soup' }
$label   = if ($args.Count -ge 2) { $args[1] } else { 'conformance-soup' }
New-Item -ItemType Directory -Force -Path 'E:\AI\role-os\tools\conformance-dataset\certify' | Out-Null

docker rm -f cfcertserve 2>$null | Out-Null
if (-not (Test-Path "E:\AI-Models\adapters\$adapter.gguf")) {
  Write-Host "[$label] converting adapter -> GGUF"
  docker run --rm -v E:/AI-Models:/models -e HF_HUB_OFFLINE=1 --entrypoint python3 $img `
    /app/convert_lora_to_gguf.py "/models/adapters/$adapter" --base $snap `
    --outfile "/models/adapters/$adapter.gguf" 2>&1 | Select-Object -Last 2
}
docker run -d --name cfcertserve --gpus all -v E:/AI-Models:/models -p "${port}:${port}" `
  --entrypoint /app/llama-server $img -m /models/gguf/Qwen3-14B-Q4_K_M.gguf `
  --lora-init-without-apply --lora "/models/adapters/$adapter.gguf" `
  --host 0.0.0.0 --port $port -ngl 99 -c 2048 --jinja | Out-Null
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready = $true; break }
  catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { Write-Host "[$label] server NOT ready"; docker logs --tail 15 cfcertserve 2>&1; docker rm -f cfcertserve 2>$null | Out-Null; return }
try { Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null } catch {}
Write-Host "[$label] scoring conformance exam ($port) @ lora-scale 4.0"
wsl -d Ubuntu -- bash -lc "python3 $cert --endpoint http://localhost:$port --exam $exam --label $label --out /mnt/e/AI/role-os/tools/conformance-dataset/certify/$label.json"
docker rm -f cfcertserve 2>$null | Out-Null
Write-Host 'CONFORMANCE_CERTIFY_DONE'
