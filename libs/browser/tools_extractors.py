# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER TOOLS EXTRACTORS & UTILITIES MIXIN
  Métodos de consulta do DOM, verificação de visibilidade, extração de tabelas,
  resolução de captchas, capturas de tela, downloads e gestão de abas.
=============================================================================
"""

import os
import base64
import asyncio
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("Browser.ToolsExtractors")


class BrowserToolsExtractorsMixin:
    """
    Mixin contendo métodos de extração, inspeção e utilitários do BrowserTools.
    """

    # -------------------------------------------------------------------------
    # Extração de Dados & Consultas no DOM com Espera Reativa
    # -------------------------------------------------------------------------
    async def get_value(self, selector: str, timeout: int = 5000, retries: int = 3) -> str:
        """
        Obtém o valor (.value ou input_value) de um campo de formulário (<input>, <textarea>, <select>).
        Aguarda o elemento com até 3 retentativas automáticas e timeouts curtos.
        """
        page = await self.ensure_active_page()
        last_err = None
        for attempt in range(retries):
            try:
                await page.wait_for_selector(selector, state="attached", timeout=timeout)
                val = await page.locator(selector).first.input_value(timeout=timeout)
                return val.strip() if val is not None else ""
            except Exception as e:
                last_err = e
                try:
                    val = await page.locator(selector).first.evaluate("el => el ? (el.value || el.innerText || '') : null")
                    if val is not None:
                        return str(val).strip()
                except Exception:
                    pass
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.25)
        raise RuntimeError(f"Falha ao obter valor do seletor '{selector}' após {retries} tentativas: {last_err}")

    async def get_text(self, selector: str, timeout: int = 5000, retries: int = 3) -> str:
        """
        Obtém o texto visível de um elemento com espera reativa e até 3 retentativas.
        """
        page = await self.ensure_active_page()
        last_err = None
        for attempt in range(retries):
            try:
                await self.wait(selector, state="visible", timeout=timeout, retries=1)
                txt = await page.locator(selector).first.inner_text(timeout=timeout)
                return txt.strip() if txt else ""
            except Exception as e:
                last_err = e
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.25)
        raise RuntimeError(f"Falha ao obter texto de '{selector}' após {retries} tentativas: {last_err}")

    async def get_attribute(self, selector: str, attribute: str, timeout: int = 5000, retries: int = 3) -> Optional[str]:
        """
        Obtém o valor de um atributo HTML (ex: 'href', 'src', 'value') com espera reativa e retries.
        """
        page = await self.ensure_active_page()
        last_err = None
        for attempt in range(retries):
            try:
                await self.wait(selector, state="attached", timeout=timeout, retries=1)
                return await page.locator(selector).first.get_attribute(attribute, timeout=timeout)
            except Exception as e:
                last_err = e
                try:
                    page = await self.ensure_active_page()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.25)
        raise RuntimeError(f"Falha ao obter atributo '{attribute}' de '{selector}' após {retries} tentativas: {last_err}")

    async def is_visible(self, selector: str, timeout: int = 5000) -> bool:
        """
        Verifica se um elemento está visível no DOM.
        """
        page = await self.ensure_active_page()
        try:
            return await page.locator(selector).first.is_visible(timeout=timeout)
        except Exception:
            return False

    async def is_hidden(self, selector: str, timeout: int = 5000) -> bool:
        """
        Verifica se um elemento está oculto no DOM.
        """
        page = await self.ensure_active_page()
        try:
            return await page.locator(selector).first.is_hidden(timeout=timeout)
        except Exception:
            return True

    async def exists(self, selector: str) -> bool:
        """
        Verifica se um elemento existe no DOM.
        """
        page = await self.ensure_active_page()
        try:
            return (await page.locator(selector).count()) > 0
        except Exception:
            return False

    async def is_checked(self, selector: str, timeout: int = 5000) -> bool:
        """
        Verifica se um checkbox ou radio está marcado no DOM.
        """
        page = await self.ensure_active_page()
        try:
            return await page.locator(selector).first.is_checked(timeout=timeout)
        except Exception:
            return False

    async def is_disabled(self, selector: str, timeout: int = 5000) -> bool:
        """
        Verifica se um elemento está desabilitado no DOM.
        """
        page = await self.ensure_active_page()
        try:
            return await page.locator(selector).first.is_disabled(timeout=timeout)
        except Exception:
            return False

    async def is_enabled(self, selector: str, timeout: int = 5000) -> bool:
        """
        Verifica se um elemento está habilitado no DOM.
        """
        page = await self.ensure_active_page()
        try:
            return await page.locator(selector).first.is_enabled(timeout=timeout)
        except Exception:
            return False

    async def count(self, selector: str, timeout: int = 5000, min_count: int = 1) -> int:
        """
        Aguarda a renderização de elementos no DOM antes de contar, evitando leituras prematuras de 0 itens em AJAX.
        """
        page = await self.ensure_active_page()
        try:
            await page.wait_for_selector(selector, state="attached", timeout=timeout)
        except Exception:
            pass
        return await page.locator(selector).count()

    async def wait_for_idle(self, timeout: int = 2000) -> None:
        """
        Aguarda brevemente a estabilização de rede/DOM após ações assíncronas.
        """
        page = await self.ensure_active_page()
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            await asyncio.sleep(0.5)

    async def extract_table(self, selector: str = "table", timeout: int = 5000, retries: int = 3) -> List[Dict[str, Any]]:
        """
        Extrai qualquer tabela HTML convertendo-a para uma lista de dicionários Python.
        """
        page = await self.ensure_active_page()
        await self.wait(selector, state="attached", timeout=timeout, retries=retries)

        js_extract = """
        (tableSel) => {
            const table = document.querySelector(tableSel);
            if (!table) return [];
            
            const rows = Array.from(table.querySelectorAll('tr'));
            if (rows.length === 0) return [];
            
            // Extrai cabeçalhos
            let headers = [];
            const headerRow = table.querySelector('thead tr') || rows[0];
            const ths = Array.from(headerRow.querySelectorAll('th, td'));
            if (ths.length > 0) {
                headers = ths.map(th => th.innerText.trim().replace(/\\s+/g, ' '));
            }
            
            const results = [];
            const dataRows = (table.querySelector('tbody') ? Array.from(table.querySelectorAll('tbody tr')) : rows.slice(1));
            
            dataRows.forEach((tr, rIdx) => {
                const cells = Array.from(tr.querySelectorAll('td, th'));
                if (cells.length === 0) return;
                const rowObj = {};
                cells.forEach((td, cIdx) => {
                    const colKey = headers[cIdx] || `coluna_${cIdx + 1}`;
                    rowObj[colKey] = td.innerText.trim().replace(/\\s+/g, ' ');
                });
                if (Object.keys(rowObj).length > 0) {
                    results.push(rowObj);
                }
            });
            return results;
        }
        """
        data = await page.evaluate(js_extract, selector)
        await self.broadcast_frame()
        return data or []

    # -------------------------------------------------------------------------
    # Resolução de Captcha & OCR (Delegado para CaptchaSolver)
    # -------------------------------------------------------------------------
    async def solve_captcha(self, selector: str) -> str:
        """
        Resolve automaticamente um captcha de imagem delegando para o módulo CaptchaSolver.
        """
        from libs.browser.captcha import CaptchaSolver
        page = await self.ensure_active_page()
        res = await CaptchaSolver.solve(page, selector)
        await self.broadcast_frame()
        return res

    # -------------------------------------------------------------------------
    # Diagnóstico, Downloads e Abas
    # -------------------------------------------------------------------------
    async def screenshot(
        self,
        filename: Optional[str] = None,
        selector: Optional[str] = None,
        full_page: bool = False
    ) -> str:
        """Captura screenshot e retorna como string Base64 e URI de imagem."""
        page = await self.ensure_active_page()
        if selector:
            el = page.locator(selector).first
            await el.wait_for(state="visible", timeout=10000)
            screenshot_bytes = await el.screenshot()
        else:
            screenshot_bytes = await page.screenshot(full_page=full_page)

        if filename:
            os.makedirs("static/screenshots", exist_ok=True)
            path = os.path.join("static/screenshots", filename)
            with open(path, "wb") as f:
                f.write(screenshot_bytes)

        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def scroll(self, direction: str = "down", amount: int = 500) -> None:
        """Rola a página verticalmente para cima ou para baixo."""
        page = await self.ensure_active_page()
        delta = amount if direction.lower() == "down" else -amount
        await page.evaluate(f"window.scrollBy(0, {delta})")
        await self.broadcast_frame()

    async def evaluate(self, script: str) -> Any:
        """Executa um snippet JavaScript no contexto da página."""
        page = await self.ensure_active_page()
        script_clean = (script or "").strip()
        if "return " in script_clean and not script_clean.startswith("() =>") and not script_clean.startswith("function"):
            script = f"(() => {{ {script_clean} }})()"
        return await page.evaluate(script)

    async def inspect_dom(self) -> str:
        """Inspeciona o DOM da página ativa delegando para dom_inspector."""
        from libs.browser.dom_inspector import inspect_dom
        page = await self.ensure_active_page()
        return await inspect_dom(page)

    async def list_tabs(self) -> List[Dict[str, Any]]:
        """Lista todas as abas/páginas abertas no contexto."""
        if not self._context:
            return []
        tabs = []
        for i, p in enumerate(self._context.pages):
            try:
                title = await p.title()
                tabs.append({"index": i, "url": p.url, "title": title, "is_active": p == self._page})
            except Exception:
                pass
        return tabs

    async def switch_tab(self, index: int) -> None:
        """Alterna a página ativa para o índice especificado."""
        if not self._context:
            raise RuntimeError("Contexto não inicializado.")
        pages = self._context.pages
        if 0 <= index < len(pages):
            self._page = pages[index]
            await self._page.bring_to_front()
        else:
            raise IndexError(f"Aba de índice {index} não encontrada.")

    async def download_file(self, selector: str, timeout: int = 60000) -> Dict[str, Any]:
        """Clica em um elemento e aguarda o download do arquivo."""
        page = await self.ensure_active_page()
        async with page.expect_download(timeout=timeout) as download_info:
            await self.click(selector)
        download = await download_info.value
        os.makedirs("static/downloads", exist_ok=True)
        save_path = os.path.join("static/downloads", download.suggested_filename)
        await download.save_as(save_path)
        self.register_download(save_path)
        return {"downloaded_file": download.suggested_filename, "path": save_path}
