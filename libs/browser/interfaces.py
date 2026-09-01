# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR ESTÚDIO IA - BROWSER INTERFACES (OOP ABSTRACTION & CONTRACTS)
  Contratos formais abstratos (ABC) para:
  1. IBrowserDriver: Execução unificada de comandos do navegador.
  2. IBrowserSessionManager: Gerenciamento do ciclo de vida de sessões Playwright.
  3. IExecutionObserver: Observador para logging em tempo real e captura de downloads.
=============================================================================
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union


# =============================================================================
# 1. INTERFACE DO DRIVER DE NAVEGAÇÃO
# =============================================================================

class IBrowserDriver(ABC):
    """
    Interface abstrata que define o contrato unificado de execução
    de ações em navegadores no ecossistema CBR Estúdio IA.
    """

    @abstractmethod
    async def goto(self, url: str, **kwargs) -> str:
        """Navega para a URL especificada."""
        pass

    @abstractmethod
    async def click(self, selector: str, force: bool = False, button: str = "left", click_count: int = 1, **kwargs) -> str:
        """Clica em um elemento localizado pelo seletor CSS ou XPath."""
        pass

    @abstractmethod
    async def type(self, selector: str, text: str, delay: int = 35, **kwargs) -> str:
        """Digita texto com delay simulando digitação humana."""
        pass

    @abstractmethod
    async def fill(self, selector: str, text: str, **kwargs) -> str:
        """Preenche o valor de um campo disparando eventos reativos (input, change, blur)."""
        pass

    @abstractmethod
    async def press_key(self, key: str, selector: Optional[str] = None, **kwargs) -> str:
        """Pressiona uma tecla no teclado."""
        pass

    @abstractmethod
    async def hover(self, selector: str, **kwargs) -> str:
        """Move o cursor do mouse sobre o elemento."""
        pass

    @abstractmethod
    async def select_option(self, selector: str, value: str, **kwargs) -> str:
        """Seleciona uma opção em um elemento <select>."""
        pass

    @abstractmethod
    async def scroll(self, direction: str = "down", amount: int = 500, **kwargs) -> str:
        """Rola a página em pixels na direção indicada."""
        pass

    @abstractmethod
    async def wait_for(self, selector: str, timeout: int = 30000, state: str = "visible", **kwargs) -> str:
        """Aguarda um elemento atingir um estado específico no DOM."""
        pass

    async def wait(self, selector: str, state: str = "visible", timeout: int = 5000, **kwargs) -> str:
        """Aguarda um elemento atingir um estado específico no DOM (timeout em ms)."""
        return await self.wait_for(selector, timeout=timeout, state=state, **kwargs)

    @abstractmethod
    async def get_value(self, selector: str, timeout: int = 5000, **kwargs) -> str:
        """Obtém o valor de um campo de formulário no DOM."""
        pass

    @abstractmethod
    async def get_text(self, selector: str, timeout: int = 5000, **kwargs) -> str:
        """Obtém o texto visível de um elemento no DOM."""
        pass

    @abstractmethod
    async def get_attribute(self, selector: str, attribute: str, timeout: int = 5000, **kwargs) -> Optional[str]:
        """Obtém o valor de um atributo HTML de um elemento."""
        pass

    @abstractmethod
    async def is_visible(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        """Verifica se um elemento está visível no DOM."""
        pass

    @abstractmethod
    async def is_hidden(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        """Verifica se um elemento está oculto no DOM."""
        pass

    @abstractmethod
    async def exists(self, selector: str, **kwargs) -> bool:
        """Verifica se um elemento existe no DOM."""
        pass

    @abstractmethod
    async def is_checked(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        """Verifica se um checkbox ou radio está marcado no DOM."""
        pass

    @abstractmethod
    async def is_disabled(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        """Verifica se um elemento está desabilitado no DOM."""
        pass

    @abstractmethod
    async def is_enabled(self, selector: str, timeout: int = 5000, **kwargs) -> bool:
        """Verifica se um elemento está habilitado no DOM."""
        pass

    @abstractmethod
    async def back(self) -> str:
        """Retorna à página anterior no histórico de navegação."""
        pass

    @abstractmethod
    async def inspect_dom(self) -> str:
        """Inspeciona os elementos interativos, iframes e conteúdo visível da página ativa."""
        pass

    @abstractmethod
    async def screenshot(
        self,
        filename: Optional[str] = None,
        selector: Optional[str] = None,
        full_page: bool = False
    ) -> Dict[str, Any]:
        """Captura screenshot da página ou de um elemento específico."""
        pass

    @abstractmethod
    async def solve_captcha(self, selector: str) -> str:
        """Resolve automaticamente captcha de imagem utilizando OCR/Gemini Vision."""
        pass

    @abstractmethod
    async def extract_table(self, selector: str = "table") -> List[Dict[str, Any]]:
        """Extrai dados tabulares e converte em lista de dicionários Python."""
        pass

    @abstractmethod
    async def download_file(self, selector: str) -> Dict[str, Any]:
        """Clica em um elemento e aguarda o download do arquivo."""
        pass

    @abstractmethod
    async def evaluate(self, script: str) -> Any:
        """Executa uma expressão ou script JavaScript no contexto da página."""
        pass

    @abstractmethod
    async def run_code(
        self,
        code: str,
        login_user: str = "",
        login_pass: str = "",
        params: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Executa um script ou snippet Python Playwright completo."""
        pass

    @abstractmethod
    async def list_tabs(self) -> List[Dict[str, Any]]:
        """Lista as abas abertas no navegador."""
        pass

    @abstractmethod
    async def switch_tab(self, index: int) -> str:
        """Alterna para a aba no índice especificado."""
        pass


# =============================================================================
# 2. INTERFACE DO GERENCIADOR DE SESSÃO DO NAVEGADOR
# =============================================================================

class IBrowserSessionManager(ABC):
    """
    Interface abstrata que define o ciclo de vida e controle de instâncias
    do Playwright (Browser, Context, Page).
    """

    @abstractmethod
    async def init_session(
        self,
        engine: Optional[str] = None,
        headless: bool = True,
        proxy_config: Optional[Dict[str, str]] = None,
        run_id: Optional[int] = None,
        agent_name: Optional[str] = None
    ) -> str:
        """Inicializa uma nova sessão assíncrona do navegador Playwright."""
        pass

    @abstractmethod
    async def ensure_initialized(self) -> None:
        """Garante que uma sessão ativa e válida está pronta para receber comandos."""
        pass

    @abstractmethod
    async def close_session(self) -> str:
        """Fecha a sessão ativa e libera os recursos do navegador."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Verifica se há uma sessão de navegador ativa no momento."""
        pass

    @abstractmethod
    def get_page(self) -> Optional[Any]:
        """Retorna a página (Page) ativa da sessão."""
        pass

    @abstractmethod
    def get_context(self) -> Optional[Any]:
        """Retorna o contexto (BrowserContext) ativo da sessão."""
        pass

    @abstractmethod
    def get_browser(self) -> Optional[Any]:
        """Retorna a instância do navegador (Browser) ativa."""
        pass


# =============================================================================
# 3. INTERFACE DE OBSERVADORES DE EXECUÇÃO (LOGS E DOWNLOADS)
# =============================================================================

class IExecutionObserver(ABC):
    """
    Interface abstrata (Padrão Observer) para desacoplamento de
    registro de progresso em tempo real e notificações de downloads.
    """

    @abstractmethod
    def log_progress(self, message: str, run_id: Optional[int] = None) -> None:
        """Registra uma mensagem de progresso da execução em tempo real."""
        pass

    @abstractmethod
    def register_download(self, filename: str, filepath: str, run_id: Optional[int] = None) -> None:
        """Registra a conclusão de download de um arquivo gerado durante a execução."""
        pass
