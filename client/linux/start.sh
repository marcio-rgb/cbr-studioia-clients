#!/usr/bin/env bash
set -e
export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

VPS_URL="wss://ia.creditobr.com.br/ws"
if [[ "$1" == ws://* || "$1" == wss://* ]]; then
    VPS_URL="$1"
    shift
fi

echo -e "${BLUE}========================================================${NC}"
echo -e "${BLUE}  Omni Playwright Remote Client (Linux Auto-Installer)${NC}"
echo -e "${BLUE}  URL de Conexão: ${VPS_URL}${NC}"
echo -e "${BLUE}========================================================${NC}"
echo ""

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}[!] Python 3 não foi encontrado. Instalando pacotes...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3 python3-pip
    elif command -v pacman &> /dev/null; then
        sudo pacman -Sy --noconfirm python python-pip
    fi
fi

if [ -d ".venv" ]; then
    if ! .venv/bin/python3 -c "import sys" &>/dev/null; then
        echo -e "${YELLOW}[!] Ambiente .venv invalido ou movido de pasta. Recriando .venv...${NC}"
        rm -rf .venv
    fi
fi

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[!] Criando ambiente virtual Python (.venv)...${NC}"
    python3 -m venv .venv || {
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
        fi
        python3 -m venv .venv
    }
    echo -e "${GREEN}[✔] Ambiente .venv criado com sucesso!${NC}"
fi

REQ_FILE="requirements.txt"
if [ ! -f "$REQ_FILE" ] && [ -f "../../requirements.txt" ]; then
    REQ_FILE="../../requirements.txt"
fi

echo -e "${BLUE}[1/3] Verificando dependências Python no .venv...${NC}"
.venv/bin/python3 -m pip install --upgrade pip --quiet
.venv/bin/python3 -m pip install -r "$REQ_FILE" --quiet
echo -e "${GREEN}[✔] Dependências Python prontas!${NC}"

echo -e "${BLUE}[2/3] Verificando navegadores (Chromium e Camoufox)...${NC}"
.venv/bin/playwright install chromium || echo -e "${YELLOW}[!] Aviso ao instalar Chromium. Continuando com Camoufox...${NC}"
.venv/bin/python3 -m camoufox fetch || true

if command -v sudo &> /dev/null; then
    echo -e "${YELLOW}[!] Instalando/verificando dependências nativas do Linux (sudo)...${NC}"
    sudo .venv/bin/playwright install-deps chromium || echo -e "${YELLOW}[!] Aviso: 'install-deps' via sudo não foi executado. Continuando...${NC}"
fi
echo -e "${GREEN}[✔] Chromium e bibliotecas nativas de sistema verificadas!${NC}"

echo -e "${GREEN}[3/3] Conectando cliente Playwright a ${VPS_URL}...${NC}"
echo ""

CLIENT_SCRIPT="remote_client.py"
if [ ! -f "$CLIENT_SCRIPT" ] && [ -f "../remote_client.py" ]; then
    CLIENT_SCRIPT="../remote_client.py"
fi

LAUNCHER_SCRIPT="launcher.py"
if [ ! -f "$LAUNCHER_SCRIPT" ] && [ -f "../launcher.py" ]; then
    LAUNCHER_SCRIPT="../launcher.py"
fi

if [ -f "$LAUNCHER_SCRIPT" ]; then
    exec .venv/bin/python3 "$LAUNCHER_SCRIPT" "$@"
else
    exec .venv/bin/python3 "$CLIENT_SCRIPT" --url "$VPS_URL" "$@"
fi
