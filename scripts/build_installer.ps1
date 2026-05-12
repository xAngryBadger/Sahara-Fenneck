param(
    [switch]$SkipInno,
    [switch]$SkipPip,
    [switch]$InnoOnly
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot | Split-Path
Set-Location $root

if (-not (Test-Path "main.py")) {
    Write-Error "main.py nao encontrado em $root. Execute a partir da raiz do projeto."
    exit 1
}
if (-not (Test-Path "assets\fennec_head_icon.ico")) {
    Write-Warning "assets\fennec_head_icon.ico nao encontrado. Build prosseguira sem icone customizado."
}
if (-not (Test-Path "requirements-slim.txt") -and -not (Test-Path "requirements.txt")) {
    Write-Warning "Nenhum requirements.txt encontrado. PyInstaller pode falhar com deps ausentes."
}

# Só recompila os instaladores (Legacy só se dist existir; Slim sempre)
if ($InnoOnly) {
    $isccCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        Write-Error "Inno Setup (ISCC.exe) não encontrado. Instale o Inno Setup 6."
        exit 1
    }
if (Test-Path "dist\FennecExcel\FennecExcel.exe") {
    & $iscc "installer\FennecExcel.iss"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ISCC (Legacy) falhou (exit $LASTEXITCODE)"
        exit 1
    }
    Write-Host "Legacy: build\installer\SaharaFennec-Setup-Legacy.exe"
} else {
    Write-Host "Pulando Legacy (dist\FennecExcel nao encontrado)."
}
& $iscc "installer\FennecExcel-Slim.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Error "ISCC (Slim) falhou (exit $LASTEXITCODE)"
    exit 1
}
Write-Host "Slim (divulgacao): build\installer\SaharaFennec-Setup.exe"
    exit 0
}

if (-not $SkipPip) {
    python -m pip install --upgrade pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pip install pyinstaller falhou (exit $LASTEXITCODE)"
        exit 1
    }
}

# Gera assets do installer (BMP)
if (Test-Path "assets\installer_fennec.png") {
    python "scripts\make_installer_assets.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "make_installer_assets.py falhou. Prosseguindo sem BMPs customizados."
    }
} else {
    Write-Warning "assets\installer_fennec.png nao encontrado. Pulando geracao de BMPs do installer."
}

# Build app standalone
$pyInstallerArgs = @(
    "--noconfirm", "--clean", "--windowed",
    "--name", "FennecExcel",
    "--add-data", "assets;assets",
    "main.py"
)
if (Test-Path "assets\fennec_head_icon.ico") {
    $pyInstallerArgs = @("--icon", "assets\fennec_head_icon.ico") + $pyInstallerArgs
}
python -m PyInstaller @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller falhou (exit $LASTEXITCODE)"
    exit 1
}
if (-not (Test-Path "dist\FennecExcel\FennecExcel.exe")) {
    Write-Error "dist\FennecExcel\FennecExcel.exe nao encontrado apos build."
    exit 1
}

if ($SkipInno) {
    Write-Host "Build PyInstaller concluído. Inno Setup pulado por parâmetro."
    exit 0
}

# Compila instalador Inno Setup (se disponível)
$isccCandidatesFull = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidatesFull | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Warning "Inno Setup (ISCC.exe) não encontrado. Instale o Inno Setup 6 para gerar o .exe do instalador."
    exit 0
}

if (Test-Path "dist\FennecExcel\FennecExcel.exe") {
    & $iscc "installer\FennecExcel.iss"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ISCC (Legacy) falhou (exit $LASTEXITCODE)"
        exit 1
    }
    Write-Host "Legacy: build\installer\SaharaFennec-Setup-Legacy.exe"
}
& $iscc "installer\FennecExcel-Slim.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Error "ISCC (Slim) falhou (exit $LASTEXITCODE)"
    exit 1
}
Write-Host "Slim: build\installer\SaharaFennec-Setup.exe (use este para divulgar)"
