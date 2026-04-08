param(
    [bool]$WriteConfig = $true,
    [string]$ModelsToPull = "",
    [bool]$EnsureOllamaInstall = $true,
    [bool]$StartOllamaIfNeeded = $true,
    [bool]$PullRecommendedIfEmpty = $true,
    [int]$PullTimeoutSec = 3600,
    [bool]$DeferModelPull = $true,
    [string]$StatusFile = ""
)

$ErrorActionPreference = "Continue"
$CONFIG_DIR = Join-Path $env:APPDATA "SaharaFennec"
$LOG_PATH = Join-Path $CONFIG_DIR "bootstrap.log"
$ANSI = [System.Text.Encoding]::GetEncoding(28591)

Add-Type -AssemblyName System.Windows.Forms | Out-Null

function Write-Log {
    param([string]$Message)
    try {
        if (-not (Test-Path $CONFIG_DIR)) {
            New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
        }
        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $LOG_PATH -Value "[$ts] [postinstall] $Message" -Encoding UTF8
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

function Show-ManualHelp {
    param(
        [string]$Title,
        [string]$Message
    )

    try {
        [System.Windows.Forms.MessageBox]::Show(
            $Message,
            $Title,
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning
        ) | Out-Null
    }
    catch {
        Write-Log "Nao foi possivel exibir popup de ajuda: $($_.Exception.Message)"
    }
}

function Get-RamGb {
    try {
        $m = Get-CimInstance Win32_ComputerSystem
        return [math]::Round($m.TotalPhysicalMemory / 1GB, 1)
    }
    catch {
        return 0
    }
}

function Get-LogicalCpuCount {
    try {
        $cpus = Get-CimInstance Win32_Processor
        $count = ($cpus | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
        if ($count -gt 0) { return [int]$count }
    }
    catch {}
    return 0
}

function Get-VramGb {
    try {
        $out = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $vals = $out | ForEach-Object {
                $n = 0
                if ([int]::TryParse($_.Trim(), [ref]$n)) { $n / 1024.0 }
            }
            if ($vals) {
                return [math]::Round(($vals | Measure-Object -Maximum).Maximum, 1)
            }
        }
    }
    catch {}

    try {
        $max = (
            Get-CimInstance Win32_VideoController |
            Where-Object {
                $_.AdapterRAM -gt 0 -and
                $_.Name -notmatch 'Intel' -and
                ($_.VideoProcessor -eq $null -or $_.VideoProcessor -notmatch 'Intel')
            } |
            Measure-Object -Property AdapterRAM -Maximum
        ).Maximum
        if ($max -gt 0) {
            return [math]::Round($max / 1GB, 1)
        }
    }
    catch {}

    return 0
}

function Get-Recommendation {
    param(
        [double]$RamGb,
        [double]$VramGb,
        [int]$CpuThreads
    )

    $availableRam = [math]::Round($RamGb * 0.60, 1)

    if ($VramGb -ge 10) {
        return @{ Model = "qwen2.5:14b"; Profile = "top"; Reason = "GPU dedicada forte" }
    }
    if ($VramGb -ge 6) {
        return @{ Model = "qwen2.5:7b"; Profile = "medium"; Reason = "GPU dedicada intermediaria" }
    }
    if ($availableRam -ge 22 -and $CpuThreads -ge 16) {
        return @{ Model = "qwen2.5:14b"; Profile = "top"; Reason = "CPU high-end com RAM suficiente" }
    }
    if ($availableRam -ge 8 -and $CpuThreads -ge 8) {
        return @{ Model = "qwen2.5:7b"; Profile = "medium"; Reason = "melhor equilibrio para uso empresarial" }
    }
    return @{ Model = "qwen2.5:3b"; Profile = "low"; Reason = "hardware mais limitado" }
}

function Resolve-ConfiguredModel {
    param(
        [string]$RecommendedModel,
        [string[]]$RequestedModels
    )

    if (-not $RequestedModels -or $RequestedModels.Count -eq 0) {
        return $RecommendedModel
    }
    if ($RequestedModels -contains $RecommendedModel) {
        return $RecommendedModel
    }
    return $RequestedModels[0]
}

function Find-Ollama {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
        (Join-Path $env:ProgramFiles "Ollama\ollama.exe")
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
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

function Install-Ollama {
    Set-Status "Baixando instalador do Ollama..."
    $tmp = Join-Path $env:TEMP "SaharaFennec"
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $installer = Join-Path $tmp "OllamaSetup.exe"
    $urls = @(
        "https://ollama.com/download/OllamaSetup.exe",
        "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"
    )

    $downloadOk = Invoke-DownloadWithRetry -Urls $urls -OutFile $installer -MaxAttempts 4 -RetryDelaySec 8
    if (-not $downloadOk) {
        Write-Log "Nao foi possivel baixar o Ollama apos todas as tentativas."
        Show-ManualHelp -Title "Sahara Fennec - Ollama" -Message (
            "Nao foi possivel baixar o Ollama automaticamente.`n`n" +
            "Baixe manualmente em: https://ollama.com/download/windows`n`n" +
            "Depois reabra o Fennec.`n`nLog: $LOG_PATH"
        )
        return $null
    }

    Set-Status "Instalando Ollama..."
    $p = Start-Process -FilePath $installer -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-' -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        $p = Start-Process -FilePath $installer -ArgumentList '/S' -Wait -PassThru
    }
    if ($p.ExitCode -ne 0) {
        Write-Log "Instalador do Ollama falhou com exit code $($p.ExitCode)"
        Show-ManualHelp -Title "Sahara Fennec - Ollama" -Message (
            "O instalador do Ollama falhou automaticamente.`n`n" +
            "Instale manualmente em: https://ollama.com/download/windows`n`n" +
            "Depois reabra o Fennec.`n`nLog: $LOG_PATH"
        )
        return $null
    }

    Start-Sleep -Seconds 3
    return (Find-Ollama)
}

function Wait-OllamaReady {
    param([int]$TimeoutSec = 25)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -Method GET -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { return $true }
        }
        catch {}
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Start-OllamaServer {
    param([string]$OllamaExe)
    if (Wait-OllamaReady -TimeoutSec 3) { return $true }
    if (-not $StartOllamaIfNeeded) { return $false }

    try {
        Set-Status "Iniciando servico Ollama em segundo plano..."
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $OllamaExe
        $psi.Arguments = "serve"
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        [System.Diagnostics.Process]::Start($psi) | Out-Null
        return (Wait-OllamaReady -TimeoutSec 30)
    }
    catch {
        Write-Log "Falha ao iniciar Ollama: $($_.Exception.Message)"
        return $false
    }
}

function Test-ModelInstalled {
    param([string]$OllamaExe, [string]$Model)
    try {
        $listOut = & $OllamaExe list 2>$null | Out-String
        return ($listOut -match [regex]::Escape($Model))
    }
    catch {
        return $false
    }
}

function Pull-ModelWithRetry {
    param([string]$OllamaExe, [string]$Model, [int]$TimeoutSec, [int]$MaxAttempts = 3)
    $attempt = 0
    while ($attempt -lt $MaxAttempts) {
        $attempt++
        Set-Status "Baixando modelo $Model (tentativa $attempt/$MaxAttempts)..."
        try {
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $OllamaExe
            $psi.Arguments = "pull $Model"
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            $proc = [System.Diagnostics.Process]::Start($psi)
            $ok = $proc.WaitForExit($TimeoutSec * 1000)
            if (-not $ok) {
                try { $proc.Kill() } catch {}
                Write-Log "Modelo ${Model}: timeout na tentativa $attempt"
            }
            elseif ($proc.ExitCode -eq 0) {
                return $true
            }
            else {
                Write-Log "Modelo ${Model}: exit code $($proc.ExitCode) na tentativa $attempt"
            }
        }
        catch {
            Write-Log "Modelo ${Model}: excecao na tentativa ${attempt}: $($_.Exception.Message)"
        }

        if ($attempt -lt $MaxAttempts) {
            $wait = 10 * $attempt
            Set-Status "Aguardando ${wait}s antes de nova tentativa do modelo..."
            Start-Sleep -Seconds $wait
        }
    }
    return $false
}

function Register-DeferredModelPull {
    param([string]$OllamaExe, [string[]]$Models)

    $pendingFile = Join-Path $CONFIG_DIR "pending_models.txt"
    $Models | Set-Content -Path $pendingFile -Encoding UTF8

    $pullScript = @"
param([string]`$OllamaExe, [string]`$PendingFile, [string]`$LogPath)
Start-Sleep -Seconds 20
function wl([string]`$m) {
    try { Add-Content -Path `$LogPath -Value "[`$(Get-Date -f 'yyyy-MM-dd HH:mm:ss')] [bgpull] `$m" -Encoding UTF8 } catch {}
}
if (-not (Test-Path `$PendingFile)) { exit 0 }
`$models = Get-Content `$PendingFile
try {
    `$deadline = (Get-Date).AddSeconds(7200)
    foreach (`$m in `$models) {
        `$m = `$m.Trim()
        if (-not `$m) { continue }
        wl "Starting pull: `$m"
        for (`$i = 1; `$i -le 3; `$i++) {
            `$psi = New-Object System.Diagnostics.ProcessStartInfo
            `$psi.FileName = `$OllamaExe
            `$psi.Arguments = "pull `$m"
            `$psi.UseShellExecute = `$false
            `$psi.CreateNoWindow = `$true
            `$proc = [System.Diagnostics.Process]::Start(`$psi)
            `$remaining = [int]((`$deadline - (Get-Date)).TotalMilliseconds)
            if (`$remaining -le 0) {
                try { `$proc.Kill() } catch {}
                wl "Global timeout"
                exit 0
            }
            `$ok = `$proc.WaitForExit([Math]::Min(`$remaining, 3600000))
            if (-not `$ok) {
                try { `$proc.Kill() } catch {}
                wl "Timeout on attempt `$i for `$m"
            }
            elseif (`$proc.ExitCode -eq 0) {
                wl "Pull OK: `$m"
                break
            }
            else {
                wl "Exit `$(`$proc.ExitCode) attempt `$i for `$m"
            }
            if (`$i -lt 3) { Start-Sleep -Seconds (15 * `$i) }
        }
    }
    Remove-Item `$PendingFile -Force -ErrorAction SilentlyContinue
    wl "Background pull completed"
}
catch {
    wl "Error: `$_"
}
"@

    $pullScriptPath = Join-Path $CONFIG_DIR "bg_pull.ps1"
    [IO.File]::WriteAllText($pullScriptPath, $pullScript, [System.Text.Encoding]::UTF8)

    $taskName = "SaharaFennec_ModelPull"
    try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}

    $psExe = "powershell.exe"
    $args = "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$pullScriptPath`" -OllamaExe `"$OllamaExe`" -PendingFile `"$pendingFile`" -LogPath `"$LOG_PATH`""
    $action = New-ScheduledTaskAction -Execute $psExe -Argument $args
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable -DontStopIfGoingOnBatteries -RunOnlyIfNetworkAvailable
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited -Force | Out-Null
    Start-Process $psExe -ArgumentList $args -WindowStyle Hidden

    Write-Log "Modelos agendados para download em background: $($Models -join ', ')"
}

function Write-FennecConfig {
    param(
        [string]$Model,
        [bool]$IndexAllSheets = $false,
        [int]$MaxRows = 0
    )

    $cfg = @{
        model = $Model
        index_all_sheets = $IndexAllSheets
        max_rows_per_sheet = $MaxRows
    }

    $settingsPath = Join-Path $CONFIG_DIR "settings.json"
    New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
    ($cfg | ConvertTo-Json -Depth 5) | Set-Content -Path $settingsPath -Encoding UTF8
    Write-Log "settings.json salvo em $settingsPath com modelo $Model"
}

$ram = Get-RamGb
$vram = Get-VramGb
$cpuThreads = Get-LogicalCpuCount
$rec = Get-Recommendation -RamGb $ram -VramGb $vram -CpuThreads $cpuThreads

$requestedModels = @()
if ($ModelsToPull -match '\S') {
    $requestedModels = $ModelsToPull -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

$configuredModel = Resolve-ConfiguredModel -RecommendedModel $rec.Model -RequestedModels $requestedModels

Set-Status "Hardware detectado: ${ram}GB RAM, ${vram}GB VRAM, ${cpuThreads} threads. Perfil: $($rec.Profile)"
Write-Log "Modelo recomendado: $($rec.Model) | motivo: $($rec.Reason) | modelo configurado: $configuredModel"

$ollamaExe = Find-Ollama
if (-not $ollamaExe -and $EnsureOllamaInstall) {
    $ollamaExe = Install-Ollama
}

if ($WriteConfig) {
    Write-FennecConfig -Model $configuredModel -IndexAllSheets:$false -MaxRows 0
}

if (-not $ollamaExe) {
    Write-Log "Ollama nao disponivel. Pull de modelo sera adiado para o primeiro uso."
    Set-Status "Ollama nao esta instalado. O Fennec concluira a configuracao quando for aberto."
    return
}

$ready = Start-OllamaServer -OllamaExe $ollamaExe
if (-not $ready) {
    Write-Log "Ollama nao respondeu na porta 11434"
    Set-Status "Ollama nao respondeu. O download do modelo ficara pendente para o primeiro uso."
    return
}

$models = @()
if ($requestedModels.Count -gt 0) {
    $models = $requestedModels
}
elseif ($PullRecommendedIfEmpty) {
    $models = @($configuredModel)
}

if ($models.Count -gt 0) {
    if ($DeferModelPull) {
        $notInstalled = $models | Where-Object { -not (Test-ModelInstalled -OllamaExe $ollamaExe -Model $_) }
        if ($notInstalled.Count -gt 0) {
            Register-DeferredModelPull -OllamaExe $ollamaExe -Models $notInstalled
            Set-Status "Modelos serao baixados em segundo plano apos a instalacao: $($notInstalled -join ', ')"
        }
        else {
            Set-Status "Todos os modelos ja estao instalados."
        }
    }
    else {
        $total = $models.Count
        $idx = 0
        foreach ($m in $models) {
            $idx++
            if (Test-ModelInstalled -OllamaExe $ollamaExe -Model $m) {
                Set-Status "[$idx/$total] Modelo ja instalado: $m"
                continue
            }

            $ok = Pull-ModelWithRetry -OllamaExe $ollamaExe -Model $m -TimeoutSec $PullTimeoutSec -MaxAttempts 3
            if ($ok) {
                Set-Status "[$idx/$total] Modelo baixado: $m"
            }
            else {
                Write-Log "Falha ao baixar modelo $m apos todas as tentativas. O download podera ser retomado depois."
                Set-Status "[$idx/$total] Modelo $m ficara pendente para o primeiro uso do app."
                $manualCmd = "ollama pull $m"
                Show-ManualHelp -Title "Sahara Fennec - Acao necessaria" -Message (
                    "Nao foi possivel baixar o modelo '$m' automaticamente apos 3 tentativas.`n`n" +
                    "Para instalar manualmente quando tiver conexao estavel:`n`n" +
                    "  1. Abra o Prompt de Comando (cmd) como Administrador`n" +
                    "  2. Execute: $manualCmd`n`n" +
                    "O Fennec funcionara assim que o modelo estiver disponivel.`n`nLog: $LOG_PATH"
                )
            }
        }
    }
}

Set-Status "Configuracao de IA concluida."
