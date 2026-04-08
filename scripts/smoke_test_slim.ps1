# Smoke test do instalador magro (Slim)
# Simula o que o instalador copia + setup_slim (venv + pip) e verifica se o app carrega.
# Uso: .\scripts\smoke_test_slim.ps1
# Requer: Python no PATH (py -3 ou python).

$ErrorActionPreference = "Stop"
$root = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $root

Write-Host "=== Smoke test: Instalador Magro (Slim) ===" -ForegroundColor Cyan

# 1) Arquivos que o Inno empacota
$required = @(
    "main.py",
    "requirements-slim.txt",
    "installer\run_fennec.bat",
    "installer\bootstrap\postinstall.ps1",
    "installer\bootstrap\setup_slim.ps1"
)
$requiredDirs = @("src", "assets")
foreach ($f in $required) {
    if (-not (Test-Path $f)) {
        Write-Error "Arquivo ausente (o Slim precisa dele): $f"
        exit 1
    }
    Write-Host "  OK $f"
}
foreach ($d in $requiredDirs) {
    if (-not (Test-Path $d -PathType Container)) {
        Write-Error "Pasta ausente: $d"
        exit 1
    }
    Write-Host "  OK $d\"
}

# 2) Python disponível
$py = $null
try {
    $v = & py -3 --version 2>&1
    if ($LASTEXITCODE -eq 0) { $py = "py -3" }
} catch {}
if (-not $py) {
    try {
        $v = & python --version 2>&1
        if ($LASTEXITCODE -eq 0) { $py = "python" }
    } catch {}
}
if (-not $py) {
    Write-Error "Python nao encontrado (py -3 ou python). Instale Python para rodar o smoke test."
    exit 1
}
Write-Host "  OK Python: $py"

# 3) Temp dir = cópia do que o instalador entrega
$tempDir = Join-Path $env:TEMP "SaharaFennec_SlimSmoke_$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
try {
    Copy-Item "main.py" $tempDir
    Copy-Item "requirements-slim.txt" $tempDir
    Copy-Item "src" $tempDir -Recurse -Force
    Copy-Item "assets" $tempDir -Recurse -Force
    New-Item -ItemType Directory (Join-Path $tempDir "bootstrap") -Force | Out-Null
    Copy-Item "installer\bootstrap\postinstall.ps1" (Join-Path $tempDir "bootstrap")
    Copy-Item "installer\bootstrap\setup_slim.ps1" (Join-Path $tempDir "bootstrap")
    Write-Host "  OK Copia em $tempDir"

    # 4) Rodar setup_slim (venv + pip), sem RunBootstrap
    Push-Location $tempDir
    try {
        & "$root\installer\bootstrap\setup_slim.ps1" -AppDir $tempDir -ModelsToPull "" -RunBootstrap:$false
        if (-not (Test-Path "venv\Scripts\python.exe")) {
            Write-Error "setup_slim.ps1 nao criou venv\Scripts\python.exe"
            exit 1
        }
        Write-Host "  OK venv + pip install"
    } finally {
        Pop-Location
    }

    # 5) App carrega? (main.py --smoke-test)
    $pythonExe = Join-Path $tempDir "venv\Scripts\python.exe"
    Push-Location $tempDir
    try {
        & $pythonExe "main.py" "--smoke-test"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "main.py --smoke-test falhou (exit $LASTEXITCODE)"
            exit 1
        }
    } finally {
        Pop-Location
    }
    Write-Host "  OK main.py --smoke-test (app carrega com deps slim)"
} finally {
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "=== Smoke test Slim: PASSOU ===" -ForegroundColor Green
Write-Host "O instalador magro deve se comportar como esperado."
exit 0
