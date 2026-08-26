# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER TOOLS & DRIVER FACADE (OOP ARCHITECTURE & ADK TOOLS)
  Fachada de ferramentas para agentes de IA e scripts, delegando para
  o provedor polimórfico ativo através de IBrowserDriver e BrowserDriverFactory.
=============================================================================
"""

import os
import sys
import json
import base64
import asyncio
import datetime
from typing import Optional, List, Dict, Any, Union

from libs.utils import setup_logger
from libs.browser.interfaces import IBrowserDriver
from libs.browser.driver_local import LocalBrowserDriver
from libs.browser.driver_remote import RemoteWSBrowserDriver
from libs.browser.factory import BrowserDriverFactory, BrowserDriverProxy
from libs.browser.client_internal import (
    init_browser_session,
    ensure_browser_initialized,
    close_browser_session,
    is_browser_session_active,
    get_active_page,
    get_active_context,
    get_active_browser,
    set_page,
    set_context,
    set_browser,
    handle_new_page,
    db_log_progress,
    db_register_download,
    save_global_download,
    get_downloaded_file,
    get_actions_log,
    reset_actions_log,
    execute_internal_code,
    execute_internal_action,
    get_internal_browser_tools,
    sanitize_folder_name,
    _actions_log_var,
    _run_id_var
)
from libs.browser.engine import BrowserTools, inspect_dom

logger = setup_logger("Browser.ToolsFacade")

# Instância padrão de Proxy para chamadas orientadas a objeto diretas
driver: IBrowserDriver = BrowserDriverProxy()
get_driver = BrowserDriverFactory.get_driver


# ==============================================================================
# AGENT TOOLS (FERRAMENTAS EXPOSTAS AO GOOGLE ADK / GEMINI / WEBPILOT)
# ==============================================================================

async def browser_goto(url: str, **kwargs) -> str:
    """Navega para a URL especificada no navegador."""
    return await driver.goto(url, **kwargs)


async def browser_click(selector: str, **kwargs) -> str:
    """Clica no elemento localizado pelo seletor CSS ou XPath."""
    return await driver.click(selector, **kwargs)


async def browser_type(selector: str, text: str, **kwargs) -> str:
    """Digita texto com delay simulando digitação humana."""
    return await driver.type(selector, text, **kwargs)


async def browser_fill(selector: str, text: str, **kwargs) -> str:
    """Preenche campo de formulário disparando eventos reativos de SPAs."""
    return await driver.fill(selector, text, **kwargs)


async def browser_press_key(key: str, selector: Optional[str] = None, **kwargs) -> str:
    """Pressiona uma tecla no teclado."""
    return await driver.press_key(key, selector=selector, **kwargs)


async def browser_wait_for_element(selector: str, timeout: int = 30000, **kwargs) -> str:
    """Aguarda um elemento ficar visível na página."""
    return await driver.wait_for(selector, timeout=timeout, **kwargs)


async def browser_wait(selector: str, timeout: int = 5000, state: str = "visible", **kwargs) -> str:
    """Aguarda um elemento com timeout em ms."""
    return await driver.wait(selector, timeout=timeout, state=state, **kwargs)


async def browser_get_value(selector: str, timeout: int = 5000, **kwargs) -> str:
    """Obtém o valor de um campo no DOM."""
    return await driver.get_value(selector, timeout=timeout, **kwargs)


async def browser_get_text(selector: str, timeout: int = 5000, **kwargs) -> str:
    """Obtém o texto visível de um elemento."""
    return await driver.get_text(selector, timeout=timeout, **kwargs)


async def browser_get_attribute(selector: str, attribute: str, timeout: int = 5000, **kwargs) -> Optional[str]:
    """Obtém um atributo HTML de um elemento."""
    return await driver.get_attribute(selector, attribute=attribute, timeout=timeout, **kwargs)


async def browser_inspect_page() -> str:
    """Inspeciona os elementos interativos, labels, iframes e texto visível da página ativa."""
    return await driver.inspect_dom()


async def browser_take_screenshot(
    filename: Optional[str] = None,
    selector: Optional[str] = None,
    full_page: bool = False
) -> str:
    """Captura screenshot da página ou de um elemento específico."""
    res = await driver.screenshot(filename=filename, selector=selector, full_page=full_page)
    if res.get("status") == "error":
        return f"Erro ao capturar screenshot: {res.get('error')}"
    return json.dumps(res, ensure_ascii=False)


async def browser_hover(selector: str, **kwargs) -> str:
    """Posiciona o cursor do mouse sobre um elemento."""
    return await driver.hover(selector, **kwargs)


async def browser_select_option(selector: str, value: str, **kwargs) -> str:
    """Seleciona uma opção em um elemento <select>."""
    return await driver.select_option(selector, value=value, **kwargs)


async def browser_scroll(direction: str = "down", amount: int = 500) -> str:
    """Rola a página para cima ou para baixo."""
    return await driver.scroll(direction=direction, amount=amount)


async def browser_back() -> str:
    """Retorna à página anterior no histórico de navegação."""
    return await driver.back()


async def browser_solve_captcha(selector: str, **kwargs) -> str:
    """Resolve captcha visual na página e retorna o texto decifrado."""
    try:
        captcha_text = await driver.solve_captcha(selector)
        return f"Sucesso: Captcha resolvido: '{captcha_text}'"
    except Exception as e:
        return f"Erro ao resolver captcha: {e}"


async def browser_extract_table(selector: str = "table", **kwargs) -> str:
    """Extrai tabela do DOM e retorna como JSON formatado."""
    try:
        data = await driver.extract_table(selector)
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao extrair tabela: {e}"


async def browser_list_tabs() -> str:
    """Lista as abas abertas no navegador."""
    tabs = await driver.list_tabs()
    return json.dumps(tabs, ensure_ascii=False)


async def browser_switch_to_tab(index: int) -> str:
    """Alterna para a aba no índice especificado."""
    return await driver.switch_tab(index)


# Alias para compatibilidade
run_code = execute_internal_code
