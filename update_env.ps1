# Скрипт для обновления .env файла с кредами для Docker Compose
# Запустите: .\update_env.ps1

$envFile = ".env"
$backupFile = ".env.backup"

# Проверяем, существует ли .env
if (Test-Path $envFile) {
    # Создаем резервную копию
    Copy-Item $envFile $backupFile
    Write-Host "Создана резервная копия: $backupFile" -ForegroundColor Green
} else {
    Write-Host "Файл .env не найден, создаем новый..." -ForegroundColor Yellow
}

# Генерируем безопасные пароли
$postgresPassword = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 20 | % {[char]$_})
$redisPassword = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 20 | % {[char]$_})

# Читаем текущий .env или создаем новый
$envContent = if (Test-Path $envFile) { Get-Content $envFile } else { @() }

# Создаем новый контент
$newContent = @()

# Добавляем переменные для Docker Compose
$newContent += "# Docker Compose Credentials"
$newContent += "POSTGRES_USER=serm_user"
$newContent += "POSTGRES_PASSWORD=$postgresPassword"
$newContent += "POSTGRES_DB=serm"
$newContent += "REDIS_PASSWORD=$redisPassword"
$newContent += ""

# Добавляем переменные для локального FastAPI (совпадают с docker-compose)
$newContent += "# Local FastAPI Credentials (matches docker-compose)"
$newContent += "DATABASE_URL=postgresql+asyncpg://serm_user:$postgresPassword@localhost:5432/serm"
$newContent += "REDIS_URL=redis://localhost:6379/0"
$newContent += ""

# Копируем остальные переменные из существующего .env, если они есть
$existingKeys = @("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "REDIS_PASSWORD", "DATABASE_URL", "REDIS_URL")

foreach ($line in $envContent) {
    if ($line -match "^([^=]+)=(.*)$") {
        $key = $matches[1]
        if ($key -notin $existingKeys) {
            $newContent += $line
        }
    } elseif ($line -notmatch "^#" -and $line.Trim() -ne "") {
        $newContent += $line
    }
}

# Записываем новый .env
$newContent | Out-File -FilePath $envFile -Encoding UTF8

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ".env файл успешно обновлен!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Добавленные переменные:" -ForegroundColor Yellow
Write-Host "  POSTGRES_USER=serm_user" -ForegroundColor White
Write-Host "  POSTGRES_PASSWORD=$postgresPassword" -ForegroundColor White
Write-Host "  POSTGRES_DB=serm" -ForegroundColor White
Write-Host "  REDIS_PASSWORD=$redisPassword" -ForegroundColor White
Write-Host ""
Write-Host "Обновленные переменные для FastAPI:" -ForegroundColor Yellow
Write-Host "  DATABASE_URL=postgresql+asyncpg://serm_user:$postgresPassword@localhost:5432/serm" -ForegroundColor White
Write-Host "  REDIS_URL=redis://localhost:6379/0" -ForegroundColor White
Write-Host ""
Write-Host "Резервная копия сохранена в: $backupFile" -ForegroundColor Gray
Write-Host ""
Write-Host "Теперь можно запустить:" -ForegroundColor Green
Write-Host "  docker-compose up -d postgres redis" -ForegroundColor Cyan
Write-Host ""
