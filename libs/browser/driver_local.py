# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - LOCAL BROWSER DRIVER (HEADLESS / INTERNAL CONTAINER EXECUTION)
  Implementação concreta de IBrowserDriver rodando diretamente no Playwright
  local do servidor/container com suporte a isolamento de contexto e downloads.
=============================================================================
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List

from libs.browser.interfaces import IBrowserDriver
from libs.browser.client_internal import (
    ensure_browser_initialized,
    get_active_page,
    get_internal_browser_tools,
    execute_internal_action,
    execute_internal_code,
    db_log_progress
)
from libs.browser.engine import inspect_dom

logger = logging.getLogger("Browser.Driver.Local")


class LocalBrowserDriver(IBrowserDriver):
    """
    Driver concreto que executa comandos no navegador Playwright interno
    do processo/container do servidor.
    """

    async def goto(self, url: str, **kwargs) -> str:
        res = await execute_internal_action("goto", {"url": url})
        if res.get("status") == "error":
            return f"Erro ao navegar: {res.get('error')}"
        return f"Sucesso: Navegado para {url}. Título: '{res.get('title', '')}'"

    async def click(self, selector: str, force: bool = False, button: str = "left", click_count: int = 1, **kwargs) -> str:
        res = await execute_internal_action("click", {
            "selector": selector,
            "force": force,
            "button": button,
            "click_count": click_count
        })
        if res.get("status") == "error":
            return f"Erro ao clicar em '{selector}': {res.get('error')}"
        return f"Sucesso: Clicou no elemento '{selector}'."

    async def type(self, selector: str, text: str, delay: int = 35, **kwargs) -> str:
        res = await execute_internal_action("type", {
            "selector": selector,
            "text": text,
            "delay": delay
        })
        if res.get("status") == "error":
            return f"Erro ao digitar em '{selector}': {res.get('error')}"
        return f"Sucesso: Texto digitado em '{selector}'."

    async def fill(self, selector: str, text: str, **kwargs) -> str:
        res = await execute_internal_action("fill", {
            "selector": selector,
            "text": text
        })
        if res.get("status") == "error":
            return f"Erro ao preencher '{selector}': {res.get('error')}"
        return f"Sucesso: Campo '{selector}' preenchido."

    async def press_key(self, key: str, selector: Optional[str] = None, **kwargs) -> str:
        res = await execute_internal_action("press_key", {
            "key": key,
            "selector": selector
        })
        if res.get("status") == "error":
            return f"Erro ao pressionar '{key}': {res.get('error')}"
        return f"Sucesso: Tecla '{key}' pressionada."

    async def hover(self, selector: str, **kwargs) -> str:
        res = await execute_internal_action("hover", {"selector": selector})
        if res.get("status") == "error":
            return f"Erro ao posicionar mouse sobre '{selector}': {res.get('error')}"
        return f"Sucesso: Mouse posicionado sobre '{selector}'."

    async def select_option(self, selector: str, value: str, **kwargs) -> str:
        res = await execute_internal_action("select", {
            "selector": selector,
            "value": value
        })
        if res.get("status") == "error":
            return f"Erro ao selecionar '{value}' em '{selector}': {res.get('error')}"
        return f"Sucesso: Opção '{value}' selecionada em '{selector}'."

    async def scroll(self, direction: str = "down", amount: int = 500, **kwargs) -> str:
        res = await execute_internal_action("scroll", {
            "direction": direction,
            "amount": amount
        })
        if res.get("status") == "error":
            return f"Erro ao rolar página: {res.get('error')}"
        return f"Sucesso: Rolou a página {amount}px para '{direction}'."

    async def wait_for(self, selector: str, timeout: int = 30000, state: str = "visible", **kwargs) -> str:
        res = await execute_internal_action("wait_for", {
            "selector": selector,
            "timeout": timeout,
            "state": state
        })
        if res.get("status") == "error":
            return f"Elemento '{selector}' não apareceu: {res.get('error')}"
        return f"Sucesso: Elemento '{selector}' localizado."

    async def back(self) -> str:
        res = await execute_internal_action("back")
        if res.get("status") == "error":
            return f"Erro ao voltar página: {res.get('error')}"
        return "Sucesso: Retornou para a página anterior."

    async def inspect_dom(self) -> str:
        await ensure_browser_initialized()
        page = get_active_page()
        if not page:
            return "Erro: Navegador interno não inicializado."
        return await inspect_dom(page)

    async def screenshot(
        self,
        filename: Optional[str] = None,
        selector: Optional[str] = None,
        full_page: bool = False
    ) -> Dict[str, Any]:
        import datetime
        safe_name = filename or f"screenshot_{int(datetime.datetime.now().timestamp())}.png"
        res = await execute_internal_action("screenshot", {
            "filename": safe_name,
            "selector": selector,
            "full_page": full_page
        })
        return res

    async def solve_captcha(self, selector: str) -> str:
        res = await execute_internal_action("solve_captcha", {"selector": selector})
        if res.get("status") == "error":
            raise RuntimeError(f"Erro ao resolver captcha: {res.get('error')}")
        return res.get("captcha_text", "")

    async def extract_table(self, selector: str = "table") -> List[Dict[str, Any]]:
        res = await execute_internal_action("extract_table", {"selector": selector})
        if res.get("status") == "error":
            raise RuntimeError(f"Erro ao extrair tabela: {res.get('error')}")
        return res.get("data", [])

    async def download_file(self, selector: str) -> Dict[str, Any]:
        return await execute_internal_action("download_file", {"selector": selector})

    async def get_value(self, selector: str, timeout: int = 5000, **kwargs) -> str:
        res = await execute_internal_action("get_value", {"selector": selector, "timeout": timeout})
        if res.get("status") == "error":
            raise RuntimeError(f"Erro ao obter valor de '{selector}': {res.get('error')}")
        return res.get("value", "")

    async def get_text(self, selector: str, timeout: int = 5000, **kwargs) -> str:
        res = await execute_internal_action("get_text", {"selector": selector, "timeout": timeout})
        if res.get("status") == "error":
            raise RuntimeError(f"Erro ao obter texto de '{selector}': {res.get('error')}")
        return res.get("text", "")

    async def get_attribute(self, selector: str, attribute: str, timeout: int = 5000, **kwargs) -> Optional[str]:
        res = await execute_internal_action("get_attribute", {"selector": selector, "attribute": attribute, "timeout": timeout})
        if res.get("status") == "error":
            raise RuntimeError(f"Erro ao obter atributo '{attribute}' de '{selector}': {res.get('error')}")
        return res.get("value")

    async def is_visible(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        res = await execute_internal_action("is_visible", {"selector": selector, "timeout": timeout})
        return bool(res.get("visible", False))

    async def is_hidden(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        res = await execute_internal_action("is_hidden", {"selector": selector, "timeout": timeout})
        return bool(res.get("hidden", True))

    async def exists(self, selector: str, **kwargs) -> bool:
        res = await execute_internal_action("exists", {"selector": selector})
        return bool(res.get("exists", False))

    async def is_checked(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        res = await execute_internal_action("is_checked", {"selector": selector, "timeout": timeout})
        return bool(res.get("checked", False))

    async def is_disabled(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        res = await execute_internal_action("is_disabled", {"selector": selector, "timeout": timeout})
        return bool(res.get("disabled", False))

    async def is_enabled(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        res = await execute_internal_action("is_enabled", {"selector": selector, "timeout": timeout})
        return bool(res.get("enabled", False))

    async def evaluate(self, script: str) -> Any:
        res = await execute_internal_action("evaluate", {"script": script})
        return res.get("result")

    async def run_code(
        self,
        code: str,
        login_user: str = "",
        login_pass: str = "",
        params: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        return await execute_internal_code(
            code=code,
            login_user=login_user,
            login_pass=login_pass,
            params=params,
            **kwargs
        )

    async def list_tabs(self) -> List[Dict[str, Any]]:
        await ensure_browser_initialized()
        tools = get_internal_browser_tools()
        return await tools.list_tabs()

    async def switch_tab(self, index: int) -> str:
        await ensure_browser_initialized()
        tools = get_internal_browser_tools()
        try:
            await tools.switch_tab(index)
            return f"Sucesso: Foco alterado para a aba {index}."
        except Exception as e:
            return f"Erro ao alternar aba: {e}"
