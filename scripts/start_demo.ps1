Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$logDir = Join-Path $projectRoot "tmp"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "1/3 Starting local dependencies (PostgreSQL / Redis / MinIO)..."
& (Join-Path $PSScriptRoot "start_local_deps.ps1")

Write-Host "2/3 Starting backend on http://127.0.0.1:18000 ..."
$env:PYTHONPATH = "$backendRoot\.deps;$backendRoot"
$backendLog = Join-Path $logDir "demo-backend.log"
Start-Process -FilePath "D:\python3.12\python.exe" `
  -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "18000") `
  -WorkingDirectory $backendRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $backendLog `
  -RedirectStandardError $backendLog

Write-Host "3/3 Starting frontend on http://127.0.0.1:15173 ..."
$frontendLog = Join-Path $logDir "demo-frontend.log"
Start-Process -FilePath "npm.cmd" `
  -ArgumentList @("run", "dev") `
  -WorkingDirectory $frontendRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $frontendLog `
  -RedirectStandardError $frontendLog

Write-Host ""
Write-Host "Demo is starting:"
Write-Host "- Frontend: http://127.0.0.1:15173"
Write-Host "- Backend:  http://127.0.0.1:18000"
Write-Host "- Logs:     $logDir\demo-backend.log, $logDir\demo-frontend.log"
Write-Host ""
Write-Host "Before starting an interview, configure a real model provider"
Write-Host "(基础配置 -> AI 模型配置) so the HR chat uses LLM mode;"
Write-Host "without a provider, the interview falls back to rule mode."
