$ErrorActionPreference = 'Continue'
docker ps *> $null
if ($LASTEXITCODE -eq 0) { Write-Host 'docker already up'; return }
Write-Host 'docker down — starting Docker Desktop'
$exe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $exe) { Start-Process $exe } else { Write-Host "Docker Desktop exe not at $exe"; return }
for ($i = 0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 3
  docker ps *> $null
  if ($LASTEXITCODE -eq 0) { Write-Host "docker UP after ~$([int]($i * 3 + 3))s"; return }
}
Write-Host 'docker STILL DOWN after ~4.5min'
