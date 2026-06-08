# Persistent serve of the validated Sycophancy SOUP: llama.cpp (Qwen3-14B-Q4 + sycophancy-14b-soup) on
# :8095, rsLoRA adapter applied at --lora scale 4. Leaves container 'sycophancy-serve' running. Point
# prism at it with PRISM_SYCOPHANCY_ENDPOINT=http://localhost:8095 (the lens wiring opt-in). Requires
# sycophancy-14b-soup.gguf (produced by certify_all_sycophancy.ps1's convert step). Never serve while training.
$ErrorActionPreference = 'Continue'
$img = 'ghcr.io/ggml-org/llama.cpp:full-cuda'; $port = 8095
if (-not (Test-Path 'E:\AI-Models\adapters\sycophancy-14b-soup.gguf')) {
  Write-Host "MISSING sycophancy-14b-soup.gguf — run certify_all_sycophancy.ps1 (it converts the soup) first"; return
}
docker rm -f sycophancy-serve 2>$null | Out-Null
docker run -d --name sycophancy-serve --gpus all -v E:/AI-Models:/models -p "${port}:${port}" `
  --entrypoint /app/llama-server $img -m /models/gguf/Qwen3-14B-Q4_K_M.gguf `
  --lora-init-without-apply --lora /models/adapters/sycophancy-14b-soup.gguf `
  --host 0.0.0.0 --port $port -ngl 99 -c 2048 --jinja | Out-Null
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
  try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready = $true; break }
  catch { Start-Sleep -Seconds 2 }
}
if ($ready) {
  Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post `
    -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null
  Write-Host "sycophancy served on :$port @ lora-scale 4 (container: sycophancy-serve)"
} else { Write-Host "serve NOT ready"; docker logs --tail 20 sycophancy-serve 2>&1 }
