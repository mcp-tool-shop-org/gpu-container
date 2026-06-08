# Certify the model-soup adapter (averaged seeds) on the held-out puzzle exam.
$ErrorActionPreference = 'Continue'
$img  = 'ghcr.io/ggml-org/llama.cpp:full-cuda'
$exam = '/mnt/e/AI/role-os/tools/token-budget-dataset/dataset/v0.1/puzzles/puzzles_exam.jsonl'
$snap = '/models/hf-cache/hub/models--Qwen--Qwen3-4B/snapshots/1cfa9a7208912126459214e8b04321603b3df60c'
$port = 8090
$adapter = 'budgeter-v0.1-soup'
docker rm -f certserve 2>$null | Out-Null
Write-Host "[$adapter] converting -> GGUF"
docker run --rm -v E:/AI-Models:/models -e HF_HUB_OFFLINE=1 --entrypoint python3 $img `
  /app/convert_lora_to_gguf.py "/models/adapters/$adapter" --base $snap --outfile "/models/adapters/$adapter.gguf" 2>&1 | Select-Object -Last 2
$dargs = @('run','-d','--name','certserve','--gpus','all','-v','E:/AI-Models:/models','-p',"${port}:${port}",
           '--entrypoint','/app/llama-server',$img,'-m','/models/gguf/Qwen3-4B-Q4_K_M.gguf',
           '--lora',"/models/adapters/$adapter.gguf",'--host','0.0.0.0','--port',"$port",'-ngl','99','-c','2048','--jinja')
docker @dargs | Out-Null
$ready=$false; for ($i=0; $i -lt 60; $i++) { try { Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 3 | Out-Null; $ready=$true; break } catch { Start-Sleep -Seconds 2 } }
if (-not $ready) { Write-Host 'soup server NOT ready'; docker logs --tail 15 certserve 2>&1; docker rm -f certserve 2>$null | Out-Null; exit }
Write-Host "[$adapter] scoring exam"
wsl -d Ubuntu -- bash -lc "python3 /mnt/e/AI/gpu-container/specialist-training/certify.py --endpoint http://localhost:$port --exam $exam --label soup --out /mnt/e/AI/gpu-container/specialist-training/certify/soup.json"
docker rm -f certserve 2>$null | Out-Null
Write-Host 'SOUP_CERTIFY_DONE'
