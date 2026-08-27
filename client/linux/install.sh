#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================================${NC}"
echo -e "${BLUE}   Omni Playwright Remote Client (Linux - All In One)${NC}"
echo -e "${BLUE}   Conexão de Saída: ws://ia.creditobr.com.br:8384${NC}"
echo -e "${BLUE}========================================================${NC}"
echo ""

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"

VPS_URL="${1:-wss://ia.creditobr.com.br/ws}"

# 1. Verificar e instalar python3 se necessário
if ! command -v python3 &> /dev/null; then
    echo -e "${BLUE}[1/4] python3 não foi encontrado no sistema. Instalando...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3 python3-pip
    elif command -v pacman &> /dev/null; then
        sudo pacman -Sy --noconfirm python python-pip
    else
        echo -e "${RED}[ERRO] python3 não foi encontrado e o gerenciador de pacotes não é suportado.${NC}"
        echo -e "Por favor, instale o Python 3 manualmente."
        exit 1
    fi
fi

# 2. Criar ambiente virtual .venv se não existir
if [ ! -d ".venv" ]; then
    echo -e "${BLUE}[2/4] Criando ambiente virtual Python (.venv)...${NC}"
    python3 -m venv .venv || {
        echo -e "${RED}[AVISO] Falha ao criar venv. Instalando pacotes de venv do sistema...${NC}"
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
        fi
        python3 -m venv .venv
    }
fi

source .venv/bin/activate

# 3. Instalar dependências se não estiverem presentes
if ! python3 -c "import playwright, websockets, camoufox" &> /dev/null; then
    echo -e "${BLUE}[3/4] Instalando dependências (playwright, websockets, camoufox, requests)...${NC}"
    pip install --upgrade pip
    pip install playwright websockets camoufox requests
    echo -e "${BLUE}[4/4] Baixando navegadores (Chromium e Camoufox)...${NC}"
    python3 -m playwright install chromium
    python3 -m camoufox fetch || true
    if command -v sudo &> /dev/null; then
        sudo .venv/bin/python3 -m playwright install-deps chromium 2>/dev/null || true
    fi
fi

# 4. Executar o cliente remoto
echo -e "${GREEN}========================================================${NC}"
echo -e "${GREEN}   Iniciando o Cliente Remoto Playwright...${NC}"
echo -e "${GREEN}   Conectando em: ${VPS_URL}${NC}"
echo -e "${GREEN}========================================================${NC}"
echo ""

CLIENT_SCRIPT="remote_client.py"
if [ ! -f "$CLIENT_SCRIPT" ] && [ -f "../remote_client.py" ]; then
    CLIENT_SCRIPT="../remote_client.py"
fi

if [ -f "launcher.py" ]; then
    exec .venv/bin/python3 launcher.py "$@"
elif [ -f "../launcher.py" ]; then
    exec .venv/bin/python3 ../launcher.py "$@"
else
    exec .venv/bin/python3 "$CLIENT_SCRIPT" --url "$VPS_URL" "$@"
fi
