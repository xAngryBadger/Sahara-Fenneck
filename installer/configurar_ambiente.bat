@echo off
:: Execute se o app nao abrir (ambiente nao configurado).
cd /d "%~dp0"
set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"
echo Configurando ambiente Python...
powershell -ExecutionPolicy Bypass -File "%APP_DIR%\bootstrap\setup_slim.ps1" -AppDir "%APP_DIR%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo Falhou. Instale Python manualmente: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Concluido. Pode abrir o Sahara Fennec agora.
pause
