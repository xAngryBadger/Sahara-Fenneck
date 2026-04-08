param(
    [switch]$SkipInno,
    [switch]$SkipPip,
    [switch]$InnoOnly
)

$ErrorActionPreference = "Stop"
$root = "e:\Sahara Fenneck"
Set-Location $root

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
        Write-Host "Legacy: build\installer\SaharaFennec-Setup-Legacy.exe"
    } else {
        Write-Host "Pulando Legacy (dist\FennecExcel nao encontrado)."
    }
    & $iscc "installer\FennecExcel-Slim.iss"
    Write-Host "Slim (divulgacao): build\installer\SaharaFennec-Setup.exe"
    exit 0
}

if (-not $SkipPip) {
    python -m pip install --upgrade pyinstaller
}

# Gera assets do installer (BMP)
python "scripts\make_installer_assets.py"

# Build app standalone
python -m PyInstaller --noconfirm --clean --windowed `
    --name "FennecExcel" `
    --icon "assets\fennec_head_icon.ico" `
    --add-data "assets;assets" `
    "main.py"

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
    Write-Host "Legacy: build\installer\SaharaFennec-Setup-Legacy.exe"
}
& $iscc "installer\FennecExcel-Slim.iss"
Write-Host "Slim: build\installer\SaharaFennec-Setup.exe (use este para divulgar)"
