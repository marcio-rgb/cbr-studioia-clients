#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - CLIENT LAUNCHER & AUTO-UPDATER (DESKTOP GUI & CLI)
  Design System: Warm Dark Mode (CBR Agents)
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
from pathlib import Path

# Constantes de Configuração
DEFAULT_SERVER_URL = "https://ia.creditobr.com.br"
GITHUB_RAW_FALLBACK = "https://raw.githubusercontent.com/marcio-rgb/cbr-studioia-clients/main/client/remote_client.py"
APP_DIR = Path.home() / ".cbragents"
SESSION_FILE = APP_DIR / "session.json"
LOCAL_SCRIPT_FILE = APP_DIR / "remote_client.py"

# Cores do Sistema CBR Agents (Warm Dark Theme)
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
    """Sincroniza o código do remote_client.py via API autenticada ou GitHub."""
    code_str = None
    server_sha256 = None

    # 1. Tenta baixar via API Oficial do CBR Agents
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
        log_fn(f"[i] API direta indisponível para atualização ({e}), consultando GitHub público...")

    # 2. Fallback: Consulta repositório público do GitHub
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

    # 3. Compara SHA-256 local
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


# =============================================================================
#  INTERFACE GRÁFICA DESKTOP (GUI MODERNA - WARM DARK THEME)
# =============================================================================

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    session = load_session()
    root = tk.Tk()
    root.title("CBR Agents - WebPilot Desktop")
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
        text="CBR AGENTS",
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
                        session["server_url"] = server_url
                        session["email"] = email
                        session["token"] = token
                        session["browser_engine"] = engine
                        save_session(session)
                        append_log(f"[✔] Autenticado com sucesso como {email}!")
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

        # Inicia o robô via subprocesso isolado
        ws_url = build_ws_url(server_url)
        append_log(f"[🚀] Conectando motor {engine.upper()} ao WebSocket: {ws_url}")
        root.after(0, lambda: set_ui_state(True))

        if getattr(sys, 'frozen', False):
            # Se estiver rodando como executável standalone PyInstaller
            cmd = [sys.executable, "--run-client", str(script_path), "--url", ws_url, "--engine", engine]
        else:
            # Se estiver rodando como script python direto
            cmd = [sys.executable, str(script_path), "--url", ws_url, "--engine", engine]

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

def main():
    # Se chamado como subprocesso para executar o script do robô (PyInstaller bundle)
    if len(sys.argv) > 1 and sys.argv[1] == "--run-client":
        client_script = sys.argv[2]
        remaining_args = sys.argv[3:]
        sys.argv = [client_script] + remaining_args
        import runpy
        runpy.run_path(client_script, run_name="__main__")
        sys.exit(0)

    parser = argparse.ArgumentParser(description="CBR Agents Desktop Launcher")
    parser.add_argument("--cli", action="store_true", help="Executar no modo terminal/CLI")
    args = parser.parse_args()

    # Se chamado com --cli ou sem display disponível, executa modo console
    if args.cli or ("DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ and os.name != "nt"):
        # Execução CLI
        session = load_session()
        print("=== CBR AGENTS - MODO CLI ===")
        server_url = session.get("server_url") or DEFAULT_SERVER_URL
        token = session.get("token")
        if not token:
            print("[!] Token ausente. Execute com interface gráfica para autenticar.")
            sys.exit(1)
        script_path = sync_remote_client(server_url, token)
        ws_url = build_ws_url(server_url)
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--run-client", str(script_path), "--url", ws_url, "--engine", session.get("browser_engine", "camoufox")]
        else:
            cmd = [sys.executable, str(script_path), "--url", ws_url, "--engine", session.get("browser_engine", "camoufox")]
        subprocess.run(cmd)
    else:
        try:
            run_gui()
        except Exception as e:
            print(f"[!] Erro ao abrir interface gráfica: {e}. Alternando para CLI...")
            sys.exit(1)


if __name__ == "__main__":
    main()
