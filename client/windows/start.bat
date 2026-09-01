@echo off
TITLE Omni Playwright Client (Windows)
CLS
echo ========================================================
echo   Omni Playwright Remote Client (Windows Auto-Launcher)
echo   Conexao de Saida: wss://ia.creditobr.com.br/ws
echo ========================================================
echo.

cd /d "%~dp0"

if "%PLAYWRIGHT_BROWSERS_PATH%"=="" (
    set "PLAYWRIGHT_BROWSERS_PATH=%LOCALAPPDATA%\ms-playwright"
)

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Python 3 nao foi encontrado no PATH do sistema.
    echo Por favor, instale o Python 3.10+ marcando 'Add python.exe to PATH':
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/3] Criando ambiente virtual Python (.venv)...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [2/3] Instalando dependencias Python...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

set "VPS_URL=wss://ia.creditobr.com.br/ws"
set "ARG1=%~1"
if not "%ARG1%"=="" (
    if not "%ARG1:~0,2%"=="--" (
        set "VPS_URL=%ARG1%"
        shift
    )
)

echo [3/3] Verificando navegadores (Chromium e Camoufox)...
python -m playwright install chromium
python -m camoufox fetch

echo.
echo ========================================================
echo   Iniciando CBR Estúdio IA Launcher...
echo ========================================================
echo.

if exist "launcher.py" (
    python launcher.py %*
) else if exist "..\launcher.py" (
    python ..\launcher.py %*
) else (
    python remote_client.py --url "%VPS_URL%" %*
)

pause
