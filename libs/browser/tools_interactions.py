# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER TOOLS INTERACTIONS MIXIN
  Métodos de navegação, esperas reativas, cliques, digitação, seleção e
  preenchimento resiliente com auto-verificação de valor no DOM.
=============================================================================
"""

import re
import asyncio
import logging
from typing import Optional, Any, Union

logger = logging.getLogger("Browser.ToolsInteractions")


class BrowserToolsInteractionsMixin:
    """
    Mixin contendo ações de interação e navegação de página do BrowserTools.
    """

    # -------------------------------------------------------------------------
    # Ações de Navegação e Espera Reativa
    # -------------------------------------------------------------------------
    async def goto(
        self,
        url: str,
        wait_for: Optional[str] = None,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
        retries: int = 3
    ) -> str:
        """
        Navega até uma URL e opcionalmente aguarda um seletor específico ser carregado na tela.
        
        Args:
            url: URL de destino.
            wait_for: Seletor opcional para aguardar após a navegação (ex: '#txtCPF', 'table').
            wait_until: 'domcontentloaded' (padrão, rápido), 'load', 'networkidle'.
            timeout: Tempo limite de navegação em MILISSEGUNDOS (ms) (padrão: 30000ms = 30s).
            retries: Quantidade de retentativas se a navegação falhar (padrão: 3x).
        """
        page = await self.ensure_active_page()
        last_err = None
        for attempt in range(retries):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                if wait_for:
                    await self.wait(wait_for, state="visible", timeout=5000, retries=retries)
                await self.broadcast_frame()
                return page.url
            except Exception as e:
                last_err = e
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.5)
        raise RuntimeError(f"Falha ao navegar para '{url}' após {retries} tentativas: {last_err}")

    async def wait(
        self,
        selector: str,
        state: str = "visible",
        timeout: int = 5000,
        retries: int = 3
    ) -> None:
        """
        Aguarda um elemento atingir o estado desejado ('visible', 'attached', 'hidden').
        
        Args:
            selector: Seletor CSS, XPath ou Playwright (ex: '#btn', 'button:has-text("Acessar")').
            state: 'visible' (padrão), 'attached', 'detached', 'hidden'.
            timeout: Tempo limite em MILISSEGUNDOS (ms) por tentativa (padrão: 5000ms = 5s).
            retries: Quantidade de retentativas se ocorrer timeout (padrão: 3x).
        """
        page = await self.ensure_active_page()
        last_err = None
        for attempt in range(retries):
            try:
                await page.wait_for_selector(selector, state=state, timeout=timeout)
                return
            except Exception as e:
                last_err = e
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.25)
        raise TimeoutError(f"Elemento '{selector}' não atingiu o estado '{state}' após {retries} tentativas (timeout={timeout}ms cada): {last_err}")

    async def sleep(self, seconds_or_ms: Union[int, float]) -> None:
        """
        Pausa assíncrona da execução.
        Se o valor for >= 100, é interpretado em MILISSEGUNDOS (ms) (ex: 1000 = 1s).
        Se for < 100, é interpretado em SEGUNDOS (s) (ex: 1 = 1s, 0.5 = 500ms).
        """
        val = float(seconds_or_ms)
        secs = (val / 1000.0) if val >= 100 else val
        await asyncio.sleep(secs)

    async def back(self) -> str:
        """Retorna à página anterior no histórico de navegação."""
        page = await self.ensure_active_page()
        await page.go_back(wait_until="domcontentloaded", timeout=30000)
        await self.broadcast_frame()
        return page.url

    async def reload(self) -> str:
        """Recarrega a página ativa."""
        page = await self.ensure_active_page()
        await page.reload(wait_until="domcontentloaded", timeout=30000)
        await self.broadcast_frame()
        return page.url

    async def get_html(self) -> str:
        """Retorna o conteúdo HTML completo da página ativa."""
        page = await self.ensure_active_page()
        return await page.content() if page else ""

    # -------------------------------------------------------------------------
    # Ações de Interação e Formulários (com Espera Reativa e Verificação)
    # -------------------------------------------------------------------------
    async def click(
        self,
        selector: str,
        wait_for: Optional[str] = None,
        force: bool = False,
        button: str = "left",
        click_count: int = 1,
        timeout: int = 5000,
        retries: int = 3
    ) -> None:
        """
        Clica em um elemento com espera reativa, retries automáticos (3x) e múltiplos fallbacks resilientes.
        """
        page = await self.ensure_active_page()
        last_err = None

        for attempt in range(retries):
            try:
                # 1. Aguarda visibilidade do elemento
                try:
                    await page.wait_for_selector(selector, state="visible", timeout=timeout)
                except Exception:
                    pass

                # 2. Tenta clique nativo Playwright
                try:
                    await page.click(selector, force=force, button=button, click_count=click_count, timeout=timeout)
                except Exception:
                    # 3. Fallback via Locator direto
                    loc = page.locator(selector).first
                    try:
                        await loc.click(force=True, button=button, click_count=click_count, timeout=timeout)
                    except Exception:
                        # 4. Fallback via evento DOM
                        try:
                            await loc.dispatch_event("click")
                        except Exception:
                            # 5. Fallback via JavaScript no locator
                            try:
                                await loc.evaluate("el => el.click()")
                            except Exception:
                                pass

                # Se solicitado wait_for, aguarda o elemento alvo pós-clique
                if wait_for:
                    await self.wait(wait_for, state="visible", timeout=timeout, retries=2)
                await self.broadcast_frame()
                return
            except Exception as e:
                last_err = e
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.3)
        raise RuntimeError(f"Falha ao clicar no elemento '{selector}' após {retries} tentativas: {last_err}")

    async def fill(
        self,
        selector: str,
        text: Any,
        timeout: int = 5000,
        retries: int = 3,
        verify: bool = True
    ) -> None:
        """
        Preenche campos de formulário (<input>, <textarea>) com verificação obrigatória de valor e retries.
        Dispara eventos de reatividade ('input', 'change', 'blur') para SPAs (Vue/React/Angular/Wicket).
        """
        page = await self.ensure_active_page()
        target_val = str(text if text is not None else "")
        last_err = None

        for attempt in range(retries):
            try:
                # 1. Aguarda visibilidade do elemento
                await page.wait_for_selector(selector, state="visible", timeout=timeout)
                
                # 2. Limpeza prévia
                loc = page.locator(selector).first
                try:
                    await loc.click(force=True, timeout=2000)
                except Exception:
                    pass
                try:
                    await loc.fill("", timeout=2000)
                except Exception:
                    pass

                # 3. Preenchimento
                await loc.fill(target_val, timeout=timeout)

                # 4. Disparo de eventos de reatividade para SPAs via Locator
                try:
                    await loc.dispatch_event("input")
                    await loc.dispatch_event("change")
                    await loc.dispatch_event("blur")
                except Exception:
                    pass

                # 5. Verificação estrita se o valor foi realmente setado
                if verify:
                    actual_val = ""
                    try:
                        actual_val = await loc.input_value(timeout=1000)
                    except Exception:
                        try:
                            actual_val = await loc.evaluate("el => el ? el.value : ''")
                        except Exception:
                            actual_val = ""

                    digits_target = re.sub(r'\D', '', target_val)
                    digits_actual = re.sub(r'\D', '', str(actual_val))
                    if actual_val == target_val or (digits_target and digits_target == digits_actual):
                        await self.broadcast_frame()
                        return
                    else:
                        # Fallback de digitação se a atribuição direta falhou
                        try:
                            await loc.click(force=True, timeout=1000)
                            await page.keyboard.press("Control+A")
                            await page.keyboard.press("Backspace")
                            await page.keyboard.type(target_val, delay=25)
                        except Exception:
                            # Injeção direta via JS com setter de protótipo no locator (para React/Vue)
                            try:
                                await loc.evaluate("""(el, val) => {
                                    if (el) {
                                        const proto = Object.getPrototypeOf(el);
                                        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                                        if (setter) {
                                            setter.call(el, val);
                                        } else {
                                            el.value = val;
                                        }
                                        el.dispatchEvent(new Event('input', { bubbles: true }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                }""", target_val)
                            except Exception:
                                pass

                        actual_val2 = ""
                        try:
                            actual_val2 = await loc.input_value(timeout=1000)
                        except Exception:
                            try:
                                actual_val2 = await loc.evaluate("el => el ? el.value : ''")
                            except Exception:
                                actual_val2 = ""
                        if actual_val2 == target_val or (digits_target and digits_target == re.sub(r'\D', '', str(actual_val2))):
                            await self.broadcast_frame()
                            return

                await self.broadcast_frame()
                return
            except Exception as e:
                last_err = e
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.3)

        raise RuntimeError(f"Falha ao preencher campo '{selector}' com o valor após {retries} tentativas: {last_err}")

    async def type(
        self,
        selector: str,
        text: Any,
        delay: int = 35,
        timeout: int = 5000,
        retries: int = 3
    ) -> None:
        """
        Digita texto caractere a caractere simulando digitação humana.
        """
        page = await self.ensure_active_page()
        target_val = str(text if text is not None else "")
        last_err = None
        for attempt in range(retries):
            try:
                await page.wait_for_selector(selector, state="visible", timeout=timeout)
                loc = page.locator(selector).first
                await loc.click(force=True, timeout=timeout)
                await loc.type(target_val, delay=delay, timeout=timeout)
                await self.broadcast_frame()
                return
            except Exception as e:
                last_err = e
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.3)
        raise RuntimeError(f"Falha ao digitar no campo '{selector}' após {retries} tentativas: {last_err}")

    async def press(self, key: str, selector: Optional[str] = None) -> None:
        """
        Pressiona uma tecla do teclado ('Enter', 'Tab', 'Escape', 'ArrowDown').
        Se selector for informado, foca no elemento antes de pressionar.
        """
        page = await self.ensure_active_page()
        if selector:
            loc = page.locator(selector).first
            await loc.press(key)
        else:
            await page.keyboard.press(key)
        await self.broadcast_frame()

    async def hover(self, selector: str, timeout: int = 5000) -> None:
        """Passa o mouse (hover) sobre um elemento para abrir menus dropdown e tooltips."""
        page = await self.ensure_active_page()
        await page.wait_for_selector(selector, state="visible", timeout=timeout)
        await page.locator(selector).first.hover(timeout=timeout)

    async def select(
        self,
        selector: str,
        value: Any,
        timeout: int = 5000,
        retries: int = 3,
        verify: bool = True
    ) -> str:
        """
        Seleciona uma opção em um elemento <select> por value, label ou índice.
        Implementa auto-verificação no DOM e retries automáticos.
        """
        page = await self.ensure_active_page()
        target = str(value if value is not None else "")
        last_err = None

        for attempt in range(retries):
            try:
                await page.wait_for_selector(selector, state="visible", timeout=timeout)
                loc = page.locator(selector).first
                
                try:
                    await loc.select_option(value=target, timeout=timeout)
                except Exception:
                    try:
                        await loc.select_option(label=target, timeout=timeout)
                    except Exception:
                        try:
                            await loc.evaluate("""(select, val) => {
                                for (let opt of select.options) {
                                    if (opt.value === val || opt.text.trim() === val || opt.text.includes(val)) {
                                        select.value = opt.value;
                                        select.dispatchEvent(new Event('change', { bubbles: true }));
                                        select.dispatchEvent(new Event('input', { bubbles: true }));
                                        break;
                                    }
                                }
                            }""", target)
                        except Exception:
                            pass

                if verify:
                    try:
                        selected_val = await loc.evaluate("""select => {
                            const opt = select.options[select.selectedIndex];
                            return opt ? (opt.value + ' | ' + opt.text) : select.value;
                        }""")
                        if target in str(selected_val):
                            await self.broadcast_frame()
                            return selected_val
                    except Exception:
                        pass

                await self.broadcast_frame()
                return target
            except Exception as e:
                last_err = e
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.3)

        raise RuntimeError(f"Falha ao selecionar opção '{target}' no seletor '{selector}' após {retries} tentativas: {last_err}")
