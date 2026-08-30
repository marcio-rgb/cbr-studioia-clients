# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - REMOTE WS BROWSER DRIVER (WEBSOCKET RPC EXECUTION)
  Implementação concreta de IBrowserDriver rodando no cliente Desktop do usuário
  através de canal RPC bidirecional WebSocket (porta 8384 / wss).
=============================================================================
"""

import os
import json
import base64
import logging
from typing import Optional, Dict, Any, List

from libs.browser.interfaces import IBrowserDriver
from libs.browser.ws_server import execute_remote_action
from libs.browser.client_internal import db_log_progress, _actions_log_var

logger = logging.getLogger("Browser.Driver.RemoteWS")


class RemoteWSBrowserDriver(IBrowserDriver):
    """
    Driver concreto que delega comandos via WebSocket para o cliente Desktop
    (Chromium Stealth ou Camoufox Anti-Detect).
    """

    def _log_action(self, action_data: Dict[str, Any]) -> None:
        actions_log = _actions_log_var.get()
        if actions_log is not None:
            actions_log.append(action_data)

    async def goto(self, url: str, **kwargs) -> str:
        logger.info(f"Roteando 'goto' via WebSocket. URL: {url}")
        db_log_progress("Navegando no cliente remoto...")
        res = await execute_remote_action("goto", {"url": url})
        self._log_action({"action": "goto", "url": url})
        title = res.get("title", "")
        return f"Sucesso: Navegado para {url}. Título da página: '{title}'"

    async def click(self, selector: str, force: bool = False, button: str = "left", click_count: int = 1, **kwargs) -> str:
        logger.info(f"Roteando 'click' via WebSocket. Seletor: {selector}")
        db_log_progress(f"Clicando em '{selector}' no cliente remoto...")
        await execute_remote_action("click", {
            "selector": selector,
            "force": force,
            "button": button,
            "click_count": click_count
        })
        self._log_action({"action": "click", "selector": selector})
        return f"Sucesso: Clicou no elemento '{selector}'."

    async def type(self, selector: str, text: str, delay: int = 35, **kwargs) -> str:
        logger.info(f"Roteando 'type' via WebSocket. Seletor: {selector}")
        db_log_progress(f"Digitando no cliente remoto...")
        await execute_remote_action("type", {
            "selector": selector,
            "text": text,
            "delay": delay
        })
        self._log_action({"action": "type", "selector": selector, "text": text})
        return f"Sucesso: Texto digitado em '{selector}'."

    async def fill(self, selector: str, text: str, **kwargs) -> str:
        logger.info(f"Roteando 'fill' via WebSocket. Seletor: {selector}")
        db_log_progress(f"Preenchendo '{selector}' no cliente remoto...")
        await execute_remote_action("fill", {
            "selector": selector,
            "text": text
        })
        self._log_action({"action": "type", "selector": selector, "text": text})
        return f"Sucesso: Campo '{selector}' preenchido."

    async def press_key(self, key: str, selector: Optional[str] = None, **kwargs) -> str:
        logger.info(f"Roteando 'press_key' via WebSocket. Tecla: {key}")
        await execute_remote_action("press_key", {
            "key": key,
            "selector": selector
        })
        self._log_action({"action": "press_key", "key": key, "selector": selector})
        return f"Sucesso: Tecla '{key}' pressionada."

    async def hover(self, selector: str, **kwargs) -> str:
        logger.info(f"Roteando 'hover' via WebSocket. Seletor: {selector}")
        await execute_remote_action("hover", {"selector": selector})
        self._log_action({"action": "hover", "selector": selector})
        return f"Sucesso: Mouse posicionado sobre '{selector}'."

    async def select_option(self, selector: str, value: str, **kwargs) -> str:
        logger.info(f"Roteando 'select' via WebSocket. Seletor: {selector}")
        await execute_remote_action("select", {
            "selector": selector,
            "value": value
        })
        self._log_action({"action": "select", "selector": selector, "value": value})
        return f"Sucesso: Opção '{value}' selecionada em '{selector}'."

    async def scroll(self, direction: str = "down", amount: int = 500, **kwargs) -> str:
        logger.info(f"Roteando 'scroll' via WebSocket. Direção: {direction}")
        await execute_remote_action("scroll", {
            "direction": direction,
            "amount": amount
        })
        self._log_action({"action": "scroll", "direction": direction, "amount": amount})
        return f"Sucesso: Rolou a página {amount}px para '{direction}'."

    async def wait_for(self, selector: str, timeout: int = 30000, state: str = "visible", **kwargs) -> str:
        logger.info(f"Roteando 'wait_for' via WebSocket. Seletor: {selector}")
        await execute_remote_action("wait_for", {
            "selector": selector,
            "timeout": timeout,
            "state": state
        })
        return f"Sucesso: Elemento '{selector}' localizado."

    async def back(self) -> str:
        logger.info("Roteando 'back' via WebSocket.")
        await execute_remote_action("back")
        return "Sucesso: Retornou para a página anterior."

    async def inspect_dom(self) -> str:
        logger.info("Roteando 'inspect' via WebSocket.")
        res = await execute_remote_action("inspect")
        return res.get("inspect_text", "PÁGINA ATUAL: (cliente remoto)")

    async def screenshot(
        self,
        filename: Optional[str] = None,
        selector: Optional[str] = None,
        full_page: bool = False
    ) -> Dict[str, Any]:
        logger.info("Roteando 'screenshot' via WebSocket.")
        safe_name = filename or "screenshot.png"
        res = await execute_remote_action("screenshot", {
            "filename": safe_name,
            "selector": selector,
            "full_page": full_page
        })

        b64_img = res.get("b64_image") if isinstance(res, dict) else None
        filepath = os.path.join("static/screenshots", safe_name)
        os.makedirs("static/screenshots", exist_ok=True)
        size_b = 0
        if b64_img:
            try:
                b_bytes = base64.b64decode(b64_img)
                size_b = len(b_bytes)
                with open(filepath, "wb") as f:
                    f.write(b_bytes)
            except Exception:
                pass

        return {
            "status": "success",
            "file": filepath,
            "url": f"/static/screenshots/{safe_name}",
            "b64_image": b64_img,
            "data_uri": f"data:image/png;base64,{b64_img}" if b64_img else None,
            "size_bytes": size_b,
            "selector": selector
        }

    async def solve_captcha(self, selector: str) -> str:
        logger.info(f"Roteando 'solve_captcha' via WebSocket. Seletor: {selector}")
        self._log_action({"action": "solve_captcha", "selector": selector})
        res = await execute_remote_action("solve_captcha", {"selector": selector})
        return res.get("captcha_text", "")

    async def extract_table(self, selector: str = "table") -> List[Dict[str, Any]]:
        logger.info(f"Roteando 'extract_table' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("extract_table", {"selector": selector})
        return res.get("data", [])

    async def download_file(self, selector: str) -> Dict[str, Any]:
        logger.info(f"Roteando 'download_file' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("download_file", {"selector": selector})
        return res

    async def get_value(self, selector: str, timeout: int = 5000, **kwargs) -> str:
        logger.info(f"Roteando 'get_value' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("get_value", {"selector": selector, "timeout": timeout})
        if res.get("status") == "error":
            raise RuntimeError(f"Erro ao obter valor de '{selector}': {res.get('error')}")
        return res.get("value", "")

    async def get_text(self, selector: str, timeout: int = 5000, **kwargs) -> str:
        logger.info(f"Roteando 'get_text' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("get_text", {"selector": selector, "timeout": timeout})
        if res.get("status") == "error":
            raise RuntimeError(f"Erro ao obter texto de '{selector}': {res.get('error')}")
        return res.get("text", "")

    async def get_attribute(self, selector: str, attribute: str, timeout: int = 5000, **kwargs) -> Optional[str]:
        logger.info(f"Roteando 'get_attribute' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("get_attribute", {"selector": selector, "attribute": attribute, "timeout": timeout})
        if res.get("status") == "error":
            raise RuntimeError(f"Erro ao obter atributo '{attribute}' de '{selector}': {res.get('error')}")
        return res.get("value")

    async def is_visible(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        logger.info(f"Roteando 'is_visible' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("is_visible", {"selector": selector, "timeout": timeout})
        return bool(res.get("visible", False))

    async def is_hidden(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        logger.info(f"Roteando 'is_hidden' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("is_hidden", {"selector": selector, "timeout": timeout})
        return bool(res.get("hidden", True))

    async def exists(self, selector: str, **kwargs) -> bool:
        logger.info(f"Roteando 'exists' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("exists", {"selector": selector})
        return bool(res.get("exists", False))

    async def is_checked(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        logger.info(f"Roteando 'is_checked' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("is_checked", {"selector": selector, "timeout": timeout})
        return bool(res.get("checked", False))

    async def is_disabled(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        logger.info(f"Roteando 'is_disabled' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("is_disabled", {"selector": selector, "timeout": timeout})
        return bool(res.get("disabled", False))

    async def is_enabled(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        logger.info(f"Roteando 'is_enabled' via WebSocket. Seletor: {selector}")
        res = await execute_remote_action("is_enabled", {"selector": selector, "timeout": timeout})
        return bool(res.get("enabled", False))

    async def evaluate(self, script: str) -> Any:
        logger.info("Roteando 'evaluate' via WebSocket.")
        res = await execute_remote_action("evaluate", {"script": script})
        return res.get("result")

    async def run_code(
        self,
        code: str,
        login_user: str = "",
        login_pass: str = "",
        params: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        logger.info("Roteando 'run_code' via WebSocket...")
        timeout = kwargs.get("timeout", 300.0)
        return await execute_remote_action("run_code", {
            "code": code,
            "login_user": login_user,
            "login_pass": login_pass,
            "params": params
        }, timeout=timeout)

    async def list_tabs(self) -> List[Dict[str, Any]]:
        res = await execute_remote_action("list_tabs")
        return res.get("tabs", [])

    async def switch_tab(self, index: int) -> str:
        await execute_remote_action("switch_tab", {"index": index})
        return f"Sucesso: Foco alterado para a aba {index} no cliente remoto."
