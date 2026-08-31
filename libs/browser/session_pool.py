# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER SESSION POOL (MULTI-TENANT CONTEXT ISOLATION)
  Gerenciador de pool de sessões do Playwright com isolamento por source_id.
  Compartilha 1 processo Chromium do motor principal e aloca BrowserContexts
  leves e independentes para cada WebPilot, com auto-cleanup por inatividade.
=============================================================================
"""

import os
import time
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

from libs.utils import setup_logger
from libs.browser.launcher import init_browser_engine

logger = setup_logger("Browser.SessionPool")

# Tempo limite de inatividade para auto-cleanup da sessão (15 minutos)
IDLE_SESSION_TIMEOUT_SECONDS = 15 * 60


class SessionContextEntry:
    """Representa uma sessão ativa isolada para um WebPilot específico."""

    def __init__(self, source_id: int, context: BrowserContext, page: Page):
        self.source_id: int = source_id
        self.context: BrowserContext = context
        self.page: Page = page
        self.last_activity: float = time.time()
        self.lock: asyncio.Lock = asyncio.Lock()

    def touch(self) -> None:
        """Atualiza o timestamp de atividade da sessão."""
        self.last_activity = time.time()

    def is_idle(self, timeout_seconds: float = IDLE_SESSION_TIMEOUT_SECONDS) -> bool:
        """Verifica se a sessão ultrapassou o tempo limite de inatividade."""
        return (time.time() - self.last_activity) > timeout_seconds

    async def close(self) -> None:
        """Encerra com segurança a página e o contexto."""
        try:
            if not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass
        try:
            await self.context.close()
        except Exception:
            pass


class BrowserSessionPool:
    """
    Pool multi-tenant de sessões do Playwright.
    Garante que cada automação WebPilot (source_id) possua seu próprio BrowserContext
    isolado (cookies, localStorage, histórico, abas) sobre um único engine do Chromium.
    """

    _instance: Optional["BrowserSessionPool"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserSessionPool, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._sessions: Dict[int, SessionContextEntry] = {}
        self._pool_lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def _ensure_engine(
        self,
        engine: Optional[str] = None,
        headless: bool = True,
        proxy_config: Optional[Dict[str, str]] = None
    ) -> Browser:
        """Garante que a instância compartilhada do Playwright/Chromium está ativa."""
        if self._browser and self._browser.is_connected():
            return self._browser

        if not self._playwright:
            self._playwright = await async_playwright().start()

        browser, _, _ = await init_browser_engine(
            self._playwright,
            engine=engine,
            headless=headless,
            proxy_config=proxy_config
        )
        self._browser = browser
        
        # Inicia a tarefa de monitoramento de inatividade se não estiver rodando
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._idle_cleanup_loop())

        return self._browser

    async def get_or_create(
        self,
        source_id: Optional[int] = None,
        headless: bool = True,
        proxy_config: Optional[Dict[str, str]] = None,
        engine: Optional[str] = None
    ) -> Tuple[BrowserContext, Page]:
        """
        Obtém a sessão existente para o source_id ou cria um novo BrowserContext isolado.
        """
        sid = int(source_id) if source_id is not None else 0

        async with self._pool_lock:
            entry = self._sessions.get(sid)
            if entry and not entry.page.is_closed():
                entry.touch()
                return entry.context, entry.page

            # Se a sessão existia mas a página fechou, limpa a entrada anterior
            if entry:
                await entry.close()
                self._sessions.pop(sid, None)

            # Inicializa o browser principal compartilhado
            browser = await self._ensure_engine(
                engine=engine,
                headless=headless,
                proxy_config=proxy_config
            )

            # Cria BrowserContext dedicado para este source_id
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            context_kwargs = {
                "user_agent": ua,
                "viewport": {"width": 1280, "height": 800},
                "locale": "pt-BR",
                "timezone_id": "America/Sao_Paulo",
                "accept_downloads": True
            }
            if proxy_config:
                context_kwargs["proxy"] = proxy_config

            context = await browser.new_context(**context_kwargs)
            
            # Injeta script anti-detecção stealth
            stealth_js = """
            (() => {
                try {
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
                    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                } catch (e) {}
            })();
            """
            await context.add_init_script(stealth_js)
            page = await context.new_page()

            new_entry = SessionContextEntry(sid, context, page)
            self._sessions[sid] = new_entry
            logger.info(f"🟢 Nova sessão Playwright isolada criada para source_id #{sid}")
            return context, page

    def get_page(self, source_id: Optional[int] = None) -> Optional[Page]:
        """Retorna a Page ativa para o source_id se existir e estiver aberta."""
        sid = int(source_id) if source_id is not None else 0
        entry = self._sessions.get(sid)
        if entry and not entry.page.is_closed():
            entry.touch()
            return entry.page
        return None

    def get_context(self, source_id: Optional[int] = None) -> Optional[BrowserContext]:
        """Retorna o BrowserContext ativo para o source_id se existir."""
        sid = int(source_id) if source_id is not None else 0
        entry = self._sessions.get(sid)
        if entry:
            entry.touch()
            return entry.context
        return None

    def get_browser(self) -> Optional[Browser]:
        """Retorna a instância compartilhada do Browser."""
        return self._browser

    def get_playwright(self) -> Optional[Playwright]:
        """Retorna a instância compartilhada do Playwright."""
        return self._playwright

    async def ensure_page_initialized(
        self,
        source_id: Optional[Union[int, str]] = None,
        headless: bool = True,
        proxy_config: Optional[Dict[str, str]] = None
    ) -> Page:
        """Garante que a página do source_id está ativa e inicializada."""
        _, page = await self.get_or_create(
            source_id=source_id,
            headless=headless,
            proxy_config=proxy_config
        )
        return page

    def is_active(self, source_id: Optional[Union[int, str]] = None) -> bool:
        """Verifica se há uma sessão ativa para o source_id especificado."""
        page = self.get_page(source_id)
        return page is not None and not page.is_closed()

    async def start_interactive_session(
        self,
        source_id: Optional[Union[int, str]] = None,
        url_base: str = "",
        headless: bool = True,
        proxy_config: Optional[Dict[str, str]] = None
    ) -> Tuple[BrowserContext, Page]:
        """Inicia explicitamente uma sessão interativa para desenvolvimento de passos."""
        sid = int(source_id) if source_id is not None else 0
        context, page = await self.get_or_create(
            source_id=sid,
            headless=headless,
            proxy_config=proxy_config
        )
        if url_base and url_base.strip() and (not getattr(page, "url", "") or page.url == "about:blank"):
            try:
                await page.goto(url_base.strip(), wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"Aviso ao navegar na inicialização da sessão #{sid}: {e}")
        return context, page

    def get_session_info(self, source_id: Optional[Union[int, str]] = None) -> dict:
        """Retorna informações detalhadas de status e telemetria da sessão interativa."""
        sid = int(source_id) if source_id is not None else 0
        entry = self._sessions.get(sid)
        if not entry or entry.page.is_closed():
            return {
                "source_id": sid,
                "active": False,
                "url": "",
                "idle_seconds": 0,
                "status": "CLOSED"
            }
        
        idle = round(time.time() - entry.last_activity, 1)
        url = getattr(entry.page, "url", "")
        return {
            "source_id": sid,
            "active": True,
            "url": url,
            "idle_seconds": idle,
            "status": "ACTIVE"
        }

    async def close_session(self, source_id: Optional[int] = None) -> bool:
        """Encerra a sessão específica de um source_id liberando seus recursos."""
        sid = int(source_id) if source_id is not None else 0
        async with self._pool_lock:
            entry = self._sessions.pop(sid, None)
            if entry:
                await entry.close()
                logger.info(f"🔴 Sessão do source_id #{sid} encerrada com sucesso.")
                return True
            return False

    close_interactive_session = close_session

    async def close_all(self) -> None:
        """Encerra todas as sessões ativas e desliga o navegador."""
        async with self._pool_lock:
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                self._cleanup_task = None

            for sid, entry in list(self._sessions.items()):
                await entry.close()
            self._sessions.clear()

            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None

            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            logger.info("🔴 Todas as sessões do BrowserSessionPool foram encerradas.")

    async def _idle_cleanup_loop(self) -> None:
        """Worker em segundo plano para limpeza de sessões ociosas."""
        try:
            while True:
                await asyncio.sleep(60)  # Verifica a cada 1 minuto
                async with self._pool_lock:
                    expired_sids = [
                        sid for sid, entry in self._sessions.items()
                        if entry.is_idle()
                    ]
                    for sid in expired_sids:
                        entry = self._sessions.pop(sid, None)
                        if entry:
                            logger.info(f"⏱️ Limpando sessão ociosa por inatividade (source_id #{sid})")
                            await entry.close()

                    # Se não houver mais nenhuma sessão ativa e ninguém usou recentemente, fecha o browser
                    if not self._sessions and self._browser:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Erro no loop de limpeza de sessões: {e}")


# Instância Singleton global do pool de sessões
session_pool = BrowserSessionPool()
