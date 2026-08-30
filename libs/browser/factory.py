# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER DRIVER FACTORY & PROXY (POLYMORPHIC RESOLVER)
  Fábrica e Proxy de resolução dinâmica entre Local e Remoto em runtime.
=============================================================================
"""

import logging
from typing import Optional, Dict, Any, List

from libs.browser.interfaces import IBrowserDriver
from libs.browser.driver_local import LocalBrowserDriver
from libs.browser.driver_remote import RemoteWSBrowserDriver
from libs.browser.ws_server import is_client_connected

logger = logging.getLogger("Browser.Factory")


class BrowserDriverFactory:
    """
    Fábrica responsável por instanciar e resolver o driver apropriado
    com base no estado da conexão WebSocket em tempo de execução.
    """

    _local_driver: Optional[LocalBrowserDriver] = None
    _remote_driver: Optional[RemoteWSBrowserDriver] = None

    @classmethod
    def get_local_driver(cls) -> LocalBrowserDriver:
        if cls._local_driver is None:
            cls._local_driver = LocalBrowserDriver()
        return cls._local_driver

    @classmethod
    def get_remote_driver(cls) -> RemoteWSBrowserDriver:
        if cls._remote_driver is None:
            cls._remote_driver = RemoteWSBrowserDriver()
        return cls._remote_driver

    @classmethod
    def get_driver(cls) -> IBrowserDriver:
        """
        Retorna dinamicamente o driver ativo:
        - Se houver cliente Desktop conectado via WS -> RemoteWSBrowserDriver
        - Caso contrário -> LocalBrowserDriver (Headless / Container)
        """
        if is_client_connected():
            return cls.get_remote_driver()
        return cls.get_local_driver()


class BrowserDriverProxy(IBrowserDriver):
    """
    Proxy transparente que implementa IBrowserDriver e delega
    todas as operações dinamicamente para o driver ativo retornado pela fábrica.
    """

    def _active(self) -> IBrowserDriver:
        return BrowserDriverFactory.get_driver()

    async def goto(self, url: str, **kwargs) -> str:
        return await self._active().goto(url, **kwargs)

    async def click(self, selector: str, force: bool = False, button: str = "left", click_count: int = 1, **kwargs) -> str:
        return await self._active().click(selector, force=force, button=button, click_count=click_count, **kwargs)

    async def type(self, selector: str, text: str, delay: int = 35, **kwargs) -> str:
        return await self._active().type(selector, text, delay=delay, **kwargs)

    async def fill(self, selector: str, text: str, **kwargs) -> str:
        return await self._active().fill(selector, text, **kwargs)

    async def press_key(self, key: str, selector: Optional[str] = None, **kwargs) -> str:
        return await self._active().press_key(key, selector=selector, **kwargs)

    async def hover(self, selector: str, **kwargs) -> str:
        return await self._active().hover(selector, **kwargs)

    async def select_option(self, selector: str, value: str, **kwargs) -> str:
        return await self._active().select_option(selector, value=value, **kwargs)

    async def scroll(self, direction: str = "down", amount: int = 500, **kwargs) -> str:
        return await self._active().scroll(direction=direction, amount=amount, **kwargs)

    async def wait_for(self, selector: str, timeout: int = 30000, state: str = "visible", **kwargs) -> str:
        return await self._active().wait_for(selector, timeout=timeout, state=state, **kwargs)

    async def wait(self, selector: str, state: str = "visible", timeout: int = 5000, **kwargs) -> str:
        return await self._active().wait(selector, state=state, timeout=timeout, **kwargs)

    async def get_value(self, selector: str, timeout: int = 5000, **kwargs) -> str:
        return await self._active().get_value(selector, timeout=timeout, **kwargs)

    async def get_text(self, selector: str, timeout: int = 5000, **kwargs) -> str:
        return await self._active().get_text(selector, timeout=timeout, **kwargs)

    async def get_attribute(self, selector: str, attribute: str, timeout: int = 5000, **kwargs) -> Optional[str]:
        return await self._active().get_attribute(selector, attribute=attribute, timeout=timeout, **kwargs)

    async def is_visible(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        return await self._active().is_visible(selector, timeout=timeout, **kwargs)

    async def is_hidden(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        return await self._active().is_hidden(selector, timeout=timeout, **kwargs)

    async def exists(self, selector: str, **kwargs) -> bool:
        return await self._active().exists(selector, **kwargs)

    async def is_checked(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        return await self._active().is_checked(selector, timeout=timeout, **kwargs)

    async def is_disabled(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        return await self._active().is_disabled(selector, timeout=timeout, **kwargs)

    async def is_enabled(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        return await self._active().is_enabled(selector, timeout=timeout, **kwargs)

    async def back(self) -> str:
        return await self._active().back()

    async def inspect_dom(self) -> str:
        return await self._active().inspect_dom()

    async def screenshot(
        self,
        filename: Optional[str] = None,
        selector: Optional[str] = None,
        full_page: bool = False
    ) -> Dict[str, Any]:
        return await self._active().screenshot(filename=filename, selector=selector, full_page=full_page)

    async def solve_captcha(self, selector: str) -> str:
        return await self._active().solve_captcha(selector)

    async def extract_table(self, selector: str = "table") -> List[Dict[str, Any]]:
        return await self._active().extract_table(selector)

    async def download_file(self, selector: str) -> Dict[str, Any]:
        return await self._active().download_file(selector)

    async def evaluate(self, script: str) -> Any:
        return await self._active().evaluate(script)

    async def run_code(
        self,
        code: str,
        login_user: str = "",
        login_pass: str = "",
        params: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        return await self._active().run_code(
            code=code,
            login_user=login_user,
            login_pass=login_pass,
            params=params,
            **kwargs
        )

    async def list_tabs(self) -> List[Dict[str, Any]]:
        return await self._active().list_tabs()

    async def switch_tab(self, index: int) -> str:
        return await self._active().switch_tab(index)
