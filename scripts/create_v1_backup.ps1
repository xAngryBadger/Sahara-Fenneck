param(
    [string]$Root = ($PSScriptRoot | Split-Path)
)

$ErrorActionPreference = "Stop"
Set-Location $Root

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = Join-Path $Root "releases\v1.0-backup-$stamp"
$artifacts = Join-Path $backup "artifacts"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
New-Item -ItemType Directory -Path $artifacts -Force | Out-Null

Write-Host "Criando backup v1.0 em: $backup"

# Codigo e configuracao para rebuild da v1
Copy-Item "main.py" $backup -Force
Copy-Item "README.md" $backup -Force
Copy-Item "requirements.txt" $backup -Force -ErrorAction SilentlyContinue
Copy-Item "requirements-slim.txt" $backup -Force -ErrorAction SilentlyContinue
Copy-Item "src" $backup -Recurse -Force
Copy-Item "installer" $backup -Recurse -Force
Copy-Item "scripts" $backup -Recurse -Force
Copy-Item "docs" $backup -Recurse -Force -ErrorAction SilentlyContinue

# Artefatos de release, se existirem
$legacy = "build\installer\SaharaFennec-Setup-Legacy.exe"
$slim = "build\installer\SaharaFennec-Setup.exe"
if (Test-Path $legacy) { Copy-Item $legacy $artifacts -Force }
if (Test-Path $slim) { Copy-Item $slim $artifacts -Force }

Write-Host "Backup v1.0 concluido."
Write-Host "Pasta: $backup"

