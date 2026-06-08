# Persistent serve of the validated budgeter: llama.cpp (Qwen3-14B-Q4 + budgeter-14b600-soup) on :8090,
# rsLoRA adapter applied at --lora scale 4 (converter bakes alpha/r; rsLoRA needs ~4x). Leaves the
# container 'budgeter-serve' running. Pair with verify_shim.py on :8000 for the role-os gate contract.
$ErrorActionPreference = 'Continue'
$img = 'ghcr.io/ggml-org/llama.cpp:full-cuda'; $port = 8090
docker rm -f budgeter-serve 2>$null | Out-Null
docker run -d --name budgeter-serve --gpus all -v E:/AI-Models:/models -p "${port}:${port}" `
  --entrypoint /app/llama-server $img -m /models/gguf/Qwen3-14B-Q4_K_M.gguf `
  --lora-init-without-apply --lora /models/adapters/budgeter-14b600-soup.gguf `
  --host 0.0.0.0 --port $port -ngl 99 -c 2048 --jinja | Out-Null
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
  try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready = $true; break }
  catch { Start-Sleep -Seconds 2 }
}
if ($ready) {
  Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post `
    -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null
  Write-Host "budgeter served on :$port @ lora-scale 4 (container: budgeter-serve)"
} else { Write-Host "serve NOT ready"; docker logs --tail 20 budgeter-serve 2>&1 }
