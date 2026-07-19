# Setup UI design tools for pgadmin-system
# Usage: .\scripts\setup-ui-tools.ps1
#        .\scripts\setup-ui-tools.ps1 -ApiKey "your-key"

param(
  [string]$ApiKey
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== PG Control Center — UI tools setup ===" -ForegroundColor Cyan

# 1. UI UX Pro Max (skill)
Write-Host "`n[1/3] UI UX Pro Max skill..." -ForegroundColor Yellow
npx -y uipro-cli init --ai cursor
Write-Host "OK: .cursor/skills/ui-ux-pro-max/" -ForegroundColor Green

# 2. Design system
Write-Host "`n[2/3] Design system..." -ForegroundColor Yellow
python .cursor/skills/ui-ux-pro-max/scripts/search.py `
  "database admin dashboard PostgreSQL monitoring B2B SaaS real-time" `
  --design-system --persist -p "PG Control Center" --stack vue
Write-Host "OK: design-system/pg-control-center/" -ForegroundColor Green

# 3. Magic MCP (21st.dev)
Write-Host "`n[3/3] Magic MCP (21st.dev)..." -ForegroundColor Yellow
if (-not $ApiKey) {
  Write-Host "Получите ключ: https://21st.dev/magic/console" -ForegroundColor Gray
  $ApiKey = Read-Host "Введите Magic API key (или Enter — пропустить)"
}

if ($ApiKey) {
  [Environment]::SetEnvironmentVariable("TWENTYFIRST_MAGIC_API_KEY", $ApiKey, "User")
  $env:TWENTYFIRST_MAGIC_API_KEY = $ApiKey
  npx -y @21st-dev/cli@latest install cursor --api-key $ApiKey
  Write-Host "OK: Magic MCP + env TWENTYFIRST_MAGIC_API_KEY (User)" -ForegroundColor Green
} else {
  Write-Host "SKIP: задайте ключ позже и запустите:" -ForegroundColor Yellow
  Write-Host '  $env:TWENTYFIRST_MAGIC_API_KEY = "your-key"' -ForegroundColor Gray
  Write-Host "  npx @21st-dev/cli@latest install cursor --api-key `$env:TWENTYFIRST_MAGIC_API_KEY" -ForegroundColor Gray
}

Write-Host "`nГотово. Перезапустите Cursor." -ForegroundColor Cyan
Write-Host "В чате: «улучши Dashboard» или /ui modern stats cards for PostgreSQL monitoring" -ForegroundColor Gray
