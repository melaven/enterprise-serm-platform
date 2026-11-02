# Create or refresh local PostgreSQL, tenant-role, and Redis credentials.
# Run from any directory with: .\scripts\update_env.ps1

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$envFile = Join-Path $repoRoot ".env"
$backupFile = Join-Path $repoRoot ".env.backup"
$envContent = @()

if (Test-Path -LiteralPath $envFile) {
    Copy-Item -LiteralPath $envFile -Destination $backupFile -Force
    $envContent = Get-Content -LiteralPath $envFile
    Write-Host "Created a backup at .env.backup" -ForegroundColor Green
} else {
    $templateFile = Join-Path $repoRoot ".env.example"
    if (-not (Test-Path -LiteralPath $templateFile)) {
        throw "Environment template not found: $templateFile"
    }
    $envContent = Get-Content -LiteralPath $templateFile
}

$alphabet = (48..57) + (65..90) + (97..122)
$postgresPassword = -join ($alphabet | Get-Random -Count 32 | ForEach-Object { [char]$_ })
$tenantPassword = -join ($alphabet | Get-Random -Count 32 | ForEach-Object { [char]$_ })
$redisPassword = -join ($alphabet | Get-Random -Count 32 | ForEach-Object { [char]$_ })

$newContent = @(
    "# Local PostgreSQL"
    "POSTGRES_USER=sentiguard"
    "POSTGRES_PASSWORD=$postgresPassword"
    "POSTGRES_DB=sentiguard"
    "APP_TENANT_PASSWORD=$tenantPassword"
    "DATABASE_URL=postgresql+asyncpg://sentiguard:$postgresPassword@db:5432/sentiguard"
    "TENANT_DATABASE_URL=postgresql+asyncpg://app_tenant:$tenantPassword@db:5432/sentiguard"
    "USE_TENANT_ROLE=true"
    ""
    "# Local Redis"
    "REDIS_PASSWORD=$redisPassword"
    "REDIS_URL=redis://127.0.0.1:6379/0"
    ""
)

$generatedKeys = @(
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
    "APP_TENANT_PASSWORD", "DATABASE_URL", "TENANT_DATABASE_URL",
    "USE_TENANT_ROLE", "REDIS_PASSWORD", "REDIS_URL"
)

foreach ($line in $envContent) {
    if ($line -match "^([^=]+)=" -and $matches[1] -notin $generatedKeys) {
        $newContent += $line
    } elseif ($line -match "^\s*#" -or $line.Trim() -eq "") {
        $newContent += $line
    }
}

$newContent | Set-Content -LiteralPath $envFile -Encoding UTF8
Write-Host "Updated .env with unique PostgreSQL, tenant-role, and Redis passwords." -ForegroundColor Green
Write-Host "Generated passwords were not printed. Start the stack with: docker compose up --build"
