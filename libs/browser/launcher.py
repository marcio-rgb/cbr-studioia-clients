# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER LAUNCHER & STEALTH ENGINE
  Inicializador do navegador Playwright (Chromium/Firefox/WebKit/Camoufox)
  com anti-bot stealth, gestão de proxies autenticados, locales e permissões.
=============================================================================
"""

import os
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("Browser.Launcher")


async def init_browser_engine(
    p_obj,
    engine: Optional[str] = None,
    headless: bool = True,
    proxy_config: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
    viewport: Optional[Dict[str, int]] = None
) -> Tuple[Any, Any, Any]:
    """
    Inicializa o navegador (Browser), Contexto com Proteção Anti-Detecção Stealth e Página ativa.
    Suporta Camoufox, Chromium nativo e conexão remota com servidor Playwright.
    """
    ws_url = os.environ.get("PLAYWRIGHT_SERVER_WS_URL")
    selected_engine = (engine or os.environ.get("BROWSER_ENGINE") or "").strip().lower()

    browser = None

    # 1. Tenta Camoufox se solicitado
    if "camoufox" in selected_engine:
        try:
            from camoufox.async_api import AsyncCamoufox
            camoufox_kwargs = {"headless": headless, "humanize": True}
            if proxy_config:
                camoufox_kwargs["proxy"] = proxy_config
            browser = await AsyncCamoufox(**camoufox_kwargs).__aenter__()
            logger.info("Navegador Camoufox inicializado com sucesso.")
        except Exception as e:
            logger.warning(f"Não foi possível iniciar o Camoufox ({e}). Alternando para Chromium Stealth...")

    # 2. Conexão com microsserviço Playwright se disponível
    if not browser and ws_url and headless:
        try:
            browser = await p_obj.chromium.connect(ws_url, timeout=30000)
            logger.info(f"Conectado ao servidor Playwright remoto em {ws_url}")
        except Exception as ws_err:
            logger.warning(f"Falha ao conectar no servidor Playwright ({ws_url}): {ws_err}. Abrindo localmente...")

    # 3. Chromium Local com Argumentos Stealth
    if not browser:
        stealth_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1280,800",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-dev-shm-usage",
            "--disable-gpu"
        ]
        launch_kwargs = {
            "headless": headless,
            "args": stealth_args
        }
        if proxy_config:
            launch_kwargs["proxy"] = proxy_config
        browser = await p_obj.chromium.launch(**launch_kwargs)

    # Criação de contexto com evasão anti-detecção
    ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    vp = viewport or {"width": 1280, "height": 800}

    context_kwargs = {
        "user_agent": ua,
        "viewport": vp,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "accept_downloads": True
    }
    if proxy_config:
        context_kwargs["proxy"] = proxy_config

    context = await browser.new_context(**context_kwargs)

    # Injeta script anti-detecção
    stealth_js = """
    (() => {
        try {
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            const originalQuery = window.navigator.permissions?.query;
            if (originalQuery) {
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            }
        } catch (e) {}
    })();
    """
    await context.add_init_script(stealth_js)
    page = await context.new_page()
    return browser, context, page
