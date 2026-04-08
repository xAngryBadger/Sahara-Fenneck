param(
    [string]$AppDir = "",
    [string]$ModelsToPull = "",
    [switch]$RunBootstrap,
    [string]$StatusFile = "",
    [string]$DoneFile = ""
)

$ErrorActionPreference = "Stop"
$TEMP_DIR = Join-Path $env:TEMP "SaharaFennec"
$MINICONDA_ROOT = Join-Path $env:LOCALAPPDATA "SaharaFennec\Miniconda3"
$CONDA_ENV = "fennec"
$CONFIG_DIR = Join-Path $env:APPDATA "SaharaFennec"
$LAUNCHER_CFG = Join-Path $CONFIG_DIR "launcher_config.txt"
$LOG_PATH = Join-Path $CONFIG_DIR "bootstrap.log"
$ANSI = [System.Text.Encoding]::GetEncoding(28591)

$AppDir = ($AppDir -replace '[\\/]+$', '').Trim()
if (-not $AppDir -or -not (Test-Path $AppDir)) {
    $AppDir = (Get-Item $PSScriptRoot).Parent.FullName
}

$script:InstalledMinicondaNow = $false

function Write-Log {
    param([string]$Message)
    try {
        if (-not (Test-Path $CONFIG_DIR)) {
            New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
        }
        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -LiteralPath $LOG_PATH -Value "[$ts] [setup] $Message" -Encoding UTF8
    }
    catch {}
    Write-Host $Message
}

function Set-Status {
    param([string]$Message)
    Write-Log $Message
    if ($StatusFile) {
        try {
            $dir = Split-Path $StatusFile
            if ($dir -and -not (Test-Path $dir)) {
                New-Item -ItemType Directory -Force -Path $dir | Out-Null
            }
            [IO.File]::WriteAllText($StatusFile, $Message, $ANSI)
        }
        catch {}
    }
}

function Set-Done {
    param([string]$State, [string]$Message)
    Write-Log "DONE => $State | $Message"
    if ($DoneFile) {
        try {
            $dir = Split-Path $DoneFile
            if ($dir -and -not (Test-Path $dir)) {
                New-Item -ItemType Directory -Force -Path $dir | Out-Null
            }
            [IO.File]::WriteAllText($DoneFile, "$State|$Message", $ANSI)
        }
        catch {}
    }
}

function Invoke-DownloadWithRetry {
    param(
        [string[]]$Urls,
        [string]$OutFile,
        [int]$MaxAttempts = 4,
        [int]$RetryDelaySec = 5
    )

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    foreach ($u in $Urls) {
        $attempt = 0
        while ($attempt -lt $MaxAttempts) {
            $attempt++
            try {
                Write-Log "Downloading (attempt $attempt/$MaxAttempts): $u"
                Invoke-WebRequest -Uri $u -OutFile $OutFile -UseBasicParsing -TimeoutSec 180
                if ((Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
                    return $true
                }
            }
            catch {
                Write-Log "Attempt $attempt failed: $($_.Exception.Message)"
                if (Test-Path $OutFile) {
                    Remove-Item -Path $OutFile -Force -ErrorAction SilentlyContinue
                }
            }
            if ($attempt -lt $MaxAttempts) {
                $wait = $RetryDelaySec * $attempt
                Set-Status "Aguardando ${wait}s antes de nova tentativa..."
                Start-Sleep -Seconds $wait
            }
        }
    }
    return $false
}

function Get-CondaExe {
    $p = Join-Path $MINICONDA_ROOT "Scripts\conda.exe"
    if (Test-Path $p) { return $p }
    return $null
}

function Get-CondaPython {
    $p = Join-Path $MINICONDA_ROOT "envs\$CONDA_ENV\python.exe"
    if (Test-Path $p) { return $p }
    return $null
}

function Get-SystemPython {
    foreach ($cmd in @('py', 'python')) {
        try {
            $p = & $cmd -c "import sys; print(sys.executable)" 2>$null
            if ($p -and (Test-Path $p.Trim())) {
                return $p.Trim()
            }
        }
        catch {}
    }

    foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $base) { continue }
        foreach ($ver in @('313', '312', '311', '310')) {
            $p = Join-Path $base "Programs\Python\Python$ver\python.exe"
            if (Test-Path $p) {
                return $p
            }
        }
    }

    return $null
}

function Install-Miniconda {
    Set-Status "Baixando Miniconda..."
    New-Item -ItemType Directory -Force -Path $TEMP_DIR | Out-Null
    $installer = Join-Path $TEMP_DIR "Miniconda3-latest-Windows-x86_64.exe"
    $ok = Invoke-DownloadWithRetry -Urls @("https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe") -OutFile $installer -MaxAttempts 4 -RetryDelaySec 8
    if (-not $ok) {
        throw "Nao foi possivel baixar o Miniconda automaticamente."
    }

    Set-Status "Instalando Miniconda..."
    $installerArgs = @('/S', '/InstallationType=JustMe', '/RegisterPython=0', '/AddToPath=0', "/D=$MINICONDA_ROOT")
    $p = Start-Process -FilePath $installer -ArgumentList $installerArgs -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        throw "Miniconda install failed with exit code $($p.ExitCode)"
    }

    $script:InstalledMinicondaNow = $true
}

function Ensure-CondaEnvironment {
    $pythonExe = Get-CondaPython
    if ($pythonExe) {
        return $pythonExe
    }

    $condaExe = Get-CondaExe
    if (-not $condaExe) {
        Install-Miniconda
        $condaExe = Get-CondaExe
    }

    if (-not $condaExe) {
        throw "conda.exe nao encontrado apos instalacao do Miniconda"
    }

    Set-Status "Criando ambiente Python do Fennec..."
    $env:CONDA_PLUGINS_AUTO_ACCEPT_TOS = "yes"
    & $condaExe create -n $CONDA_ENV python=3.12 -c conda-forge --override-channels -y 2>&1 |
    ForEach-Object { Write-Log "conda: $_" }
    if ($LASTEXITCODE -ne 0) {
        throw "conda create failed ($LASTEXITCODE)"
    }

    $pythonExe = Get-CondaPython
    if (-not $pythonExe) {
        throw "python.exe do ambiente conda nao foi encontrado"
    }
    return $pythonExe
}

function Ensure-VenvFallback {
    $sysPy = Get-SystemPython
    if (-not $sysPy) {
        throw "Python do sistema nao encontrado para fallback."
    }

    $venvPy = Join-Path $AppDir "venv\Scripts\python.exe"
    if (-not (Test-Path $venvPy)) {
        Set-Status "Criando ambiente virtual local..."
        & $sysPy -m venv (Join-Path $AppDir "venv")
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPy)) {
            throw "Falha ao criar ambiente virtual local."
        }
    }

    return $venvPy
}

function Install-PythonDependencies {
    param([string]$PythonExe)

    $req = Join-Path $AppDir "requirements-slim.txt"
    if (-not (Test-Path $req)) {
        Write-Log "requirements-slim.txt nao encontrado; pulando dependencias."
        return
    }

    Set-Status "Instalando dependencias Python..."
    & $PythonExe -m pip install --upgrade pip --quiet 2>&1 | ForEach-Object { Write-Log "pip: $_" }

    $attempt = 0
    while ($attempt -lt 2) {
        $attempt++
        & $PythonExe -m pip install -r $req 2>&1 | ForEach-Object { Write-Log "pip: $_" }
        if ($LASTEXITCODE -eq 0) {
            return
        }
        if ($attempt -lt 2) {
            Set-Status "Falha nas dependencias. Nova tentativa em 10s..."
            Start-Sleep -Seconds 10
        }
    }

    throw "Falha ao instalar dependencias Python."
}

function Write-LauncherConfig {
    param([string]$PythonExe)

    New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
    $pythonw = $null

    if ($PythonExe -like "*Miniconda3*") {
        $candidate = Join-Path $MINICONDA_ROOT "envs\$CONDA_ENV\pythonw.exe"
        if (Test-Path $candidate) { $pythonw = $candidate }
    }
    else {
        $candidate = Join-Path $AppDir "venv\Scripts\pythonw.exe"
        if (Test-Path $candidate) { $pythonw = $candidate }
    }

    if (-not $pythonw) {
        $pythonw = $PythonExe
    }

    [IO.File]::WriteAllText($LAUNCHER_CFG, $pythonw, $ANSI)
    Write-Log "launcher_config salvo em $LAUNCHER_CFG => $pythonw"
}

try {
    Set-Status "Iniciando configuracao automatica..."
    Set-Location -LiteralPath $AppDir

    $pythonExe = $null
    try {
        $pythonExe = Ensure-CondaEnvironment
    }
    catch {
        Write-Log "Conda falhou; tentando fallback para venv. Motivo: $($_.Exception.Message)"
        $pythonExe = Ensure-VenvFallback
    }

    Write-Log "Python final: $pythonExe"
    Install-PythonDependencies -PythonExe $pythonExe
    Write-LauncherConfig -PythonExe $pythonExe

    if ($RunBootstrap) {
        $post = Join-Path $AppDir "bootstrap\postinstall.ps1"
        if (Test-Path $post) {
            Set-Status "Configurando IA local (Ollama)..."
            & $post -WriteConfig $true -ModelsToPull $ModelsToPull -EnsureOllamaInstall $true -StartOllamaIfNeeded $true -PullRecommendedIfEmpty $true -PullTimeoutSec 3600 -DeferModelPull $true -StatusFile $StatusFile
            if ($LASTEXITCODE -ne 0) {
                throw "Falha ao executar postinstall.ps1 ($LASTEXITCODE)"
            }
        }
    }

    if (Test-Path $TEMP_DIR) {
        Remove-Item -Path $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue
    }

    Set-Status "Instalacao concluida com sucesso."
    Set-Done -State "OK" -Message "Instalacao concluida"
}
catch {
    $err = $_.Exception.Message
    Write-Log "FATAL ERROR: $err"
    Write-Log ($_ | Out-String)

    if ($script:InstalledMinicondaNow) {
        Write-Log "Rollback: removendo Miniconda instalado nesta execucao"
        Remove-Item -Path $MINICONDA_ROOT -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path $TEMP_DIR) {
        Remove-Item -Path $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue
    }

    Set-Done -State "ERROR" -Message $err
    exit 1
}
