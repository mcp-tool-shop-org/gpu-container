$ErrorActionPreference = 'Continue'
$img = 'ghcr.io/ggml-org/llama.cpp:full-cuda'; $port = 8090
docker rm -f certserve 2>$null | Out-Null
docker run -d --name certserve --gpus all -v E:/AI-Models:/models -p "${port}:${port}" `
  --entrypoint /app/llama-server $img -m /models/gguf/Qwen3-4B-Q4_K_M.gguf `
  --lora-init-without-apply --lora /models/adapters/budgeter-v0.1-seed42.gguf --host 0.0.0.0 --port $port -ngl 99 -c 2048 --jinja | Out-Null
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready = $true; break }
  catch { Start-Sleep -Seconds 2 }
}
if ($ready) { wsl -d Ubuntu -- bash -lc 'python3 /mnt/e/AI/gpu-container/specialist-training/diag.py' }
else { docker logs --tail 15 certserve 2>&1 }
docker rm -f certserve 2>$null | Out-Null
