# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - LOCAL BROWSER SESSION MANAGER (OOP PLAYWRIGHT LIFECYCLE)
  Implementação de IBrowserSessionManager para gerenciar o ciclo de vida
  do Playwright local/headless no servidor com isolamento de contexto (ContextVars).
=============================================================================
"""

import os
import sys
import json
import asyncio
import datetime
import contextvars
import zipfile
import re
from typing import Optional, List, Dict, Any, Union

from playwright.async_api import async_playwright
from libs.utils import setup_logger
from libs.browser.interfaces import IBrowserSessionManager
from libs.browser.observers import ObserverRegistry
from libs.browser.engine import init_browser_engine

logger = setup_logger("Browser.SessionManager")

DOWNLOADS_DIR = os.path.abspath("static/downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def sanitize_folder_name(name: Optional[str]) -> str:
    if not name:
        return "Geral"
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
    sanitized = re.sub(r'\s+', " ", sanitized)
    return sanitized.strip()


class LocalBrowserSessionManager(IBrowserSessionManager):
    """
    Gerenciador de sessão concreto que controla as instâncias locais
    do Playwright, isolando o estado por corrotina via contextvars.
    """

    def __init__(self):
        self._playwright_var = contextvars.ContextVar("_playwright", default=None)
        self._browser_var = contextvars.ContextVar("_browser", default=None)
        self._context_var = contextvars.ContextVar("_context", default=None)
        self._page_var = contextvars.ContextVar("_page", default=None)

        self._global_playwright = None
        self._global_browser = None
        self._global_context = None
        self._global_page = None

        self._downloaded_file_var = contextvars.ContextVar("_downloaded_file", default=None)
        self._downloaded_files_var = contextvars.ContextVar("_downloaded_files", default=None)
        self._active_downloads_var = contextvars.ContextVar("_active_downloads", default=0)
        self._run_id_var = contextvars.ContextVar("_run_id", default=None)
        self._headless_var = contextvars.ContextVar("_headless", default=True)
        self._agent_name_var = contextvars.ContextVar("_agent_name", default="Geral")

    def _observer(self):
        return ObserverRegistry.get_observer()

    def get_run_id(self) -> Optional[int]:
        return self._run_id_var.get()

    def set_run_id(self, run_id: Optional[int]) -> None:
        self._run_id_var.set(run_id)

    def log_progress(self, message: str) -> None:
        run_id = self._run_id_var.get()
        self._observer().log_progress(message, run_id)

    def register_download(self, filename: str, filepath: str) -> None:
        run_id = self._run_id_var.get()
        self._observer().register_download(filename, filepath, run_id)

    def get_page(self) -> Optional[Any]:
        return self._page_var.get() or self._global_page

    def get_context(self) -> Optional[Any]:
        return self._context_var.get() or self._global_context

    def get_browser(self) -> Optional[Any]:
        return self._browser_var.get() or self._global_browser

    def set_page(self, page: Any) -> None:
        self._page_var.set(page)
        self._global_page = page

    def set_context(self, context: Any) -> None:
        self._context_var.set(context)
        self._global_context = context

    def set_browser(self, browser: Any) -> None:
        self._browser_var.set(browser)
        self._global_browser = browser

    def is_active(self) -> bool:
        page = self.get_page()
        browser = self.get_browser()
        return browser is not None and page is not None

    async def handle_new_page(self, new_page: Any) -> None:
        """Listener para quando o navegador abrir uma nova aba/janela popup."""
        logger.info(f"Nova aba aberta detectada: {new_page.url}")
        self.set_page(new_page)
        browser = self.get_browser()
        if browser:
            browser._active_page = new_page
            browser._active_frame = new_page
        self.log_progress(f"Nova aba detectada: {new_page.url}")

        new_page.on("close", lambda p: self._handle_page_close(p))

    def _handle_page_close(self, closed_page: Any) -> None:
        logger.info(f"Aba fechada: {closed_page.url}")
        context = self.get_context()
        if context and hasattr(context, "pages"):
            open_pages = [p for p in context.pages if not p.is_closed()]
            if open_pages:
                active_page = open_pages[-1]
                self.set_page(active_page)
                browser = self.get_browser()
                if browser:
                    browser._active_page = active_page
                    browser._active_frame = active_page
                logger.info(f"Foco restaurado para a aba anterior: {active_page.url}")

    async def save_global_download(self, download: Any) -> None:
        """Listener global para capturar e salvar downloads emitidos pela página."""
        page = download.page
        context = getattr(page, "context", None)

        if context and hasattr(context, "_active_downloads"):
            context._active_downloads += 1

        try:
            filename = download.suggested_filename
            now = datetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H-%M-%S")

            agent_dir_name = sanitize_folder_name(self._agent_name_var.get())
            agent_dir = os.path.join(DOWNLOADS_DIR, agent_dir_name, date_str)
            os.makedirs(agent_dir, exist_ok=True)

            new_filename = f"{time_str}_{filename}"
            filepath = os.path.join(agent_dir, new_filename)

            logger.info(f"Download capturado: {filename}. Salvando em {filepath}...")
            self.log_progress(f"Download global capturado: '{filename}'. Salvando...")
            await download.save_as(filepath)
            self.register_download(new_filename, filepath)

            if context and hasattr(context, "_downloaded_files"):
                context._downloaded_files.append(filepath)
            if context:
                context._downloaded_file = filepath
            logger.info(f"Download salvo com sucesso: {filepath}")
            self.log_progress(f"Download concluído: '{new_filename}'")
        except Exception as e:
            logger.error(f"Erro no listener de download: {e}", exc_info=True)
            self.log_progress(f"Erro no listener de download: {str(e)}")
        finally:
            if context and hasattr(context, "_active_downloads"):
                context._active_downloads = max(0, context._active_downloads - 1)

    async def init_session(
        self,
        engine: Optional[str] = None,
        headless: bool = True,
        proxy_config: Optional[Dict[str, str]] = None,
        run_id: Optional[int] = None,
        agent_name: Optional[str] = None
    ) -> str:
        if agent_name:
            self._agent_name_var.set(agent_name)
        self._headless_var.set(headless)

        if run_id:
            self._run_id_var.set(run_id)
        else:
            env_run_id = os.getenv("RUN_ID")
            if env_run_id:
                try:
                    self._run_id_var.set(int(env_run_id))
                except ValueError:
                    pass

        env_headless = os.getenv("HEADLESS")
        if env_headless is not None:
            headless = env_headless.lower() in ("true", "1")

        selected_engine = (engine or os.getenv("BROWSER_ENGINE") or os.getenv("ENGINE") or "").strip().lower()

        logger.info(f"Inicializando motor de navegação interna ({selected_engine or 'chromium'}, headless={headless})...")
        self.log_progress(f"Inicializando navegador interno ({selected_engine or 'chromium'}, headless={headless})...")

        try:
            playwright = self._playwright_var.get() or self._global_playwright
            if not playwright:
                playwright = await async_playwright().start()
                self._playwright_var.set(playwright)
                self._global_playwright = playwright

            if not proxy_config:
                proxy_server = os.getenv("PROXY_SERVER")
                if proxy_server and proxy_server.strip():
                    proxy_config = {"server": proxy_server.strip()}
                    p_user = os.getenv("PROXY_USERNAME")
                    p_pass = os.getenv("PROXY_PASSWORD")
                    if p_user and p_pass:
                        proxy_config["username"] = p_user.strip()
                        proxy_config["password"] = p_pass.strip()

            browser, context, page = await init_browser_engine(
                playwright,
                engine=selected_engine,
                headless=headless,
                proxy_config=proxy_config
            )

            self.set_browser(browser)
            self.set_context(context)
            self.set_page(page)

            browser._active_page = page
            browser._active_frame = page
            context._downloaded_files = []
            context._downloaded_file = None
            context._active_downloads = 0

            page.on("download", self.save_global_download)
            context.on("page", self.handle_new_page)

            logger.info(f"✅ Navegador interno ({selected_engine or 'chromium'}) inicializado com sucesso!")
            self.log_progress(f"Navegador interno pronto ({selected_engine or 'chromium'}).")
            return "Sucesso: Sessão do navegador inicializada com sucesso."
        except Exception as e:
            logger.error(f"Falha ao inicializar sessão do navegador interno: {e}", exc_info=True)
            self.log_progress(f"Erro ao inicializar navegador interno: {str(e)}")
            return f"Erro ao inicializar a sessão do navegador: {str(e)}"

    async def ensure_initialized(self) -> None:
        page = self.get_page()
        browser = self.get_browser()
        if browser is None or page is None:
            headless = self._headless_var.get()
            run_id = self._run_id_var.get()
            logger.info(f"Inicializando navegador Playwright sob demanda (headless={headless})...")
            await self.init_session(headless=headless, run_id=run_id)

    async def close_session(self) -> str:
        logger.info("Fechando sessão do navegador interno...")
        page = self.get_page()
        browser = self.get_browser()
        playwright = self._playwright_var.get() or self._global_playwright

        if page and hasattr(page.context, "_active_downloads"):
            wait_time = 0
            while page.context._active_downloads > 0 and wait_time < 30:
                logger.info(f"Aguardando {page.context._active_downloads} downloads pendentes finalizarem...")
                await asyncio.sleep(1)
                wait_time += 1

        try:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
            logger.info("Sessão do navegador interno encerrada com sucesso.")
            return "Sucesso: Sessão do navegador fechada com sucesso."
        except Exception as e:
            logger.error(f"Erro ao fechar navegador: {e}")
            return f"Erro ao fechar a sessão do navegador: {str(e)}"
        finally:
            self._page_var.set(None)
            self._context_var.set(None)
            self._browser_var.set(None)
            self._playwright_var.set(None)
            self._global_page = None
            self._global_context = None
            self._global_browser = None
            self._global_playwright = None

    def get_downloaded_file(self) -> Optional[str]:
        page = self.get_page()
        if not page or not hasattr(page.context, "_downloaded_files"):
            return self._downloaded_file_var.get()

        files = page.context._downloaded_files
        if not files:
            return getattr(page.context, "_downloaded_file", None) or self._downloaded_file_var.get()

        if len(files) == 1:
            return files[0]

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        zip_filename = f"scraped_files_{timestamp}.zip"
        zip_path = os.path.join(DOWNLOADS_DIR, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in files:
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
        return zip_path
