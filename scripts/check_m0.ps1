Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"

function Test-Port {
  param(
    [string] $Name,
    [int] $Port
  )

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (-not $connect.AsyncWaitHandle.WaitOne(3000)) {
      throw "$Name port $Port is not reachable"
    }
    $client.EndConnect($connect)
    Write-Host "$Name port $Port OK"
  }
  finally {
    $client.Close()
  }
}

Write-Host "Checking local dependency ports..."
Test-Port "PostgreSQL" 5432
Test-Port "Redis" 6379
Test-Port "MinIO API" 9000
Test-Port "MinIO Console" 9001

Write-Host "Checking question bank..."
Push-Location $projectRoot
try {
  & "D:\python3.12\python.exe" "scripts\import_question_bank.py"
}
finally {
  Pop-Location
}

Write-Host ""
Write-Host "Checking backend tests..."
Push-Location $backendRoot
try {
  $env:PYTHONPATH = "$backendRoot\.deps;$backendRoot"
  & "D:\python3.12\python.exe" -m pytest -q
  & "$backendRoot\.tools\Scripts\ruff.exe" check app tests alembic\env.py --no-cache
  & "D:\python3.12\python.exe" -m alembic upgrade head
  @'
from sqlalchemy import create_engine, text

url = "postgresql+psycopg://ai_job_agent:ai_job_agent@localhost:5432/ai_job_agent"
engine = create_engine(url)
with engine.connect() as conn:
    version = conn.execute(text("select extversion from pg_extension where extname='vector'")).scalar_one()
    migration = conn.execute(text("select version_num from alembic_version")).scalar_one()
print(f"pgvector={version}; alembic={migration}")
'@ | & "D:\python3.12\python.exe" -
}
finally {
  Pop-Location
}

Write-Host ""
Write-Host "Checking Redis PING..."
$redis = [System.Net.Sockets.TcpClient]::new("127.0.0.1", 6379)
try {
  $stream = $redis.GetStream()
  $bytes = [System.Text.Encoding]::ASCII.GetBytes("PING`r`n")
  $stream.Write($bytes, 0, $bytes.Length)
  $buffer = New-Object byte[] 64
  $read = $stream.Read($buffer, 0, $buffer.Length)
  $redisResponse = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $read).Trim()
  if ($redisResponse -ne "+PONG") {
    throw "Unexpected Redis response: $redisResponse"
  }
  Write-Host "Redis PING OK"
}
finally {
  $redis.Close()
}

Write-Host ""
Write-Host "Checking MinIO health..."
Invoke-RestMethod -Uri "http://127.0.0.1:9000/minio/health/live" -TimeoutSec 10 | Out-Null
Write-Host "MinIO health OK"

Write-Host ""
Write-Host "Checking frontend typecheck and build..."
Push-Location (Join-Path $projectRoot "frontend")
try {
  npm exec tsc -- --noEmit
  npm exec vite -- build --outDir ../tmp/frontend-build-check --emptyOutDir false
}
finally {
  Pop-Location
}

Write-Host ""
Write-Host "Checking browser extension build..."
Push-Location (Join-Path $projectRoot "browser-extension")
try {
  npm run build
}
finally {
  Pop-Location
}

Write-Host ""
Write-Host "M0 local checks finished."
