# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - INTERNAL BROWSER CLIENT (SERVER / HEADLESS SESSION MANAGER)
  Camada de compatibilidade e gerenciamento de sessão interna do Playwright.
  Delega para LocalBrowserSessionManager (IBrowserSessionManager) e
  DatabaseExecutionObserver (IExecutionObserver).
=============================================================================
"""

import os
import sys
import json
import base64
import asyncio
import zipfile
import datetime
import time
import io
import contextvars
from typing import Optional, List, Dict, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor

from playwright.async_api import async_playwright
from libs.utils import setup_logger
from libs.browser.interfaces import IBrowserSessionManager, IExecutionObserver
from libs.browser.observers import (
    ObserverRegistry,
    DatabaseExecutionObserver,
    ConsoleExecutionObserver,
    NullExecutionObserver
)
from libs.browser.session import (
    LocalBrowserSessionManager,
    sanitize_folder_name,
    DOWNLOADS_DIR
)
from libs.browser.engine import (
    BrowserTools,
    execute_code_sandbox,
    execute_browser_action,
    init_browser_engine,
    inspect_dom
)

logger = setup_logger("Browser.ClientInternal")

# Instância singleton do gerenciador de sessão local
_session_manager = LocalBrowserSessionManager()

# Variáveis de contexto e mocks retrocompatíveis
_playwright_var = _session_manager._playwright_var
_browser_var = _session_manager._browser_var
_context_var = _session_manager._context_var
_page_var = _session_manager._page_var
_downloaded_file_var = _session_manager._downloaded_file_var
_downloaded_files_var = _session_manager._downloaded_files_var
_active_downloads_var = _session_manager._active_downloads_var
_run_id_var = _session_manager._run_id_var
_headless_var = _session_manager._headless_var
_agent_name_var = _session_manager._agent_name_var


class GlobalActionsLogMock:
    def __init__(self):
        self._actions = []

    def get(self, default=None):
        if self._actions is None:
            return default
        return self._actions

    def set(self, value):
        self._actions = value


_actions_log_var = GlobalActionsLogMock()


# =============================================================================
# PERSISTÊNCIA EM BANCO DE DADOS (VIA IExecutionObserver)
# =============================================================================

def db_log_progress(message: str) -> None:
    """Grava mensagem no banco em tempo real via Observer."""
    run_id = _run_id_var.get()
    ObserverRegistry.get_observer().log_progress(message, run_id)


def db_register_download(filename: str, filepath: str) -> None:
    """Registra arquivo baixado via Observer."""
    run_id = _run_id_var.get()
    ObserverRegistry.get_observer().register_download(filename, filepath, run_id)


async def save_global_download(download) -> None:
    """Listener global para capturar e salvar downloads emitidos pela página."""
    await _session_manager.save_global_download(download)


# =============================================================================
# CONTROLE DE PÁGINA E CONTEXTO ATIVOS
# =============================================================================

def get_active_page():
    return _session_manager.get_page()


def get_active_context():
    return _session_manager.get_context()


def get_active_browser():
    return _session_manager.get_browser()


def set_page(page) -> None:
    _session_manager.set_page(page)


def set_context(context) -> None:
    _session_manager.set_context(context)


def set_browser(browser) -> None:
    _session_manager.set_browser(browser)


def handle_new_page(new_page) -> None:
    asyncio.create_task(_session_manager.handle_new_page(new_page))


# =============================================================================
# CICLO DE VIDA DO NAVEGADOR INTERNO
# =============================================================================

async def init_browser_session(
    headless: bool = True,
    run_id: Optional[int] = None,
    agent_name: Optional[str] = None,
    ws_url: Optional[str] = None,
    engine: Optional[str] = None
) -> str:
    """Inicializa a sessão Playwright interna com proteções anti-bot (Stealth)."""
    return await _session_manager.init_session(
        engine=engine,
        headless=headless,
        run_id=run_id,
        agent_name=agent_name
    )


def is_browser_session_active() -> bool:
    return _session_manager.is_active()


async def ensure_browser_initialized() -> None:
    await _session_manager.ensure_initialized()


async def close_browser_session() -> str:
    return await _session_manager.close_session()


def get_actions_log() -> List[Dict[str, Any]]:
    return _actions_log_var.get() or []


def reset_actions_log() -> None:
    _actions_log_var.set([])


def get_downloaded_file() -> Optional[str]:
    return _session_manager.get_downloaded_file()


# =============================================================================
# EXECUTORES INTERNOS DIRETO NO ENGINE
# =============================================================================

def get_internal_browser_tools(
    login_user: str = "",
    login_pass: str = "",
    params: Optional[Any] = None
) -> BrowserTools:
    """Cria uma instância de BrowserTools apontando para a sessão interna ativa."""
    page = get_active_page()
    context = get_active_context()
    browser = get_active_browser()
    playwright = _session_manager._playwright_var.get() or _session_manager._global_playwright
    return BrowserTools(
        page=page,
        context=context,
        browser=browser,
        playwright=playwright,
        login_user=login_user,
        login_pass=login_pass,
        params=params,
        register_download_fn=db_register_download
    )


async def execute_internal_code(
    code: str,
    login_user: str = "",
    login_pass: str = "",
    run_id: Optional[int] = None,
    engine: Optional[str] = None,
    params: Optional[Any] = None,
    timeout: Optional[float] = None,
    **kwargs
) -> Dict[str, Any]:
    """Executa snippet ou script Python no navegador interno ativo via engine.py."""
    await ensure_browser_initialized()
    page = get_active_page()
    if not page:
        return {"status": "error", "error": "Navegador interno não pôde ser inicializado."}

    context = page.context if hasattr(page, "context") else get_active_context()
    browser = get_active_browser()
    playwright = _session_manager._playwright_var.get() or _session_manager._global_playwright

    extra_ctx = {}
    if params:
        extra_ctx["params"] = params

    return await execute_code_sandbox(
        page, context, browser, playwright, code,
        login_user=login_user,
        login_pass=login_pass,
        extra_context=extra_ctx,
        register_download_fn=db_register_download
    )


async def execute_internal_action(
    action: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Executa uma ação atômica no navegador interno ativo via engine.py."""
    await ensure_browser_initialized()
    page = get_active_page()
    if not page:
        return {"status": "error", "error": "Navegador interno não inicializado."}

    context = get_active_context()
    browser = get_active_browser()
    playwright = _session_manager._playwright_var.get() or _session_manager._global_playwright

    return await execute_browser_action(
        page, context, browser, playwright, action,
        params=params,
        register_download_fn=db_register_download
    )
