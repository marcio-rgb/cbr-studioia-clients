#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR ESTÚDIO IA - CLIENT LAUNCHER & AUTO-UPDATER (DESKTOP GUI & CLI)
  Design System: Warm Dark Mode (CBR Estúdio IA)
  Repositório Oficial: https://github.com/marcio-rgb/cbr-studioia-clients
=============================================================================
"""

import os
import sys
import json
import time
import hashlib
import getpass
import argparse
import threading
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import runpy
import base64
import traceback
from pathlib import Path

# Configuração Universal do Diretório de Cache dos Navegadores Playwright
def get_playwright_browsers_path() -> str:
    custom_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if custom_path and custom_path != "0":
        return os.path.abspath(os.path.expanduser(custom_path))
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return os.path.join(local_appdata, "ms-playwright")
        return os.path.expanduser("~\\AppData\\Local\\ms-playwright")
    return os.path.expanduser("~/.cache/ms-playwright")

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = get_playwright_browsers_path()

# Dependências embutidas para o runtime do robô (PyInstaller Bundle)
import asyncio
import websockets
try:
    import playwright
    import camoufox
except ImportError:
    pass

# Constantes de Configuração
DEFAULT_SERVER_URL = "https://ia.creditobr.com.br"
GITHUB_RAW_FALLBACK = "https://raw.githubusercontent.com/marcio-rgb/cbr-studioia-clients/main/client/remote_client.py"
APP_DIR = Path.home() / ".cbragents"
SESSION_FILE = APP_DIR / "session.json"
LOCAL_SCRIPT_FILE = APP_DIR / "remote_client.py"
LOCAL_ENGINE_FILE = APP_DIR / "engine.py"

# Cores do Sistema CBR Estúdio IA (Warm Dark Theme)
BG_MAIN = "#141211"       # Dark 900
BG_CARD = "#1c1917"       # Dark 800
BG_INPUT = "#0c0a09"      # Dark 950
BORDER_COLOR = "#292524"  # Stone 800
BORDER_FOCUS = "#ea580c"  # Orange 600
TEXT_MAIN = "#f5f5f4"     # Stone 100
TEXT_MUTED = "#a8a29e"    # Stone 400
TEXT_HINT = "#78716c"     # Stone 500
ACCENT_ORANGE = "#ea580c" # Orange 600
ACCENT_HOVER = "#f97316"  # Orange 500
ACCENT_AMBER = "#f59e0b"  # Amber 500
SUCCESS_GREEN = "#10b981" # Emerald 500
DANGER_ROSE = "#f43f5e"   # Rose 500


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


def sync_remote_client(server_url: str, token: str, log_fn=print) -> Path:
    """Sincroniza o código do remote_client.py e engine.py via API autenticada ou local."""
    code_str = None
    server_sha256 = None
    engine_str = None

    # Garante cópia local do engine.py se existir no repositório
    repo_engine = Path(__file__).resolve().parent.parent / "libs" / "browser" / "engine.py"
    if not repo_engine.exists():
        repo_engine = Path(__file__).resolve().parent / "engine.py"
    if repo_engine.exists():
        try:
            with open(repo_engine, "r", encoding="utf-8") as f:
                engine_content = f.read()
            with open(LOCAL_ENGINE_FILE, "w", encoding="utf-8") as f:
                f.write(engine_content)
        except Exception:
            pass

    # 1. Tenta baixar via API Oficial do CBR Estúdio IA
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
                engine_str = data.get("engine_code")
                if engine_str:
                    with open(LOCAL_ENGINE_FILE, "w", encoding="utf-8") as ef:
                        ef.write(engine_str)
    except Exception as e:
        log_fn(f"[i] API direta indisponível para atualização ({e}), consultando GitHub público...")

    # 2. Fallback: Se não tiver engine.py baixado, baixa direto do GitHub público
    if not LOCAL_ENGINE_FILE.exists() or LOCAL_ENGINE_FILE.stat().st_size == 0 or not engine_str:
        try:
            gh_engine_url = "https://raw.githubusercontent.com/marcio-rgb/cbr-studioia-clients/main/engine.py"
            req_eng = urllib.request.Request(gh_engine_url, headers={"User-Agent": "CBR-Agents-Desktop/2.5"})
            with urllib.request.urlopen(req_eng, timeout=6) as res_eng:
                if res_eng.status == 200:
                    with open(LOCAL_ENGINE_FILE, "w", encoding="utf-8") as ef:
                        ef.write(res_eng.read().decode("utf-8"))
        except Exception as gh_eng_err:
            log_fn(f"[!] Aviso ao baixar engine.py do GitHub: {gh_eng_err}")

    # 3. Fallback: Consulta repositório público do GitHub para remote_client.py
    if not code_str:
        try:
            req = urllib.request.Request(
                GITHUB_RAW_FALLBACK,
                headers={"User-Agent": "CBR-Agents-Desktop/2.5"}
            )
            with urllib.request.urlopen(req, timeout=6) as res:
                if res.status == 200:
                    code_str = res.read().decode("utf-8")
                    server_sha256 = hashlib.sha256(code_str.encode("utf-8")).hexdigest()
        except Exception as gh_err:
            log_fn(f"[!] Aviso GitHub: {gh_err}")

    # 4. Compara SHA-256 local
    local_sha256 = None
    if LOCAL_SCRIPT_FILE.exists():
        with open(LOCAL_SCRIPT_FILE, "r", encoding="utf-8") as f:
            local_content = f.read()
            local_sha256 = hashlib.sha256(local_content.encode("utf-8")).hexdigest()

    if code_str:
        if server_sha256 != local_sha256:
            log_fn(f"[⟳] Atualizando script do robô (SHA: {server_sha256[:8]})...")
            with open(LOCAL_SCRIPT_FILE, "w", encoding="utf-8") as f:
                f.write(code_str)
            log_fn("[✔] Robô atualizado com sucesso!")
        else:
            log_fn("[✔] Robô já está na versão mais recente.")
        return LOCAL_SCRIPT_FILE

    if LOCAL_SCRIPT_FILE.exists():
        log_fn("[✔] Usando versão em cache local.")
        return LOCAL_SCRIPT_FILE

    fallback = Path(__file__).parent / "remote_client.py"
    if fallback.exists():
        return fallback

    raise RuntimeError("Não foi possível encontrar o arquivo remote_client.py.")


def build_ws_url(server_url: str) -> str:
    """Converte URL HTTP para WebSocket."""
    url = server_url.rstrip("/")
    if url.startswith("https://"):
        ws = "wss://" + url[8:]
    elif url.startswith("http://"):
        ws = "ws://" + url[7:]
    else:
        ws = "wss://" + url
    return f"{ws}/ws" if not ws.endswith("/ws") else ws


def is_chromium_installed() -> bool:
    """Verifica se os binários do Chromium estão instalados no diretório do Playwright."""
    bw_path = Path(get_playwright_browsers_path())
    if not bw_path.exists():
        return False
    for cdir in bw_path.glob("chromium-*"):
        if sys.platform == "win32":
            if any(cdir.glob("**/chrome.exe")):
                return True
        else:
            for f in cdir.glob("**/chrome"):
                if f.is_file() and os.access(f, os.X_OK):
                    return True
    return False


def is_camoufox_installed() -> bool:
    """Verifica se os binários do Camoufox estão instalados localmente."""
    try:
        import camoufox.pkgman as pm
        lp = pm.launch_path()
        if lp and os.path.exists(str(lp)):
            return True
        ver = pm.installed_verstr()
        return ver is not None
    except Exception:
        return False


def install_chromium(log_fn=print) -> bool:
    """Instala o navegador Chromium para Playwright com suporte multiplataforma e PyInstaller."""
    log_fn("[📥] Baixando e instalando navegador Chromium para Playwright...")
    env = os.environ.copy()
    pw_path = get_playwright_browsers_path()
    env["PLAYWRIGHT_BROWSERS_PATH"] = pw_path
    os.makedirs(pw_path, exist_ok=True)

    # 1. Driver Node nativo do Playwright
    try:
        from playwright._impl._driver import compute_driver_executable
        node_path, cli_js = compute_driver_executable()
        cmd = [str(node_path), str(cli_js), "install", "chromium"]
        proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.stdout:
            for line in proc.stdout.splitlines():
                if line.strip():
                    log_fn(f"  [Playwright] {line.strip()}")
        if proc.returncode == 0 and is_chromium_installed():
            log_fn("[✔] Chromium instalado com sucesso via driver Playwright!")
            return True
    except Exception as e:
        log_fn(f"[!] Driver interno Playwright indisponível: {e}")

    # 2. Executável python -m playwright
    try:
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.stdout:
            for line in proc.stdout.splitlines():
                if line.strip():
                    log_fn(f"  [Playwright] {line.strip()}")
        if proc.returncode == 0 and is_chromium_installed():
            log_fn("[✔] Chromium instalado com sucesso via python -m playwright!")
            return True
    except Exception as e:
        log_fn(f"[!] Subprocesso python -m playwright indisponível: {e}")

    # 3. Binário global playwright no PATH
    try:
        cmd = ["playwright", "install", "chromium"]
        proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.stdout:
            for line in proc.stdout.splitlines():
                if line.strip():
                    log_fn(f"  [Playwright] {line.strip()}")
        if proc.returncode == 0 and is_chromium_installed():
            log_fn("[✔] Chromium instalado com sucesso via CLI global!")
            return True
    except Exception as e:
        log_fn(f"[!] CLI global playwright indisponível: {e}")

    return is_chromium_installed()


def install_camoufox(log_fn=print) -> bool:
    """Instala o navegador Camoufox (Firefox Anti-Detect)."""
    log_fn("[📥] Baixando e instalando navegador Camoufox (Firefox Anti-Detect)...")
    env = os.environ.copy()

    # 1. API Python CamoufoxFetcher
    try:
        import camoufox.pkgman as pm
        fetcher = pm.CamoufoxFetcher()
        fetcher.fetch()
        if is_camoufox_installed():
            log_fn("[✔] Camoufox instalado com sucesso via CamoufoxFetcher!")
            return True
    except Exception as e:
        log_fn(f"[!] CamoufoxFetcher falhou ({e}), tentando método alternativo...")

    # 2. Executável python -m camoufox fetch
    try:
        cmd = [sys.executable, "-m", "camoufox", "fetch"]
        proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.stdout:
            for line in proc.stdout.splitlines():
                if line.strip():
                    log_fn(f"  [Camoufox] {line.strip()}")
        if proc.returncode == 0 and is_camoufox_installed():
            log_fn("[✔] Camoufox instalado com sucesso via subprocesso!")
            return True
    except Exception as e:
        log_fn(f"[!] Subprocesso camoufox fetch falhou: {e}")

    return is_camoufox_installed()


def ensure_browsers(engine: str = "all", force: bool = False, log_fn=print):
    """
    Garante que o navegador selecionado esteja instalado antes de iniciar o robô.
    """
    pw_path = get_playwright_browsers_path()
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = pw_path
    os.makedirs(pw_path, exist_ok=True)

    eng = (engine or "all").strip().lower()

    if eng in ["all", "playwright", "chromium"]:
        if force or not is_chromium_installed():
            log_fn("[🔍] Verificando/Instalando navegador Chromium para Playwright...")
            install_chromium(log_fn=log_fn)
        else:
            log_fn("[✔] Chromium já está pronto.")

    if eng in ["all", "camoufox", "firefox"]:
        if force or not is_camoufox_installed():
            log_fn("[🔍] Verificando/Instalando navegador Camoufox...")
            install_camoufox(log_fn=log_fn)
        else:
            log_fn("[✔] Camoufox já está pronto.")


# =============================================================================
#  INTERFACE GRÁFICA DESKTOP (GUI MODERNA - WARM DARK THEME)
# =============================================================================

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    session = load_session()
    root = tk.Tk()
    root.title("CBR Estúdio IA - WebPilot Desktop")
    root.geometry("540x720")
    root.minsize(500, 650)
    root.configure(bg=BG_MAIN)

    # Variáveis de Estado
    server_var = tk.StringVar(value=session.get("server_url") or DEFAULT_SERVER_URL)
    email_var = tk.StringVar(value=session.get("email") or "")
    pass_var = tk.StringVar(value="")
    engine_var = tk.StringVar(value=session.get("browser_engine") or "camoufox")
    status_text = tk.StringVar(value="Pronto para conectar")
    is_running = tk.BooleanVar(value=False)
    client_proc = None

    # Estilos ttk
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(".", background=BG_MAIN, foreground=TEXT_MAIN)
    style.configure("TFrame", background=BG_MAIN)
    style.configure("Card.TFrame", background=BG_CARD)

    # Frame Principal
    main_frame = tk.Frame(root, bg=BG_MAIN, padx=24, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # 1. CABEÇALHO COM LOGO
    header_frame = tk.Frame(main_frame, bg=BG_MAIN)
    header_frame.pack(fill=tk.X, pady=(0, 16))

    logo_label = tk.Label(
        header_frame,
        text="CBR ESTÚDIO IA",
        font=("Segoe UI", 18, "bold"),
        fg=ACCENT_ORANGE,
        bg=BG_MAIN
    )
    logo_label.pack(anchor="w")

    sub_label = tk.Label(
        header_frame,
        text="Robô Visual de Automação Local (WebPilot)",
        font=("Segoe UI", 10),
        fg=TEXT_MUTED,
        bg=BG_MAIN
    )
    sub_label.pack(anchor="w", pady=(2, 0))

    # 2. CARD DO FORMULÁRIO DE CONEXÃO
    card = tk.Frame(main_frame, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=16, pady=16)
    card.pack(fill=tk.X, pady=(0, 14))

    # Campo Servidor
    tk.Label(card, text="URL DO SISTEMA", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
    server_entry = tk.Entry(
        card, textvariable=server_var, font=("Segoe UI", 10),
        bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=ACCENT_ORANGE,
        relief=tk.FLAT, highlightbackground=BORDER_COLOR, highlightcolor=BORDER_FOCUS, highlightthickness=1
    )
    server_entry.pack(fill=tk.X, pady=(4, 12), ipady=5)

    # Campo E-mail
    tk.Label(card, text="E-MAIL DE ACESSO", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
    email_entry = tk.Entry(
        card, textvariable=email_var, font=("Segoe UI", 10),
        bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=ACCENT_ORANGE,
        relief=tk.FLAT, highlightbackground=BORDER_COLOR, highlightcolor=BORDER_FOCUS, highlightthickness=1
    )
    email_entry.pack(fill=tk.X, pady=(4, 12), ipady=5)

    # Campo Senha
    pass_label = tk.Label(card, text="SENHA (DEIXE EM BRANCO SE JÁ LOGADO)", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_CARD)
    pass_label.pack(anchor="w")
    pass_entry = tk.Entry(
        card, textvariable=pass_var, show="•", font=("Segoe UI", 10),
        bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=ACCENT_ORANGE,
        relief=tk.FLAT, highlightbackground=BORDER_COLOR, highlightcolor=BORDER_FOCUS, highlightthickness=1
    )
    pass_entry.pack(fill=tk.X, pady=(4, 14), ipady=5)

    # 3. SELETOR DE NAVEGADOR
    tk.Label(card, text="MOTOR DE NAVEGAÇÃO", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w", pady=(0, 6))
    
    engine_frame = tk.Frame(card, bg=BG_CARD)
    engine_frame.pack(fill=tk.X)

    camou_radio = tk.Radiobutton(
        engine_frame, text="Camoufox (Firefox Anti-Detect)",
        variable=engine_var, value="camoufox",
        font=("Segoe UI", 9, "bold"), fg=ACCENT_AMBER, bg=BG_CARD,
        selectcolor=BG_INPUT, activebackground=BG_CARD, activeforeground=ACCENT_AMBER
    )
    camou_radio.pack(anchor="w", pady=2)

    playwright_radio = tk.Radiobutton(
        engine_frame, text="Playwright (Chromium Rápido)",
        variable=engine_var, value="playwright",
        font=("Segoe UI", 9), fg=TEXT_MAIN, bg=BG_CARD,
        selectcolor=BG_INPUT, activebackground=BG_CARD, activeforeground=TEXT_MAIN
    )
    playwright_radio.pack(anchor="w", pady=2)

    # 4. BOTÃO DE AÇÃO PRINCIPAL (CONECTAR / DESCONECTAR)
    action_btn = tk.Button(
        main_frame,
        text="Conectar Robô",
        font=("Segoe UI", 11, "bold"),
        bg=ACCENT_ORANGE,
        fg="#ffffff",
        activebackground=ACCENT_HOVER,
        activeforeground="#ffffff",
        relief=tk.FLAT,
        cursor="hand2",
        pady=8
    )
    action_btn.pack(fill=tk.X, pady=(0, 12))

    # 5. STATUS BADGE
    status_frame = tk.Frame(main_frame, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=6)
    status_frame.pack(fill=tk.X, pady=(0, 10))

    status_dot = tk.Label(status_frame, text="●", font=("Segoe UI", 12), fg=TEXT_HINT, bg=BG_CARD)
    status_dot.pack(side=tk.LEFT, padx=(0, 6))

    status_lbl = tk.Label(status_frame, textvariable=status_text, font=("Segoe UI", 9, "bold"), fg=TEXT_MAIN, bg=BG_CARD)
    status_lbl.pack(side=tk.LEFT)

    # 6. CAIXA DE LOGS DO TERMINAL
    tk.Label(main_frame, text="LOGS EM TEMPO REAL", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_MAIN).pack(anchor="w", pady=(0, 4))
    
    log_box = tk.Text(
        main_frame,
        height=9,
        bg=BG_INPUT,
        fg=TEXT_MUTED,
        insertbackground=ACCENT_ORANGE,
        font=("Consolas", 8),
        relief=tk.FLAT,
        highlightbackground=BORDER_COLOR,
        highlightthickness=1,
        padx=8,
        pady=6
    )
    log_box.pack(fill=tk.BOTH, expand=True)

    def append_log(msg: str):
        def _insert():
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)
        root.after(0, _insert)

    def set_ui_state(running: bool):
        is_running.set(running)
        if running:
            action_btn.config(text="Desconectar Robô", bg=DANGER_ROSE, activebackground="#e11d48")
            status_dot.config(fg=SUCCESS_GREEN)
            status_text.set("Conectado ao Estúdio IA (Executando)")
            server_entry.config(state="disabled")
            email_entry.config(state="disabled")
            pass_entry.config(state="disabled")
        else:
            action_btn.config(text="Conectar Robô", bg=ACCENT_ORANGE, activebackground=ACCENT_HOVER)
            status_dot.config(fg=TEXT_HINT)
            status_text.set("Desconectado")
            server_entry.config(state="normal")
            email_entry.config(state="normal")
            pass_entry.config(state="normal")

    def connect_worker():
        nonlocal client_proc
        server_url = server_var.get().strip().rstrip("/")
        if not server_url.startswith("http://") and not server_url.startswith("https://"):
            server_url = "https://" + server_url

        email = email_var.get().strip()
        password = pass_var.get().strip()
        engine = engine_var.get()

        token = session.get("token")
        
        append_log(f"[*] Iniciando conexão com {server_url}...")
        status_text.set("Autenticando...")

        # Autenticação se necessária
        if password or not token or session.get("email") != email:
            if not email or not password:
                append_log("[✖] Informe o e-mail e a senha para autenticar.")
                root.after(0, lambda: messagebox.showerror("Erro", "Por favor, digite o e-mail e a senha."))
                root.after(0, lambda: set_ui_state(False))
                return

            try:
                login_data = urllib.parse.urlencode({"username": email, "password": password}).encode("utf-8")
                req = urllib.request.Request(f"{server_url}/token", data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req, timeout=8) as res:
                    if res.status == 200:
                        data = json.loads(res.read().decode("utf-8"))
                        token = data.get("access_token")
                        user_id = data.get("user_id") or (data.get("user", {}) or {}).get("id")
                        session["server_url"] = server_url
                        session["email"] = email
                        session["token"] = token
                        if user_id:
                            session["user_id"] = user_id
                        session["browser_engine"] = engine
                        save_session(session)
                        append_log(f"[✔] Autenticado com sucesso como {email} (User #{user_id or '?'})!")
            except Exception as auth_err:
                append_log(f"[✖] Falha no login: {auth_err}")
                root.after(0, lambda: messagebox.showerror("Falha de Autenticação", f"Erro ao realizar login: {auth_err}"))
                root.after(0, lambda: set_ui_state(False))
                return

        # Sincronização do script
        status_text.set("Sincronizando robô...")
        try:
            script_path = sync_remote_client(server_url, token, log_fn=append_log)
        except Exception as sync_err:
            append_log(f"[✖] Erro ao sincronizar: {sync_err}")
            root.after(0, lambda: set_ui_state(False))
            return

        # Verificação e Auto-Instalação dos Navegadores
        status_text.set("Verificando navegadores...")
        try:
            ensure_browsers(engine=engine, log_fn=append_log)
        except Exception as bw_err:
            append_log(f"[!] Aviso ao verificar navegadores: {bw_err}")

        # Inicia o robô via subprocesso isolado
        ws_url = build_ws_url(server_url)
        append_log(f"[🚀] Conectando motor {engine.upper()} ao WebSocket: {ws_url}")
        root.after(0, lambda: set_ui_state(True))

        user_id = session.get("user_id")
        if getattr(sys, 'frozen', False):
            # Se estiver rodando como executável standalone PyInstaller
            cmd = [sys.executable, "--run-client", str(script_path), "--url", ws_url, "--engine", engine]
        else:
            # Se estiver rodando como script python direto
            cmd = [sys.executable, str(script_path), "--url", ws_url, "--engine", engine]

        if user_id:
            cmd.extend(["--user-id", str(user_id)])
        if token:
            cmd.extend(["--token", str(token)])

        try:
            client_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            for line in iter(client_proc.stdout.readline, ''):
                if line:
                    append_log(line.strip())
            client_proc.wait()
        except Exception as proc_err:
            append_log(f"[✖] Erro na execução: {proc_err}")
        finally:
            append_log("[i] Robô finalizado.")
            root.after(0, lambda: set_ui_state(False))

    def on_action_click():
        nonlocal client_proc
        if is_running.get():
            if client_proc:
                append_log("[!] Encerrando processo do robô...")
                client_proc.terminate()
                client_proc = None
            set_ui_state(False)
        else:
            threading.Thread(target=connect_worker, daemon=True).start()

    action_btn.config(command=on_action_click)

    # Centraliza janela na tela
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = (ws // 2) - (w // 2)
    y = (hs // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")

    root.mainloop()


# =============================================================================
#  ENTRYPOINT
# =============================================================================

def handle_python_internal_args():
    """Suporte universal para chamadas de subprocessos internos (Playwright, Camoufox, multiprocessing)."""
    argv = sys.argv[1:]
    if not argv:
        return

    # 1. Se chamado como subprocesso para rodar o cliente
    if argv[0] == "--run-client" and len(argv) > 1:
        client_script = argv[1]
        remaining_args = argv[2:]
        sys.argv = [client_script] + remaining_args

        # Adiciona o diretório do script e APP_DIR ao sys.path
        script_dir = os.path.dirname(os.path.abspath(client_script))
        app_dir_str = str(APP_DIR)
        for p in [script_dir, app_dir_str]:
            if p and p not in sys.path:
                sys.path.insert(0, p)

        import runpy
        runpy.run_path(client_script, run_name="__main__")
        sys.exit(0)

    # 2. Se chamado com flags do Python (-c, -m, -B, -S, -I, etc.)
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-c" and i + 1 < len(argv):
            code = argv[i + 1]
            sys.argv = ["-c"] + argv[i + 2:]
            exec(code, {"__name__": "__main__"})
            sys.exit(0)
        elif arg == "-m" and i + 1 < len(argv):
            mod = argv[i + 1]
            sys.argv = [mod] + argv[i + 2:]
            import runpy
            runpy.run_module(mod, run_name="__main__", alter_sys=True)
            sys.exit(0)
        elif arg.startswith("-") and arg not in ["--cli", "-h", "--help"]:
            # Ignora flags python normais e avança
            i += 1
            continue
        else:
            break


def main():
    handle_python_internal_args()

    parser = argparse.ArgumentParser(description="CBR Estúdio IA Desktop Launcher")
    parser.add_argument("--cli", action="store_true", help="Executar em modo linha de comando (sem interface gráfica)")
    parser.add_argument("--url", default="", help="URL do WebSocket")
    parser.add_argument("--engine", default="chromium", help="Motor de navegação")
    parser.add_argument("--user-id", type=int, default=None, help="ID do usuário")
    parser.add_argument("--token", default=None, help="Token JWT")
    args = parser.parse_args()

    if args.cli or not HAS_TK:
        print("=== CBR ESTÚDIO IA - MODO CLI ===")
        server_url = session.get("server_url") or DEFAULT_SERVER_URL
        token = session.get("token")
        if not token:
            print("[!] Token ausente. Execute com interface gráfica para autenticar.")
            sys.exit(1)
        script_path = sync_remote_client(server_url, token)
        ws_url = build_ws_url(server_url)
        engine_cli = session.get("browser_engine", "camoufox")
        try:
            ensure_browsers(engine=engine_cli, log_fn=print)
        except Exception as bw_err:
            print(f"[!] Aviso ao verificar navegadores: {bw_err}")

        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--run-client", str(script_path), "--url", ws_url, "--engine", engine_cli]
        else:
            cmd = [sys.executable, str(script_path), "--url", ws_url, "--engine", engine_cli]
        subprocess.run(cmd)
    else:
        try:
            run_gui()
        except Exception as e:
            print(f"[!] Erro ao abrir interface gráfica: {e}. Alternando para CLI...")
            sys.exit(1)


if __name__ == "__main__":
    main()
