# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - REMOTE PLAYWRIGHT CLIENT (STANDALONE DESKTOP CLIENT)
  Cliente autônomo de automação para execução na máquina do usuário (Linux / Windows).
  Conecta via WebSocket à porta 8384 e despacha as ações e snippets de código
  diretamente para o motor unificado libs/browser/engine.py.
=============================================================================
"""

import os
import sys
import io
import json
import base64
import asyncio
import inspect
import argparse
import time
import re
import random
import urllib.request
import hashlib
from typing import Optional, Dict, Any, Tuple, Union

# Limpa bloqueio de diretório se configurado incorretamente
if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == "0":
    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)

# Adiciona os caminhos de busca ao sys.path (~/.cbragents, diretório atual e raiz do projeto)
_current_dir = os.path.dirname(os.path.abspath(__file__))
_app_dir = os.path.expanduser("~/.cbragents")
_project_root = os.path.abspath(os.path.join(_current_dir, ".."))

for p in [_app_dir, _current_dir, _project_root]:
    if p and os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    import websockets
except ImportError:
    print("❌ Pacote 'websockets' não encontrado. Instale com: pip install websockets")
    sys.exit(1)

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Pacote 'playwright' não encontrado. Instale com: pip install playwright && playwright install")
    sys.exit(1)

# Importa o motor unificado e a classe BrowserTools com auto-recuperação
BrowserTools = None
execute_browser_action = None
execute_code_sandbox = None
inspect_dom = None

try:
    from libs.browser.engine import (
        BrowserTools,
        execute_browser_action,
        execute_code_sandbox,
        inspect_dom
    )
except ImportError:
    try:
        from engine import (
            BrowserTools,
            execute_browser_action,
            execute_code_sandbox,
            inspect_dom
        )
    except ImportError:
        # Fallback de emergência: baixa engine.py para ~/.cbragents se estiver ausente
        try:
            os.makedirs(_app_dir, exist_ok=True)
            local_eng_path = os.path.join(_app_dir, "engine.py")
            if not os.path.exists(local_eng_path) or os.path.getsize(local_eng_path) == 0:
                print("🔄 Baixando motor unificado 'engine.py' do repositório oficial...")
                gh_eng_url = "https://raw.githubusercontent.com/marcio-rgb/cbr-studioia-clients/main/engine.py"
                req = urllib.request.Request(gh_eng_url, headers={"User-Agent": "CBR-Agents-Desktop/2.5"})
                with urllib.request.urlopen(req, timeout=8) as res:
                    if res.status == 200:
                        with open(local_eng_path, "w", encoding="utf-8") as f:
                            f.write(res.read().decode("utf-8"))
                        if _app_dir not in sys.path:
                            sys.path.insert(0, _app_dir)
            from engine import (
                BrowserTools,
                execute_browser_action,
                execute_code_sandbox,
                inspect_dom
            )
        except Exception as fallback_err:
            print(f"❌ Erro ao carregar o motor unificado 'engine.py': {fallback_err}")
            sys.exit(1)

# =============================================================================
# SHIM DE COMPATIBILIDADE RETROATIVA (MOCK DO PACOTE LIBS PARA CLIENTE STANDALONE)
# =============================================================================
import types
if "libs" not in sys.modules:
    _libs_mod = types.ModuleType("libs")
    _browser_mod = types.ModuleType("libs.browser")
    _tools_mod = types.ModuleType("libs.browser.tools")
    _tools_mod.set_page = lambda p: None
    _tools_mod.get_page = lambda: None
    _tools_mod.get_downloaded_file = lambda: None
    _tools_mod.db_log_progress = lambda msg: None
    _browser_mod.tools = _tools_mod
    _libs_mod.browser = _browser_mod
    sys.modules["libs"] = _libs_mod
    sys.modules["libs.browser"] = _browser_mod
    sys.modules["libs.browser.tools"] = _tools_mod


# =============================================================================
# GERENCIAMENTO DE NAVEGADORES E DEPENDÊNCIAS PLAYWRIGHT
# =============================================================================

def ensure_playwright_browsers():
    try:
        import subprocess
        print("🔍 Verificando navegadores e dependências (Chromium e Camoufox)...")
        try:
            from playwright._impl._driver import compute_driver_executable
            driver_executable, driver_env = compute_driver_executable()
            subprocess.run([str(driver_executable), "install", "chromium"], env=driver_env, check=False)
        except Exception:
            try:
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
            except Exception:
                pass

        try:
            from camoufox.pkg import download_official_browser
            download_official_browser()
        except Exception:
            try:
                subprocess.run([sys.executable, "-m", "camoufox", "fetch"], check=False)
            except Exception:
                pass
    except Exception as e:
        print(f"⚠️ Aviso ao verificar navegadores: {e}")


# =============================================================================
# CICLO DE VIDA DO CLIENTE WEBSOCKET
# =============================================================================

async def run_client(urls: list, engine: str = "chromium"):
    print("========================================================")
    print("  CBR Agents Remote Client (Visual Automation Engine)")
    print(f"  Motor Selecionado: {engine.upper()}")
    print(f"  URLs de Conexão: {', '.join(urls)}")
    print("========================================================")
    print("")

    url_index = 0
    while True:
        target_url = urls[url_index % len(urls)]
        try:
            print(f"🔗 Conectando ao servidor em {target_url}...")
            async with websockets.connect(target_url, ping_interval=None) as websocket:
                print(f"✅ Conectado com sucesso ao servidor em {target_url}! Aguardando missões...")

                browser = None
                context = None
                page = None
                p = None

                if engine.lower() == "camoufox":
                    try:
                        from camoufox.async_api import AsyncCamoufox
                        print("🦊 Inicializando motor Camoufox Anti-Detect (Firefox C++ Stealth)...")
                        try:
                            camou_manager = AsyncCamoufox(
                                headless=False,
                                humanize=True,
                                locale="pt-BR",
                                geoip=True
                            )
                            browser = await camou_manager.start()
                        except Exception as geoip_err:
                            print(f"⚠️ GeoIP desativado no Camoufox ({geoip_err}). Inicializando sem GeoIP...")
                            camou_manager = AsyncCamoufox(
                                headless=False,
                                humanize=True,
                                locale="pt-BR",
                                geoip=False
                            )
                            browser = await camou_manager.start()

                        context = await browser.new_context(
                            viewport={"width": 1280, "height": 800},
                            locale="pt-BR",
                            timezone_id="America/Sao_Paulo"
                        )
                        page = await context.new_page()
                        print("✅ Camoufox inicializado com sucesso!")
                    except Exception as camou_err:
                        print(f"⚠️ Não foi possível iniciar o Camoufox ({camou_err}). Alternando para Chromium Stealth...")
                        browser = None

                if browser is None:
                    print("🌐 Inicializando motor Chromium Stealth...")
                    p = await async_playwright().start()
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
                        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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
                        ],
                        device_scale_factor=1,
                        has_touch=False,
                        is_mobile=False
                    )
                    
                    stealth_js = """
                    (() => {
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                        Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
                        window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                        const originalQuery = window.navigator.permissions ? window.navigator.permissions.query : null;
                        if (originalQuery) {
                            window.navigator.permissions.query = (parameters) => (
                                parameters.name === 'notifications' ?
                                    Promise.resolve({ state: Notification.permission }) :
                                    originalQuery(parameters)
                            );
                        }
                    })();
                    """
                    await context.add_init_script(stealth_js)
                    page = await context.new_page()

                frames_dir = "scratch/frames"
                os.makedirs(frames_dir, exist_ok=True)
                os.makedirs("static/screenshots", exist_ok=True)
                frame_counter = 0

                async def record_frame():
                    nonlocal frame_counter
                    try:
                        frame_counter += 1
                        frame_path = os.path.join(frames_dir, f"frame_{frame_counter:04d}.png")
                        await page.screenshot(path=frame_path, full_page=False)
                    except Exception:
                        pass

                try:
                    async for message in websocket:
                        data = json.loads(message)
                        msg_id = data.get("id")
                        action = data.get("action")
                        params = data.get("params", {})

                        print(f"📩 Ação recebida da VPS [{msg_id}]: {action}")
                        response = {"id": msg_id, "status": "success", "result": {}}

                        try:
                            action_res = await execute_browser_action(
                                page, context, browser, p, action, params, record_frame_fn=record_frame
                            )
                            if action_res.get("status") == "error":
                                response["status"] = "error"
                                response["error"] = action_res.get("error")
                            else:
                                response["result"] = action_res
                                print(f"   ✔ Ação '{action}' executada com sucesso.")

                        except Exception as action_err:
                            print(f"⚠️ Erro ao executar ação '{action}': {action_err}")
                            response["status"] = "error"
                            response["error"] = str(action_err)

                            err_msg = str(action_err).lower()
                            if "closed" in err_msg or "target page" in err_msg:
                                print("⚠️ Detectado que o navegador ou a página foi fechada. Reiniciando sessão...")
                                raise RuntimeError("Navegador fechado localmente")

                        await websocket.send(json.dumps(response))

                finally:
                    print("Fechando navegador local...")
                    if browser:
                        try: await browser.close()
                        except Exception: pass
                    if p:
                        try: await p.stop()
                        except Exception: pass

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as conn_err:
            print(f"🔴 Conexão falhou/perdida em {target_url} ({conn_err}). Tentando próxima URL em 3 segundos...")
            url_index += 1
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️ Erro inesperado em {target_url}: {e}. Reconectando em 3 segundos...")
            url_index += 1
            await asyncio.sleep(3)


# =============================================================================
# AUTO-ATUALIZAÇÃO DO CÓDIGO FONTE A PARTIR DA VPS
# =============================================================================

def check_and_auto_update(vps_url: str):
    try:
        http_base = vps_url.replace("wss://", "https://").replace("ws://", "http://")
        if "/ws" in http_base:
            http_base = http_base.split("/ws")[0]
        
        version_url = f"{http_base}/api/client/version"
        download_url = f"{http_base}/api/client/download/remote_client.py"
        
        req = urllib.request.Request(version_url, headers={'User-Agent': 'OmniClientAutoUpdater'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                remote_hash = data.get("hash")
                remote_size = data.get("size")
                
                current_file = os.path.abspath(__file__)
                with open(current_file, "rb") as f:
                    local_content = f.read()
                local_hash = hashlib.md5(local_content).hexdigest()
                local_size = len(local_content)
                
                if remote_hash and (remote_hash != local_hash or remote_size != local_size):
                    print("🔄 [AUTO-UPDATER] Nova versão do cliente detectada na VPS!")
                    print(f"   Hash Local:  {local_hash[:8]} ({local_size} bytes)")
                    print(f"   Hash Remoto: {remote_hash[:8]} ({remote_size} bytes)")
                    print("⏬ Baixando código remote_client.py atualizado da VPS...")
                    
                    dl_req = urllib.request.Request(download_url, headers={'User-Agent': 'OmniClientAutoUpdater'})
                    with urllib.request.urlopen(dl_req, timeout=8) as dl_resp:
                        if dl_resp.status == 200:
                            new_code = dl_resp.read()
                            with open(current_file, "wb") as f:
                                f.write(new_code)
                            print("✅ [AUTO-UPDATER] Código do cliente atualizado com sucesso! Reiniciando cliente...")
                            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        pass


# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CBR Agents Desktop Remote Client")
    parser.add_argument("--url", default="", help="URL WebSocket da VPS (ex: wss://ia.creditobr.com.br/ws ou ws://localhost:8384)")
    parser.add_argument("--engine", default="chromium", choices=["chromium", "camoufox", "playwright"], help="Motor de navegação: chromium (padrão) ou camoufox")
    args = parser.parse_args()

    urls_to_try = []
    if args.url:
        urls_to_try.append(args.url)
        if "localhost" in args.url or "127.0.0.1" in args.url:
            urls_to_try.append("ws://localhost:8384")
            urls_to_try.append("ws://localhost:8080/ws")
        else:
            if args.url != "wss://ia.creditobr.com.br/ws":
                urls_to_try.append("wss://ia.creditobr.com.br/ws")
    else:
        urls_to_try = [
            "wss://ia.creditobr.com.br/ws",
            "ws://ia.creditobr.com.br:8384",
            "ws://localhost:8384"
        ]

    try:
        if urls_to_try:
            check_and_auto_update(urls_to_try[0])
        ensure_playwright_browsers()
        asyncio.run(run_client(urls_to_try, engine=args.engine))
    except KeyboardInterrupt:
        print("\nCliente encerrado pelo usuário.")
        sys.exit(0)
