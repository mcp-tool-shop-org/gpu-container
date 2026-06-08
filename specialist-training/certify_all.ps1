# Budgeter certification orchestration: for base + each seed, convert (if adapter) -> serve (Docker
# llama.cpp) -> score the held-out puzzle exam via certify.py -> stop. Sequential (one server at a
# time; ~4GB VRAM each). Results -> certify/<label>.json.
$ErrorActionPreference = 'Continue'
$img  = 'ghcr.io/ggml-org/llama.cpp:full-cuda'
$exam = '/mnt/e/AI/role-os/tools/token-budget-dataset/dataset/v0.1/puzzles/puzzles_exam.jsonl'
$snapHash = (wsl -d Ubuntu -- bash -lc 'ls /mnt/e/AI-Models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/ 2>/dev/null | head -1').Trim()
$snap = "/models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/$snapHash"
$port = 8090
New-Item -ItemType Directory -Force -Path 'E:\AI\gpu-container\specialist-training\certify' | Out-Null

function Certify-One($label, $adapter) {
  docker rm -f certserve 2>$null | Out-Null
  if ($adapter) {
    Write-Host "[$label] converting adapter -> GGUF"
    docker run --rm -v E:/AI-Models:/models -e HF_HUB_OFFLINE=1 --entrypoint python3 $img `
      /app/convert_lora_to_gguf.py "/models/adapters/$adapter" --base $snap `
      --outfile "/models/adapters/$adapter.gguf" 2>&1 | Select-Object -Last 2
  }
  $dargs = @('run','-d','--name','certserve','--gpus','all','-v','E:/AI-Models:/models','-p',"${port}:${port}",
             '--entrypoint','/app/llama-server',$img,'-m','/models/gguf/Qwen3-14B-Q4_K_M.gguf')
  if ($adapter) { $dargs += @('--lora-init-without-apply', '--lora', "/models/adapters/$adapter.gguf") }
  $dargs += @('--host','0.0.0.0','--port',"$port",'-ngl','99','-c','2048','--jinja')
  docker @dargs | Out-Null
  $ready = $false
  for ($i=0; $i -lt 60; $i++) {
    try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready=$true; break }
    catch { Start-Sleep -Seconds 2 }
  }
  if (-not $ready) { Write-Host "[$label] server NOT ready"; docker logs --tail 15 certserve 2>&1; docker rm -f certserve 2>$null | Out-Null; return }
  if ($adapter) { try { Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null } catch {} }
  Write-Host "[$label] scoring exam ($port) @ lora-scale 4.0"
  wsl -d Ubuntu -- bash -lc "python3 /mnt/e/AI/gpu-container/specialist-training/certify.py --endpoint http://localhost:$port --exam $exam --label $label --out /mnt/e/AI/gpu-container/specialist-training/certify/$label.json"
  docker rm -f certserve 2>$null | Out-Null
}

# Certify-One 'base' $null   # base = 0.0 (doesn't emit the terse format) — skip on re-runs
if ($args.Count -ge 2) {
  Certify-One $args[0] $args[1]   # one-off: .\certify_all.ps1 <label> <adapter-dir>
} else {
  Certify-One 'seed42-14b600'   'budgeter-14b600-seed42'
  Certify-One 'seed1337-14b600' 'budgeter-14b600-seed1337'
}
Write-Host 'ALL_CERTIFY_DONE'
