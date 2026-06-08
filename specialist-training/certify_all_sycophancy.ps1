# Sycophancy watcher certification: for each of seed42 / seed1337 / soup -> convert adapter to GGUF ->
# serve (Docker llama.cpp, --lora scale 4) -> score the held-out DOMAIN-atomic exam via
# certify_sycophancy.py (cost-asymmetric flip-consistency) -> stop. Sequential. Results ->
# prism-verify/specialist/dataset/certify/<label>.json. Mirrors certify_all_verifier.ps1. GPU free; never
# serve while training. The soup must already exist (built by soup_adapters.py).
$ErrorActionPreference = 'Continue'
$img  = 'ghcr.io/ggml-org/llama.cpp:full-cuda'
$exam = '/mnt/e/AI/prism-verify/specialist/dataset/sycophancy_exam_records.jsonl'
$cert = '/mnt/e/AI/prism-verify/specialist/dataset/certify_sycophancy.py'
$snapHash = (wsl -d Ubuntu -- bash -lc 'ls /mnt/e/AI-Models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/ 2>/dev/null | head -1').Trim()
$snap = "/models/hf-cache/hub/models--Qwen--Qwen3-14B/snapshots/$snapHash"
$port = 8091
$seed42   = 'budgeter-sycophancy-14b600-seed42'
$seed1337 = 'budgeter-sycophancy-14b600-seed1337'
$soup     = 'sycophancy-14b-soup'
New-Item -ItemType Directory -Force -Path 'E:\AI\prism-verify\specialist\dataset\certify' | Out-Null

function Certify-One($label, $adapter) {
  docker rm -f scertserve 2>$null | Out-Null
  if (-not (Test-Path "E:\AI-Models\adapters\$adapter.gguf")) {
    Write-Host "[$label] converting adapter -> GGUF"
    docker run --rm -v E:/AI-Models:/models -e HF_HUB_OFFLINE=1 --entrypoint python3 $img `
      /app/convert_lora_to_gguf.py "/models/adapters/$adapter" --base $snap `
      --outfile "/models/adapters/$adapter.gguf" 2>&1 | Select-Object -Last 2
  }
  $dargs = @('run','-d','--name','scertserve','--gpus','all','-v','E:/AI-Models:/models','-p',"${port}:${port}",
             '--entrypoint','/app/llama-server',$img,'-m','/models/gguf/Qwen3-14B-Q4_K_M.gguf',
             '--lora-init-without-apply','--lora',"/models/adapters/$adapter.gguf",
             '--host','0.0.0.0','--port',"$port",'-ngl','99','-c','2048','--jinja')
  docker @dargs | Out-Null
  $ready = $false
  for ($i=0; $i -lt 60; $i++) {
    try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready=$true; break }
    catch { Start-Sleep -Seconds 2 }
  }
  if (-not $ready) { Write-Host "[$label] server NOT ready"; docker logs --tail 15 scertserve 2>&1; docker rm -f scertserve 2>$null | Out-Null; return }
  try { Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null } catch {}
  Write-Host "[$label] scoring sycophancy exam ($port) @ lora-scale 4.0"
  wsl -d Ubuntu -- bash -lc "python3 $cert --endpoint http://localhost:$port --exam $exam --label $label --out /mnt/e/AI/prism-verify/specialist/dataset/certify/$label.json"
  docker rm -f scertserve 2>$null | Out-Null
}

if ($args.Count -ge 2) {
  Certify-One $args[0] $args[1]    # one-off: .\certify_all_sycophancy.ps1 <label> <adapter-dir>
} else {
  Certify-One 'sycophancy-seed42'   $seed42
  Certify-One 'sycophancy-seed1337' $seed1337
  Certify-One 'sycophancy-soup'     $soup
}
Write-Host 'ALL_SYCOPHANCY_CERTIFY_DONE'
