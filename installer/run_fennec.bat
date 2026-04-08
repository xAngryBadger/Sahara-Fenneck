@echo off
cd /d "%~dp0"

if exist "venv\Scripts\pythonw.exe" goto :run_venv
if exist "%LOCALAPPDATA%\SaharaFennec\Miniconda3\envs\fennec\pythonw.exe" goto :run_conda
set "LAUNCHER_CFG=%APPDATA%\SaharaFennec\launcher_config.txt"
if exist "%LAUNCHER_CFG%" (
    for /f "usebackq delims=" %%a in ("%LAUNCHER_CFG%") do (
        if exist "%%a" (
            start "" "%%a" main.py
            exit /b 0
        )
    )
)

echo Configurando ambiente pela primeira vez (Miniconda + dependencias)...
echo Isso pode demorar 3-5 minutos. Aguarde.
echo.
set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"
powershell -ExecutionPolicy Bypass -File "%APP_DIR%\bootstrap\setup_slim.ps1" -AppDir "%APP_DIR%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo Falha na configuracao. Execute como administrador e tente novamente.
    pause
    exit /b 1
)
echo.
echo Configuracao concluida. Abrindo o app...
timeout /t 2 /nobreak >nul

:run_venv
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" main.py
    exit /b 0
)
:run_conda
if exist "%LOCALAPPDATA%\SaharaFennec\Miniconda3\envs\fennec\pythonw.exe" (
    start "" "%LOCALAPPDATA%\SaharaFennec\Miniconda3\envs\fennec\pythonw.exe" main.py
    exit /b 0
)

echo Ambiente ainda nao encontrado. Execute como administrador.
pause
exit /b 1
