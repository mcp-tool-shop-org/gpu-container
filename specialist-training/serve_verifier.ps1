# Persistent serve of the validated verifier SOUP: llama.cpp (Qwen3-14B-Q4 + verifier-14b600-soup) on
# :8092, rsLoRA adapter applied at --lora scale 4 (converter bakes alpha/r; rsLoRA needs ~4x). Leaves the
# container 'verifier-serve' running. Pair with the groundedness LocalVerifierProvider / shim for prism's
# CITATION lens (set PRISM_LOCAL_VERIFIER_ENDPOINT at it). Requires verifier-14b600-soup.gguf (produced by
# certify_all_verifier.ps1's convert step). WSL/Docker path; never run while training.
$ErrorActionPreference = 'Continue'
$img = 'ghcr.io/ggml-org/llama.cpp:full-cuda'; $port = 8092
if (-not (Test-Path 'E:\AI-Models\adapters\verifier-14b600-soup.gguf')) {
  Write-Host "MISSING verifier-14b600-soup.gguf — run certify_all_verifier.ps1 (it converts the soup) first"; return
}
docker rm -f verifier-serve 2>$null | Out-Null
docker run -d --name verifier-serve --gpus all -v E:/AI-Models:/models -p "${port}:${port}" `
  --entrypoint /app/llama-server $img -m /models/gguf/Qwen3-14B-Q4_K_M.gguf `
  --lora-init-without-apply --lora /models/adapters/verifier-14b600-soup.gguf `
  --host 0.0.0.0 --port $port -ngl 99 -c 2048 --jinja | Out-Null
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
  try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready = $true; break }
  catch { Start-Sleep -Seconds 2 }
}
if ($ready) {
  Invoke-RestMethod "http://localhost:$port/lora-adapters" -Method Post `
    -Body '[{"id":0,"scale":4.0}]' -ContentType 'application/json' | Out-Null
  Write-Host "verifier served on :$port @ lora-scale 4 (container: verifier-serve)"
} else { Write-Host "serve NOT ready"; docker logs --tail 20 verifier-serve 2>&1 }
