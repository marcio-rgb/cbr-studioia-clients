#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR Agents - Client Launcher & Auto-Updater
  Repositório Oficial: https://github.com/marcio-rgb/cbr-studioia-clients
=============================================================================
"""

import os
import sys
import json
import hashlib
import getpass
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Constantes de Configuração
DEFAULT_SERVER_URL = "https://ia.creditobr.com.br"
GITHUB_RAW_FALLBACK = "https://raw.githubusercontent.com/marcio-rgb/cbr-studioia-clients/main/client/remote_client.py"
APP_DIR = Path.home() / ".cbragents"
SESSION_FILE = APP_DIR / "session.json"
LOCAL_SCRIPT_FILE = APP_DIR / "remote_client.py"

# Cores ANSI para Terminal (Warm Dark Palette)
C_ORANGE = "\033[38;2;234;88;12m"
C_AMBER = "\033[38;2;245;158;11m"
C_EMERALD = "\033[38;2;52;211;153m"
C_ROSE = "\033[38;2;251;113;133m"
C_STONE = "\033[38;2;168;162;158m"
C_WHITE = "\033[38;2;245;245;244m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"


def print_banner():
    """Exibe o cabeçalho estilizado do CBR Agents."""
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{C_ORANGE}{C_BOLD}")
    print("  ██████╗██████╗ ██████╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗███████╗")
    print(" ██╔════╝██╔══██╗██╔══██╗    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝")
    print(" ██║     ██████╔╝██████╔╝    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ███████╗")
    print(" ██║     ██╔══██╗██╔══██╗    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ╚════██║")
    print(" ╚██████╗██████╔╝██║  ██║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ███████║")
    print(f"  ╚═════╝╚═════╝ ╚═╝  ╚═╝    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝{C_RESET}")
    print(f"{C_AMBER}          ✦ ROBÔ VISUAL LOCAL DE ALTA PERFORMANCE (WEBPILOT) ✦{C_RESET}")
    print(f"{C_STONE}             Conexão Segura e Auto-Atualização em Tempo Real{C_RESET}")
    print(f"{C_STONE}-----------------------------------------------------------------------------{C_RESET}\n")


def load_session() -> dict:
    """Carrega as credenciais e configurações salvas localmente."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_session(data: dict):
    """Salva a sessão localmente com permissões restritas."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    try:
        os.chmod(SESSION_FILE, 0o600)
    except Exception:
        pass


def ask_server_url(saved_session: dict) -> str:
    """Solicita ou confirma a URL base do servidor."""
    default_url = saved_session.get("server_url") or DEFAULT_SERVER_URL
    print(f"{C_WHITE}{C_BOLD}[1/4] URL do Sistema CBR Agents:{C_RESET}")
    print(f"{C_STONE}Pressione [ENTER] para usar o padrão ({C_AMBER}{default_url}{C_STONE}) ou digite outra:{C_RESET}")
    try:
        user_input = input(f"{C_ORANGE}➔ URL: {C_RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{C_ROSE}[!] Execução cancelada pelo usuário.{C_RESET}")
        sys.exit(0)

    url = user_input if user_input else default_url
    url = url.rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


def authenticate(server_url: str, saved_session: dict) -> str:
    """Valida o token existente ou realiza o login solicitando e-mail e senha."""
    token = saved_session.get("token")
    user_email = saved_session.get("email")

    print(f"\n{C_WHITE}{C_BOLD}[2/4] Autenticação no Sistema:{C_RESET}")

    # 1. Tenta validar o token existente se houver
    if token:
        try:
            req = urllib.request.Request(
                f"{server_url}/api/webpilot/client/code",
                headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req, timeout=5) as res:
                if res.status == 200:
                    print(f"{C_EMERALD}[✔] Sessão ativa autenticada como: {C_BOLD}{user_email or 'Usuário Autorizado'}{C_RESET}")
                    return token
        except Exception:
            print(f"{C_AMBER}[i] Sessão anterior expirada. Por favor, autentique-se novamente.{C_RESET}")

    # 2. Solicita login
    while True:
        try:
            email = input(f"{C_ORANGE}➔ E-mail: {C_RESET}").strip()
            if not email:
                continue
            password = getpass.getpass(f"{C_ORANGE}➔ Senha: {C_RESET}")
            if not password:
                continue

            # Faz o POST /token no formato application/x-www-form-urlencoded
            login_data = urllib.parse.urlencode({
                "username": email,
                "password": password
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{server_url}/token",
                data=login_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            print(f"{C_STONE}Autenticando...{C_RESET}", end="\r")
            with urllib.request.urlopen(req, timeout=10) as res:
                if res.status == 200:
                    resp_json = json.loads(res.read().decode("utf-8"))
                    new_token = resp_json.get("access_token")
                    if new_token:
                        saved_session["server_url"] = server_url
                        saved_session["email"] = email
                        saved_session["token"] = new_token
                        save_session(saved_session)
                        print(f"{C_EMERALD}[✔] Login realizado com sucesso! Bem-vindo(a), {email}!{C_RESET}")
                        return new_token
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"{C_ROSE}[✖] E-mail ou senha incorretos. Tente novamente.{C_RESET}")
            else:
                print(f"{C_ROSE}[✖] Erro no servidor HTTP {e.code}: {e.reason}{C_RESET}")
        except Exception as e:
            print(f"{C_ROSE}[✖] Falha ao conectar ao servidor ({server_url}): {e}{C_RESET}")
            print(f"{C_STONE}Deseja tentar novamente ou alterar a URL?{C_RESET}")


def select_browser_engine(saved_session: dict) -> str:
    """Menu de seleção interativa do motor de navegador."""
    print(f"\n{C_WHITE}{C_BOLD}[3/4] Escolha o Motor de Navegação:{C_RESET}")
    print(f"  {C_ORANGE}[1]{C_RESET} {C_WHITE}Playwright Padrão{C_RESET} {C_STONE}(Chromium - Ultra Rápido e Determinístico){C_RESET}")
    print(f"  {C_ORANGE}[2]{C_RESET} {C_WHITE}Camoufox Stealth{C_RESET} {C_STONE}(Firefox C++ Anti-Detect - Furtivo contra Cloudflare/Captchas){C_RESET}")

    last_engine = saved_session.get("browser_engine", "camoufox")
    default_opt = "2" if last_engine == "camoufox" else "1"

    try:
        choice = input(f"{C_ORANGE}➔ Selecione [1 ou 2] (Padrão: {default_opt}): {C_RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{C_ROSE}[!] Execução cancelada.{C_RESET}")
        sys.exit(0)

    if not choice:
        choice = default_opt

    if choice == "1":
        engine = "playwright"
        print(f"{C_EMERALD}[✔] Motor selecionado: Playwright (Chromium){C_RESET}")
    else:
        engine = "camoufox"
        print(f"{C_EMERALD}[✔] Motor selecionado: Camoufox (Firefox Anti-Detect){C_RESET}")

    saved_session["browser_engine"] = engine
    save_session(saved_session)
    return engine


def sync_remote_client_code(server_url: str, token: str) -> Path:
    """
    Sincroniza o código do remote_client.py a partir do endpoint autenticado da API
    ou com fallback para o repositório público do GitHub.
    """
    print(f"\n{C_WHITE}{C_BOLD}[4/4] Verificando Atualizações do Robô...{C_RESET}")

    code_str = None
    server_sha256 = None

    # 1. Tenta baixar via API Oficial do CBR Agents (Autenticada)
    try:
        req = urllib.request.Request(
            f"{server_url}/api/webpilot/client/code",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=6) as res:
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                code_str = data.get("code")
                server_sha256 = data.get("sha256")
    except Exception as e:
        print(f"{C_STONE}[i] API direta indisponível para código ({e}), consultando GitHub público...{C_RESET}")

    # 2. Fallback: Consulta o repositório público no GitHub
    if not code_str:
        try:
            req = urllib.request.Request(
                GITHUB_RAW_FALLBACK,
                headers={"User-Agent": "CBR-Agents-Launcher/2.5"}
            )
            with urllib.request.urlopen(req, timeout=6) as res:
                if res.status == 200:
                    code_str = res.read().decode("utf-8")
                    server_sha256 = hashlib.sha256(code_str.encode("utf-8")).hexdigest()
        except Exception as gh_err:
            print(f"{C_AMBER}[!] Não foi possível checar GitHub ({gh_err}).{C_RESET}")

    # 3. Compara com a versão local
    local_sha256 = None
    if LOCAL_SCRIPT_FILE.exists():
        with open(LOCAL_SCRIPT_FILE, "r", encoding="utf-8") as f:
            local_content = f.read()
            local_sha256 = hashlib.sha256(local_content.encode("utf-8")).hexdigest()

    if code_str:
        if server_sha256 != local_sha256:
            print(f"{C_AMBER}[⟳] Nova versão do robô detectada! Atualizando script local...{C_RESET}")
            with open(LOCAL_SCRIPT_FILE, "w", encoding="utf-8") as f:
                f.write(code_str)
            print(f"{C_EMERALD}[✔] Script atualizado com sucesso! (SHA: {server_sha256[:8]}...){C_RESET}")
        else:
            print(f"{C_EMERALD}[✔] Robô já está na versão mais recente! (SHA: {local_sha256[:8]}...){C_RESET}")
        return LOCAL_SCRIPT_FILE

    # 4. Se não conseguiu baixar mas tem o script em cache, usa o local
    if LOCAL_SCRIPT_FILE.exists():
        print(f"{C_AMBER}[✔] Operando com a versão em cache local.{C_RESET}")
        return LOCAL_SCRIPT_FILE

    # 5. Se não existe em cache nem conseguiu baixar, tenta encontrar no diretório de trabalho
    fallback_local = Path(__file__).parent / "remote_client.py"
    if fallback_local.exists():
        return fallback_local

    raise RuntimeError("Não foi possível obter o arquivo remote_client.py.")


def build_websocket_url(server_url: str) -> str:
    """Converte URL HTTP/HTTPS para protocolo WebSocket WS/WSS."""
    ws_url = server_url
    if ws_url.startswith("https://"):
        ws_url = "wss://" + ws_url[8:]
    elif ws_url.startswith("http://"):
        ws_url = "ws://" + ws_url[7:]
    
    # Se não tiver /ws no final, adiciona
    if not ws_url.endswith("/ws"):
        ws_url = f"{ws_url}/ws"
    return ws_url


def main():
    print_banner()
    saved_session = load_session()

    # 1. URL do Servidor
    server_url = ask_server_url(saved_session)

    # 2. Autenticação
    token = authenticate(server_url, saved_session)

    # 3. Escolha do Motor de Navegador
    engine = select_browser_engine(saved_session)

    # 4. Sincronização do remote_client.py
    script_path = sync_remote_client_code(server_url, token)

    # 5. Execução do Robô
    ws_url = build_websocket_url(server_url)
    print(f"\n{C_EMERALD}{C_BOLD}============================================================================={C_RESET}")
    print(f"{C_EMERALD}{C_BOLD}  🚀 INICIANDO CLIENTE WEBPILOT (MODO VISUAL CONECTADO){C_RESET}")
    print(f"{C_STONE}  • Servidor: {C_WHITE}{server_url}{C_RESET}")
    print(f"{C_STONE}  • Canal WebSocket: {C_WHITE}{ws_url}{C_RESET}")
    print(f"{C_STONE}  • Motor de Navegação: {C_WHITE}{engine.upper()}{C_RESET}")
    print(f"{C_EMERALD}{C_BOLD}============================================================================={C_RESET}\n")

    cmd = [
        sys.executable,
        str(script_path),
        "--url", ws_url,
        "--engine", engine
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(f"\n{C_AMBER}[i] Cliente WebPilot finalizado pelo usuário.{C_RESET}")


if __name__ == "__main__":
    main()
