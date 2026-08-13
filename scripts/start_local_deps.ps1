Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $projectRoot "infra\docker-compose.yml"

Write-Host "Starting local dependencies with Docker Compose..."
docker compose -f $composeFile up -d

Write-Host ""
Write-Host "Current dependency containers:"
docker compose -f $composeFile ps

Write-Host ""
Write-Host "Expected ports:"
Write-Host "- PostgreSQL: localhost:5432"
Write-Host "- Redis:      localhost:6379"
Write-Host "- MinIO API:  localhost:9000"
Write-Host "- MinIO UI:   http://localhost:9001"

