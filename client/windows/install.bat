@echo off
TITLE Instalador Omni Playwright Client (Windows)
CLS
echo ========================================================
echo   Instalador Omni Playwright Client (Windows)
echo   Conexao de Saida: wss://ia.creditobr.com.br/ws
echo ========================================================
echo.

if "%PLAYWRIGHT_BROWSERS_PATH%"=="" (
    set "PLAYWRIGHT_BROWSERS_PATH=%LOCALAPPDATA%\ms-playwright"
)

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python3 nao foi encontrado no PATH do sistema.
    echo Por favor, instale o Python 3.10 ou superior antes de continuar:
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Criando ambiente virtual Python (.venv)...
python -m venv .venv

echo [2/4] Instalando dependencias (playwright, websockets, camoufox, requests)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install playwright websockets camoufox requests

echo [3/4] Instalando navegadores (Chromium e Camoufox)...
python -m playwright install chromium
python -m camoufox fetch

echo [4/4] Criando atalho de inicializacao (start_client.bat)...
(
echo @echo off
echo TITLE Omni Playwright Remote Client
echo echo Conectando ao Servidor VPS: wss://ia.creditobr.com.br/ws ...
echo call .venv\Scripts\activate.bat
echo if exist "launcher.py" (
echo     python launcher.py %%*
echo ^) else if exist "..\launcher.py" (
echo     python ..\launcher.py %%*
echo ^) else if exist "remote_client.py" (
echo     python remote_client.py --url wss://ia.creditobr.com.br/ws %%*
echo ^) else (
echo     python ..\remote_client.py --url wss://ia.creditobr.com.br/ws %%*
echo ^)
echo pause
) > start_client.bat

echo.
echo ========================================================
echo   Instalacao concluida com sucesso!
echo   Execute 'start_client.bat' para conectar a VPS.
echo ========================================================
pause

