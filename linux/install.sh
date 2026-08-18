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

VPS_URL="${1:-ws://ia.creditobr.com.br:8384}"

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
    echo -e "${BLUE}[3/4] Instalando dependências (playwright, websockets, camoufox)...${NC}"
    pip install --upgrade pip
    pip install playwright websockets camoufox
    echo -e "${BLUE}[4/4] Baixando navegadores (Chromium e Camoufox)...${NC}"
    playwright install chromium
    python3 -m camoufox fetch || true
    if command -v sudo &> /dev/null; then
        sudo .venv/bin/playwright install-deps chromium || true
    fi
fi

# 4. Criar remote_playwright_client.py se ausente
if [ ! -f "remote_playwright_client.py" ]; then
    cat << 'EOF' > remote_playwright_client.py
import asyncio
import json
import argparse
import sys
import websockets
from playwright.async_api import async_playwright

async def run_client(vps_url: str):
    print("========================================================")
    print("  Omni Playwright Remote Client (Outbound Connection)")
    print(f"  Conectando ao Servidor VPS: {vps_url}")
    print("========================================================")
    print("")

    while True:
        try:
            print(f"🔗 Conectando ao servidor VPS em {vps_url}...")
            async with websockets.connect(vps_url, ping_interval=20, ping_timeout=20) as websocket:
                print("✅ Conectado com sucesso ao servidor VPS! Aguardando missões...")

                async with async_playwright() as p:
                    stealth_args = [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                        "--window-size=1280,800",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-extensions"
                    ]
                    browser = await p.chromium.launch(
                        headless=False,
                        args=stealth_args
                    )
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                        locale="pt-BR",
                        timezone_id="America/Sao_Paulo",
                        permissions=[
                            "geolocation",
                            "notifications",
                            "camera",
                            "microphone",
                            "clipboard-read",
                            "clipboard-write",
                            "accelerometer",
                            "gyroscope",
                            "magnetometer"
                        ]
                    )

                    stealth_js = """
                    (() => {
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                        Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
                        window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                    })();
                    """
                    await context.add_init_script(stealth_js)
                    page = await context.new_page()

                    try:
                        async for message in websocket:
                            data = json.loads(message)
                            msg_id = data.get("id")
                            action = data.get("action")
                            params = data.get("params", {})

                            print(f"📩 Ação recebida da VPS [{msg_id}]: {action} -> {params}")
                            response = {"id": msg_id, "status": "success", "result": {}}

                            try:
                                if action == "goto":
                                    url = params.get("url")
                                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                                    response["result"] = {"url": page.url, "title": await page.title()}

                                elif action == "click":
                                    selector = params.get("selector")
                                    await page.click(selector, timeout=30000)
                                    response["result"] = {"status": "clicked", "selector": selector}

                                elif action == "fill":
                                    selector = params.get("selector")
                                    text = params.get("text")
                                    await page.fill(selector, text, timeout=30000)
                                    response["result"] = {"status": "filled", "selector": selector}

                                elif action == "type":
                                    selector = params.get("selector")
                                    text = params.get("text")
                                    await page.type(selector, text, timeout=30000)
                                    response["result"] = {"status": "typed", "selector": selector}

                                elif action == "evaluate":
                                    script = params.get("script")
                                    eval_res = await page.evaluate(script)
                                    response["result"] = {"result": eval_res}

                                elif action == "screenshot":
                                    screenshot_bytes = await page.screenshot(full_page=False)
                                    import base64
                                    response["result"] = {"b64_image": base64.b64encode(screenshot_bytes).decode('utf-8')}

                                elif action == "get_html":
                                    content = await page.content()
                                    response["result"] = {"html": content}

                                else:
                                    response["status"] = "error"
                                    response["error"] = f"Ação desconhecida: {action}"

                            except Exception as action_err:
                                print(f"⚠️ Erro ao executar ação '{action}': {action_err}")
                                response["status"] = "error"
                                response["error"] = str(action_err)

                            await websocket.send(json.dumps(response))

                    finally:
                        print("Fechando navegador Chromium local...")
                        await browser.close()

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as conn_err:
            print(f"🔴 Conexão perdida com o servidor VPS ({conn_err}). Tentando reconectar em 5 segundos...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"⚠️ Erro inesperado: {e}. Reconectando em 5 segundos...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Omni Playwright Remote Client")
    parser.add_argument("--url", default="ws://ia.creditobr.com.br:8384", help="URL WebSocket da VPS (ex: ws://ia.creditobr.com.br:8384)")
    args = parser.parse_args()

    try:
        asyncio.run(run_client(args.url))
    except KeyboardInterrupt:
        print("\nCliente encerrado pelo usuário.")
        sys.exit(0)
EOF
fi

# 5. Executar imediatamente o cliente
echo -e "${GREEN}========================================================${NC}"
echo -e "${GREEN}   Iniciando o Cliente Remoto Playwright...${NC}"
echo -e "${GREEN}   Conectando em: ${VPS_URL}${NC}"
echo -e "${GREEN}========================================================${NC}"
echo ""

exec .venv/bin/python3 remote_playwright_client.py --url "$VPS_URL"
