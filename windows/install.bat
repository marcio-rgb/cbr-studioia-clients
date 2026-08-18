@echo off
TITLE Instalador Omni Playwright Client (Windows)
CLS
echo ========================================================
echo   Instalador Omni Playwright Client (Windows)
echo   Conexao de Saida: ws://ia.creditobr.com.br:8384
echo ========================================================
echo.

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

echo [2/4] Instalando dependencias (playwright, websockets)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install playwright websockets

echo [3/4] Instalando navegadores do Playwright (Chromium)...
playwright install chromium

echo [4/4] Criando atalho de inicializacao (start_client.bat)...
(
echo @echo off
echo TITLE Omni Playwright Remote Client
echo echo Conectando ao Servidor VPS: ws://ia.creditobr.com.br:8384 ...
echo call .venv\Scripts\activate.bat
echo python remote_playwright_client.py --url ws://ia.creditobr.com.br:8384
echo pause
) > start_client.bat

echo.
echo ========================================================
echo   Instalacao concluida com sucesso!
echo   Execute 'start_client.bat' para conectar a VPS.
echo ========================================================
pause
