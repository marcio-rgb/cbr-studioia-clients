# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - INTERNAL BROWSER CLIENT (SERVER / HEADLESS SESSION MANAGER)
  Camada de compatibilidade e gerenciamento de sessão interna do Playwright.
  Delega para BrowserSessionPool (multi-tenant por source_id) e 
  LocalBrowserSessionManager / DatabaseExecutionObserver.
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

from playwright.async_api import async_playwright, Page, BrowserContext, Browser, Playwright
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
from libs.browser.session_pool import session_pool
from libs.browser.engine import (
    BrowserTools,
    execute_code_sandbox,
    execute_browser_action,
    init_browser_engine,
    inspect_dom
)

logger = setup_logger("Browser.ClientInternal")

# Instância singleton do gerenciador de sessão local (fallback legado)
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
# CONTROLE DE PÁGINA E CONTEXTO ATIVOS (COM SUPORTE A SOURCE_ID)
# =============================================================================

def get_active_page(source_id: Optional[Union[int, str]] = None) -> Optional[Page]:
    """Retorna a Page ativa do SessionPool para o source_id ou fallback no session_manager."""
    if source_id is not None:
        p = session_pool.get_page(source_id)
        if p and not (hasattr(p, "is_closed") and p.is_closed()):
            return p
    p_pool = session_pool.get_page(0)
    if p_pool and not (hasattr(p_pool, "is_closed") and p_pool.is_closed()):
        return p_pool
    return _session_manager.get_page()


def get_active_context(source_id: Optional[Union[int, str]] = None) -> Optional[BrowserContext]:
    """Retorna o BrowserContext ativo para o source_id."""
    if source_id is not None:
        ctx = session_pool.get_context(source_id)
        if ctx:
            return ctx
    ctx_pool = session_pool.get_context(0)
    if ctx_pool:
        return ctx_pool
    return _session_manager.get_context()


def get_active_browser() -> Optional[Browser]:
    """Retorna a instância compartilhada do Browser."""
    return session_pool.get_browser() or _session_manager.get_browser()


def set_page(page: Any, source_id: Optional[Union[int, str]] = None) -> None:
    _session_manager.set_page(page)


def set_context(context: Any, source_id: Optional[Union[int, str]] = None) -> None:
    _session_manager.set_context(context)


def set_browser(browser: Any) -> None:
    _session_manager.set_browser(browser)


def handle_new_page(new_page: Any) -> None:
    asyncio.create_task(_session_manager.handle_new_page(new_page))


# =============================================================================
# CICLO DE VIDA DO NAVEGADOR INTERNO
# =============================================================================

async def init_browser_session(
    headless: bool = True,
    run_id: Optional[int] = None,
    agent_name: Optional[str] = None,
    ws_url: Optional[str] = None,
    engine: Optional[str] = None,
    source_id: Optional[Union[int, str]] = None,
    proxy_config: Optional[Dict[str, str]] = None
) -> str:
    """Inicializa a sessão Playwright interna no session_pool."""
    _, page = await session_pool.get_or_create(
        source_id=source_id,
        headless=headless,
        proxy_config=proxy_config,
        engine=engine
    )
    _session_manager.set_page(page)
    _session_manager.set_context(page.context)
    _session_manager.set_browser(session_pool.get_browser())
    return "Browser session initialized in SessionPool."


def is_browser_session_active(source_id: Optional[Union[int, str]] = None) -> bool:
    """Verifica se há sessão ativa para o source_id especificado."""
    if source_id is not None:
        return session_pool.is_active(source_id)
    return session_pool.is_active(0) or _session_manager.is_active()


async def ensure_browser_initialized(
    source_id: Optional[Union[int, str]] = None,
    headless: bool = True,
    proxy_config: Optional[Dict[str, str]] = None
) -> None:
    """Garante que a sessão do Playwright para o source_id está pronta."""
    page = get_active_page(source_id=source_id)
    if not page or (hasattr(page, "is_closed") and page.is_closed()):
        await session_pool.ensure_page_initialized(
            source_id=source_id,
            headless=headless,
            proxy_config=proxy_config
        )


async def close_browser_session(source_id: Optional[Union[int, str]] = None) -> str:
    """Encerra a sessão do source_id liberando recursos."""
    if source_id is not None:
        closed = await session_pool.close_session(source_id)
        return f"Sessão #{source_id} encerrada: {closed}"
    await session_pool.close_all()
    await _session_manager.close_session()
    return "Todas as sessões foram encerradas."


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
    params: Optional[Any] = None,
    source_id: Optional[Union[int, str]] = None
) -> BrowserTools:
    """Cria uma instância de BrowserTools apontando para a sessão ativa do source_id."""
    page = get_active_page(source_id=source_id)
    context = get_active_context(source_id=source_id)
    browser = get_active_browser()
    playwright = session_pool.get_playwright() or _session_manager._playwright_var.get() or _session_manager._global_playwright
    return BrowserTools(
        page=page,
        context=context,
        browser=browser,
        playwright=playwright,
        login_user=login_user,
        login_pass=login_pass,
        params=params,
        register_download_fn=db_register_download,
        source_id=int(source_id) if source_id is not None else None
    )


async def execute_internal_code(
    code: str,
    login_user: str = "",
    login_pass: str = "",
    run_id: Optional[int] = None,
    engine: Optional[str] = None,
    params: Optional[Any] = None,
    timeout: Optional[float] = None,
    source_id: Optional[Union[int, str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Executa snippet ou script Python no navegador interno ativo isolado por source_id."""
    try:
        context, page = await session_pool.get_or_create(
            source_id=source_id,
            headless=True,
            engine=engine
        )
        if not page or (hasattr(page, "is_closed") and page.is_closed()):
            return {"status": "error", "error": "Navegador interno não pôde ser inicializado."}

        browser = session_pool.get_browser() or get_active_browser()
        playwright = session_pool.get_playwright() or _session_manager._playwright_var.get()

        _session_manager.set_page(page)
        _session_manager.set_context(context)

        extra_ctx: Dict[str, Any] = {}
        if params:
            extra_ctx["params"] = params
        if source_id is not None:
            extra_ctx["source_id"] = source_id
        if kwargs.get("reset_output"):
            extra_ctx["reset_output"] = True

        sid_int = int(source_id) if source_id is not None else None
        return await execute_code_sandbox(
            page, context, browser, playwright, code,
            login_user=login_user,
            login_pass=login_pass,
            extra_context=extra_ctx,
            register_download_fn=db_register_download,
            source_id=sid_int
        )
    except Exception as e:
        logger.error(f"Erro ao executar snippet no navegador interno: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"Erro na execução do snippet: {e}",
            "logs": f"[ERRO] {type(e).__name__}: {str(e)}"
        }


async def execute_internal_action(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    source_id: Optional[Union[int, str]] = None
) -> Dict[str, Any]:
    """Executa uma ação atômica no navegador interno ativo via engine.py."""
    try:
        await ensure_browser_initialized(source_id=source_id)
        page = get_active_page(source_id=source_id)
        if not page:
            return {"status": "error", "error": "Navegador interno não inicializado."}

        context = get_active_context(source_id=source_id)
        browser = get_active_browser()
        playwright = session_pool.get_playwright() or _session_manager._playwright_var.get()

        return await execute_browser_action(
            page, context, browser, playwright, action,
            params=params,
            register_download_fn=db_register_download
        )
    except Exception as e:
        logger.error(f"Erro ao executar ação interna '{action}': {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"Erro ao executar ação '{action}': {e}"
        }
