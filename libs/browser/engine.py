# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - UNIFIED PLAYWRIGHT BROWSER ENGINE & TOOLS SDK
  Motor central e agnóstico de automação Playwright para modo Visual e Interno.
  Fornece a classe BrowserTools como SDK de alto nível para scripts e agentes,
  garantindo 100% de paridade em resiliência, seletores, SPAs, iframes e captchas.
=============================================================================
"""

import logging
from libs.browser.tools_base import BrowserToolsBase
from libs.browser.tools_interactions import BrowserToolsInteractionsMixin
from libs.browser.tools_extractors import BrowserToolsExtractorsMixin

from libs.browser.dom_inspector import inspect_dom
from libs.browser.captcha import CaptchaSolver, solve_captcha_image
from libs.browser.sandbox import execute_code_sandbox, TeeStream
from libs.browser.action_dispatcher import execute_browser_action
from libs.browser.launcher import init_browser_engine

logger = logging.getLogger("Browser.Engine")


class BrowserTools(BrowserToolsInteractionsMixin, BrowserToolsExtractorsMixin, BrowserToolsBase):
    """
    SDK de alto nível e agnóstico de automação web.
    Fornece métodos intuitivos, resilientes e unificados para scripts e agentes,
    encapsulando reatividade de SPAs, esperas inteligentes, extração de tabelas,
    resolução de captchas e gestão de parâmetros de entrada/saída.
    """
    pass


# =============================================================================
# EXPORTAÇÕES PÚBLICAS (100% RETROCOMPATIBILIDADE)
# =============================================================================

__all__ = [
    "BrowserTools",
    "BrowserToolsBase",
    "BrowserToolsInteractionsMixin",
    "BrowserToolsExtractorsMixin",
    "inspect_dom",
    "CaptchaSolver",
    "solve_captcha_image",
    "execute_code_sandbox",
    "TeeStream",
    "execute_browser_action",
    "init_browser_engine",
]
