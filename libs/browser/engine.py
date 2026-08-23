# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - UNIFIED PLAYWRIGHT BROWSER ENGINE & TOOLS SDK
  Motor central e agnóstico de automação Playwright para modo Visual e Interno.
  Fornece a classe BrowserTools como SDK de alto nível para scripts e agentes,
  garantindo 100% de paridade em resiliência, seletores, SPAs, iframes e captchas.
=============================================================================
"""

import os
import sys
import io
import json
import base64
import asyncio
import time
import re
import random
from typing import Optional, Dict, Any, List, Tuple, Union

# Limpa bloqueio de diretório se configurado incorretamente
if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == "0":
    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)


# =============================================================================
# 1. INSPEÇÃO PROFUNDA DE DOM & IFRAMES
# =============================================================================

async def inspect_dom(page) -> str:
    """
    Inspeciona o DOM da página ativa e de todos os iframes de forma profunda e recursiva.
    Gera seletores CSS prioritários (:has-text, IDs, names, aria-labels) e XPath correspondente.
    """
    if not page:
        return "Nenhuma página ativa para inspeção."

    js_code = """
    () => {
        const elements = [];
        const query = 'input, button, a, select, textarea, label, img, [role], [onclick], [ng-click], [\\\\@click], [v-on\\\\:click]';
        
        function scanDocument(doc, frameName = '') {
            try {
                const nodes = doc.querySelectorAll(query);
                nodes.forEach((el) => {
                    const tag = el.tagName.toLowerCase();
                    const style = window.getComputedStyle(el);
                    
                    if (style && style.display === 'none' && !['input', 'select', 'textarea'].includes(tag)) {
                        return;
                    }
                    
                    let selector = '';
                    let xpath = '';
                    const id = el.id ? el.id.trim() : null;
                    const name = el.getAttribute('name') ? el.getAttribute('name').trim() : null;
                    const type = el.getAttribute('type') ? el.getAttribute('type').trim() : null;
                    const placeholder = el.getAttribute('placeholder') ? el.getAttribute('placeholder').trim() : null;
                    const text = (el.textContent || el.value || '').trim().substring(0, 60).replace(/\\s+/g, ' ');
                    const ariaLabel = el.getAttribute('aria-label') || el.getAttribute('title') || null;

                    if (id) {
                        selector = `#${id}`;
                        xpath = `//${tag}[@id="${id}"]`;
                    } else if (name) {
                        selector = `${tag}[name="${name}"]`;
                        xpath = `//${tag}[@name="${name}"]`;
                    } else if (type && tag === 'input') {
                        selector = `input[type="${type}"]`;
                        xpath = `//input[@type="${type}"]`;
                    } else if (placeholder) {
                        selector = `${tag}[placeholder="${placeholder}"]`;
                        xpath = `//${tag}[@placeholder="${placeholder}"]`;
                    } else if (ariaLabel) {
                        selector = `${tag}[aria-label="${ariaLabel}"]`;
                        xpath = `//${tag}[@aria-label="${ariaLabel}"]`;
                    } else if (text && text.length > 0 && text.length < 40) {
                        const cleanText = text.replace(/"/g, '\\"');
                        selector = `${tag}:has-text("${cleanText}")`;
                        xpath = `//${tag}[contains(text(), "${cleanText}")]`;
                    } else {
                        const cls = el.className && typeof el.className === 'string' ? `.${el.className.split(' ').filter(c => c).join('.')}` : '';
                        selector = `${tag}${cls}`;
                        xpath = `//${tag}`;
                    }

                    elements.push({
                        frame: frameName,
                        tag: tag.toUpperCase(),
                        id: id,
                        name: name,
                        type: type,
                        placeholder: placeholder,
                        text: text,
                        ariaLabel: ariaLabel,
                        selector: selector,
                        xpath: xpath
                    });
                });
            } catch (err) {
                console.warn('Erro ao escanear documento:', err);
            }
        }

        scanDocument(document, 'main');
        return elements.slice(0, 80);
    }
    """
    try:
        title = await page.title()
        url = page.url
        output = [f"PÁGINA ATUAL: {url}", f"TÍTULO: {title}"]

        frames = getattr(page, "frames", [])
        if len(frames) > 1:
            output.append(f"IFRAMES DETECTADOS NA PÁGINA: {len(frames) - 1}")

        all_elements = []
        for i, frame in enumerate(frames):
            frame_name = "main" if i == 0 else f"frame_{i} ({getattr(frame, 'url', '')})"
            try:
                frame_elems = await frame.evaluate(js_code)
                for el in frame_elems:
                    el['frame_idx'] = i
                    el['frame_name'] = frame_name
                    all_elements.append(el)
            except Exception:
                pass

        if all_elements:
            output.append("\nELEMENTOS INTERATIVOS ENCONTRADOS:")
            for el in all_elements[:80]:
                desc = f"- [{el['tag']}] "
                if el.get('id'): desc += f"id='{el['id']}' "
                if el.get('name'): desc += f"name='{el['name']}' "
                if el.get('type'): desc += f"type='{el['type']}' "
                if el.get('placeholder'): desc += f"placeholder='{el['placeholder']}' "
                if el.get('text'): desc += f"texto='{el['text']}' "
                if el.get('frame_idx', 0) > 0: desc += f"(em {el['frame_name']}) "
                desc += f"=> Seletor CSS: `{el['selector']}` | XPath: `{el['xpath']}`"
                output.append(desc)
        else:
            output.append("\n⚠️ Nenhum elemento interativo padrão foi encontrado via query selector.")
            try:
                body_text = await page.evaluate("() => document.body ? document.body.innerText.substring(0, 1000) : ''")
                if body_text:
                    output.append(f"\nCONTEÚDO TEXTUAL VISÍVEL DA PÁGINA:\n{body_text}")
            except Exception:
                pass

        return "\n".join(output)
    except Exception as e:
        return f"Erro ao inspecionar elementos: {e}"


# =============================================================================
# 2. SDK DE ALTO NÍVEL DE AUTOMAÇÃO (BROWSER TOOLS)
# =============================================================================

class BrowserTools:
    """
    SDK de alto nível e agnóstico de automação web.
    Fornece métodos intuitivos, resilientes e unificados para scripts e agentes,
    encapsulando reatividade de SPAs, esperas inteligentes, extração de tabelas,
    resolução de captchas e gestão de parâmetros de entrada/saída.
    """

    def __init__(
        self,
        page=None,
        context=None,
        browser=None,
        playwright=None,
        login_user: str = "",
        login_pass: str = "",
        params: Optional[Union[Dict[str, Any], str]] = None,
        set_output_fn=None,
        register_download_fn=None
    ):
        self._page = page
        self._context = context
        self._browser = browser
        self._playwright = playwright
        self._login_user = str(login_user or "")
        self._login_pass = str(login_pass or "")
        self._set_output_fn = set_output_fn
        self._register_download_fn = register_download_fn
        self._downloaded_files: List[str] = []
        self._captured_output: Any = None

        # Normalização de parâmetros de entrada (suporta string JSON ou dict)
        self._params: Dict[str, Any] = {}
        if params:
            if isinstance(params, dict):
                self._params = dict(params)
            elif isinstance(params, str) and params.strip():
                try:
                    parsed = json.loads(params.strip())
                    if isinstance(parsed, dict):
                        self._params = parsed
                    else:
                        self._params = {"raw_input": parsed}
                except Exception:
                    self._params = {"raw_input": params.strip()}

    # -------------------------------------------------------------------------
    # Getters / Setters de Sessão e Propriedades
    # -------------------------------------------------------------------------
    @property
    def page(self):
        return self._page

    @property
    def context(self):
        return self._context

    @property
    def browser(self):
        return self._browser

    def set_page(self, page):
        self._page = page

    def get_page(self):
        return self._page

    # -------------------------------------------------------------------------
    # Gestão de Parâmetros e Credenciais (Início da Execução)
    # -------------------------------------------------------------------------
    def get_param(self, key: str, default: Any = None) -> Any:
        """Obtém o valor de um parâmetro de entrada/mock pelo nome."""
        return self._params.get(key, default)

    def get_params(self) -> Dict[str, Any]:
        """Retorna o dicionário completo de parâmetros de entrada."""
        return dict(self._params)

    def get_credential(self, field: str = "user") -> str:
        """Retorna a credencial 'user' (ou 'login') ou 'pass' (ou 'password')."""
        f = field.strip().lower()
        if f in ("user", "login", "username", "usuario"):
            return self._login_user
        if f in ("pass", "password", "senha"):
            return self._login_pass
        return ""

    def require_param(self, key: str) -> Any:
        """Valida que um parâmetro obrigatório está presente, levantando ValueError se ausente."""
        val = self.get_param(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            raise ValueError(f"Parâmetro obrigatório '{key}' não foi informado nos parâmetros de execução.")
        return val

    def require_credentials(self) -> Tuple[str, str]:
        """Valida a presença de usuário e senha, levantando ValueError se ausentes."""
        if not self._login_user or not self._login_pass:
            raise ValueError("Credenciais de acesso (usuário e senha) são obrigatórias para este passo.")
        return self._login_user, self._login_pass

    # -------------------------------------------------------------------------
    # Gestão de Saída de Dados e Arquivos (Final da Execução)
    # -------------------------------------------------------------------------
    def set_output(self, data: Any) -> None:
        """Grava dados estruturados de saída e emite log formatado com [JSON_RESULT]."""
        self._captured_output = data
        if callable(self._set_output_fn):
            try:
                self._set_output_fn(data)
            except Exception:
                pass
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            print(f"[JSON_RESULT] {json_str}")
        except Exception:
            print(f"[JSON_RESULT] {data}")

    def set_result(
        self,
        json_data: Any = None,
        file_url: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Consolida os resultados extraídos (JSON, relatórios e arquivos) em formato padronizado."""
        result: Dict[str, Any] = {}
        if json_data is not None:
            result["data"] = json_data
        if file_url:
            result["file_url"] = file_url
        if file_path:
            result["file_path"] = file_path
        if kwargs:
            result.update(kwargs)
        self.set_output(result)
        return result

    def register_download(self, filepath_or_name: str) -> str:
        """Registra um arquivo baixado na lista de resultados."""
        filename = os.path.basename(str(filepath_or_name))
        self._downloaded_files.append(filename)
        if callable(self._register_download_fn):
            try:
                self._register_download_fn(filename, str(filepath_or_name))
            except Exception:
                pass
        return filename

    def get_downloaded_files(self) -> List[str]:
        """Retorna a lista de nomes dos arquivos baixados durante a sessão."""
        return list(self._downloaded_files)

    def get_downloaded_file(self) -> Optional[str]:
        """Retorna o último arquivo baixado."""
        return self._downloaded_files[-1] if self._downloaded_files else None

    # -------------------------------------------------------------------------
    # Ações de Navegação e Espera
    # -------------------------------------------------------------------------
    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 60000) -> str:
        """Navega até uma URL aguardando o carregamento do DOM."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self._page.goto(url, wait_until=wait_until, timeout=timeout)
        return self._page.url

    async def wait(self, selector: str, state: str = "visible", timeout: int = 15000) -> None:
        """Aguarda um elemento atingir o estado desejado ('visible', 'attached', 'hidden')."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self._page.wait_for_selector(selector, state=state, timeout=timeout)

    async def sleep(self, seconds: float) -> None:
        """Pausa assíncrona segura."""
        await asyncio.sleep(seconds)

    # -------------------------------------------------------------------------
    # Ações de Interação com Elementos & Formulários SPAs
    # -------------------------------------------------------------------------
    async def click(
        self,
        selector: str,
        force: bool = False,
        button: str = "left",
        click_count: int = 1,
        timeout: int = 15000
    ) -> None:
        """
        Executa clique inteligente e resiliente em um seletor.
        Tenta clique direto, depois clique forçado e, em último caso, disparo via JavaScript.
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        try:
            await self._page.click(selector, force=force, button=button, click_count=click_count, timeout=timeout)
        except Exception:
            try:
                await self._page.click(selector, force=True, button=button, click_count=click_count, timeout=5000)
            except Exception:
                await self._page.evaluate("(sel) => document.querySelector(sel)?.click()", selector)

    async def fill(self, selector: str, text: Any, timeout: int = 15000) -> None:
        """
        Preenche campos de texto disparando os eventos de reatividade para SPAs (Vue/React/Angular).
        Garante limpeza prévia e emissão de 'input', 'change' e 'blur'.
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        val = str(text if text is not None else "")
        try:
            await self._page.click(selector, force=True, timeout=3000)
        except Exception:
            pass
        try:
            await self._page.fill(selector, "", timeout=3000)
        except Exception:
            pass

        await self._page.fill(selector, val, timeout=timeout)

        # Dispara eventos de reatividade em frameworks modernos
        await self._page.evaluate("""(sel) => {
            const el = document.querySelector(sel);
            if (el) {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            }
        }""", selector)

    async def type(self, selector: str, text: Any, delay: int = 35, timeout: int = 15000) -> None:
        """Digita texto com delay realista simulando digitação humana."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        val = str(text if text is not None else "")
        try:
            await self._page.click(selector, force=True, timeout=3000)
        except Exception:
            pass
        await self._page.type(selector, val, delay=delay, timeout=timeout)

    async def press(self, key: str = "Enter", selector: Optional[str] = None) -> None:
        """Pressiona uma tecla do teclado (ex: 'Enter', 'Tab', 'Escape', 'ArrowDown')."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        if selector:
            try:
                await self._page.focus(selector)
            except Exception:
                pass
        await self._page.keyboard.press(key)

    async def hover(self, selector: str, timeout: int = 15000) -> None:
        """Move o mouse sobre um elemento."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self._page.hover(selector, timeout=timeout)

    async def select(self, selector: str, value: Any, timeout: int = 15000) -> None:
        """Seleciona uma opção em um <select> pelo valor."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self._page.select_option(selector, str(value), timeout=timeout)

    # -------------------------------------------------------------------------
    # Extração de Dados & Tabelas
    # -------------------------------------------------------------------------
    async def extract_table(self, selector: str = "table", timeout: int = 15000) -> List[Dict[str, Any]]:
        """
        Extrai qualquer tabela HTML convertendo-a para uma lista de dicionários Python:
        [{coluna1: valor, coluna2: valor}, ...]
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self.wait(selector, state="attached", timeout=timeout)

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
        data = await self._page.evaluate(js_extract, selector)
        return data or []

    async def get_text(self, selector: str, timeout: int = 10000) -> str:
        """Obtém o texto visível de um elemento."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self.wait(selector, timeout=timeout)
        txt = await self._page.locator(selector).first.inner_text()
        return txt.strip() if txt else ""

    async def get_attribute(self, selector: str, attribute: str, timeout: int = 10000) -> Optional[str]:
        """Obtém o valor de um atributo HTML de um elemento (ex: 'href', 'src', 'value')."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self.wait(selector, state="attached", timeout=timeout)
        return await self._page.locator(selector).first.get_attribute(attribute)

    # -------------------------------------------------------------------------
    # Resolução de Captcha & OCR
    # -------------------------------------------------------------------------
    async def solve_captcha(self, selector: str) -> str:
        """
        Resolve automaticamente um captcha de imagem localizando o elemento,
        executando OCR local (ddddocr) e fallback com Gemini Vision.
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        el = await self._page.query_selector(selector)
        if not el:
            raise ValueError(f"Elemento de captcha '{selector}' não encontrado.")
        img_bytes = await el.screenshot()

        captcha_text = ""
        # 1. OCR local via ddddocr
        try:
            import ddddocr
            ocr = ddddocr.DdddOcr(show_ad=False)
            captcha_text = ocr.classification(img_bytes)
        except Exception:
            pass

        # 2. Fallback Gemini Vision
        if not captcha_text:
            try:
                from google import genai
                from google.genai import types
                api_key = os.environ.get("GEMINI_API_KEY")
                if api_key:
                    client = genai.Client(api_key=api_key)
                    resp = await client.aio.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[
                            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                            "Retorne APENAS os caracteres do texto do captcha nesta imagem, sem pontuações ou explicações."
                        ]
                    )
                    captcha_text = resp.text.strip().replace(" ", "").replace("\n", "")
            except Exception:
                pass

        if not captcha_text:
            raise RuntimeError("Falha ao reconhecer caracteres do captcha.")

        return captcha_text

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
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        if selector:
            el = self._page.locator(selector).first
            await el.wait_for(state="visible", timeout=10000)
            screenshot_bytes = await el.screenshot()
        else:
            screenshot_bytes = await self._page.screenshot(full_page=full_page)

        if filename:
            os.makedirs("static/screenshots", exist_ok=True)
            path = os.path.join("static/screenshots", filename)
            with open(path, "wb") as f:
                f.write(screenshot_bytes)

        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def scroll(self, direction: str = "down", amount: int = 500) -> None:
        """Rola a página verticalmente para cima ou para baixo."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        delta = amount if direction.lower() == "down" else -amount
        await self._page.evaluate(f"window.scrollBy(0, {delta})")

    async def evaluate(self, script: str) -> Any:
        """Executa um snippet JavaScript no contexto da página."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        return await self._page.evaluate(script)

    async def inspect_dom(self) -> str:
        """Inspeciona o DOM da página ativa."""
        return await inspect_dom(self._page)

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
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        async with self._page.expect_download(timeout=timeout) as download_info:
            await self.click(selector)
        download = await download_info.value
        os.makedirs("static/downloads", exist_ok=True)
        save_path = os.path.join("static/downloads", download.suggested_filename)
        await download.save_as(save_path)
        self.register_download(save_path)
        return {"downloaded_file": download.suggested_filename, "path": save_path}


# =============================================================================
# 3. SANDBOX DE EXECUÇÃO DE CÓDIGO PYTHON NO BROWSER ATIVO
# =============================================================================

async def execute_code_sandbox(
    page,
    context,
    browser,
    p_obj,
    code_str: str,
    login_user: str = "",
    login_pass: str = "",
    extra_context: Optional[Dict[str, Any]] = None,
    register_download_fn=None
) -> Dict[str, Any]:
    """
    Executa snippets de código Python no contexto ativo da página.
    Injeta o objeto 'tools' (BrowserTools), 'page', 'context', 'browser', 'params',
    capturando stdout e chamadas a tools.set_output().
    """
    clean_code = code_str.strip()
    captured_output = None

    def set_output(data):
        nonlocal captured_output
        captured_output = data

    stdout_buffer = io.StringIO()

    class TeeStream:
        def __init__(self, orig, buf):
            self.orig = orig
            self.buf = buf
        def write(self, s):
            try: self.orig.write(s)
            except Exception: pass
            self.buf.write(s)
        def flush(self):
            try: self.orig.flush()
            except Exception: pass
            self.buf.flush()

    original_stdout = sys.stdout
    sys.stdout = TeeStream(original_stdout, stdout_buffer)

    exec_res = None
    tools_instance = BrowserTools(
        page=page,
        context=context,
        browser=browser,
        playwright=p_obj,
        login_user=login_user,
        login_pass=login_pass,
        params=(extra_context or {}).get("params"),
        set_output_fn=set_output,
        register_download_fn=register_download_fn
    )

    try:
        global_context = {
            "tools": tools_instance,
            "page": page,
            "context": context,
            "browser": browser,
            "playwright": p_obj,
            "p": p_obj,
            "asyncio": asyncio,
            "json": json,
            "set_output": set_output,
            "login_user": login_user,
            "login_pass": login_pass,
            "params": tools_instance.get_params(),
            "time": time,
            "re": re,
            "random": random,
            "os": os,
            "sys": sys
        }
        if extra_context:
            global_context.update(extra_context)

        # Se contiver 'async def main' ou 'def main', executa e chama main()
        if "async def main" in clean_code or "def main" in clean_code:
            script_ns = dict(global_context)
            exec(clean_code, script_ns)
            main_fn = script_ns.get("main")
            if main_fn:
                if asyncio.iscoroutinefunction(main_fn):
                    exec_res = await main_fn()
                else:
                    exec_res = main_fn()
            else:
                exec_res = "Main executado"
        else:
            # Envolve o snippet em uma função assíncrona injetando tools, page, etc.
            indented = "\n".join("        " + line for line in clean_code.split('\n'))
            wrapper = f"""async def __snippet_runner(tools, page, context, browser, playwright, p, asyncio, set_output, login_user, login_pass, params):
{indented}
        _locs = locals()
        for _k, _v in list(_locs.items()):
            if callable(_v) and _k not in ('tools', 'page', 'context', 'browser', 'playwright', 'p', 'asyncio', 'set_output', 'login_user', 'login_pass', 'params') and not _k.startswith('__'):
                try:
                    import inspect
                    sig = inspect.signature(_v)
                    params_count = len(sig.parameters)
                    if asyncio.iscoroutinefunction(_v):
                        _fn_res = await (_v(tools) if params_count >= 1 else _v())
                    else:
                        _fn_res = _v(tools) if params_count >= 1 else _v()
                    if _fn_res is not None:
                        set_output(_fn_res)
                        return _fn_res
                except Exception:
                    pass
        if 'data' in _locs and _locs['data'] is not None:
            set_output(_locs['data'])
            return _locs['data']
        if 'dados' in _locs and _locs['dados'] is not None:
            set_output(_locs['dados'])
            return _locs['dados']
"""
            local_ns = {}
            exec(wrapper, global_context, local_ns)
            runner_func = local_ns.get("__snippet_runner")
            exec_res = await runner_func(
                tools_instance, page, context, browser, p_obj, p_obj, asyncio, set_output,
                login_user, login_pass, tools_instance.get_params()
            )
    finally:
        sys.stdout = original_stdout

    captured_stdout_str = stdout_buffer.getvalue().strip()
    structured_data = captured_output if captured_output is not None else exec_res

    # Se não houver retorno explícito, tenta extrair JSON impresso via print()
    if structured_data in (None, "Main executado", "Snippet executado") and captured_stdout_str:
        try:
            structured_data = json.loads(captured_stdout_str)
        except Exception:
            for line in captured_stdout_str.splitlines():
                clean_l = line.strip()
                if clean_l.startswith("[JSON_RESULT]"):
                    try:
                        structured_data = json.loads(clean_l.replace("[JSON_RESULT]", "").strip())
                        break
                    except Exception:
                        pass
                elif (clean_l.startswith('{') and clean_l.endswith('}')) or (clean_l.startswith('[') and clean_l.endswith(']')):
                    try:
                        structured_data = json.loads(clean_l)
                        break
                    except Exception:
                        pass

    if isinstance(structured_data, str) and (structured_data.strip().startswith('{') or structured_data.strip().startswith('[')):
        try:
            structured_data = json.loads(structured_data)
        except Exception:
            pass

    return {
        "status": "success",
        "result": "Executado com sucesso",
        "data": structured_data,
        "logs": stdout_buffer.getvalue(),
        "downloaded_files": tools_instance.get_downloaded_files()
    }


# =============================================================================
# 4. DESPACHANTE UNIFICADO DE AÇÕES BROWSER
# =============================================================================

async def execute_browser_action(
    page,
    context,
    browser,
    p_obj,
    action: str,
    params: Optional[Dict[str, Any]] = None,
    record_frame_fn=None,
    set_output_fn=None,
    register_download_fn=None
) -> Dict[str, Any]:
    """
    Despachante unificado de ações para os modos Visual e Interno delegando para BrowserTools.
    """
    params = params or {}
    act = (action or "").strip().lower()

    tools = BrowserTools(
        page=page,
        context=context,
        browser=browser,
        playwright=p_obj,
        login_user=str(params.get("login_user", "")),
        login_pass=str(params.get("login_pass", "")),
        params=params.get("params"),
        set_output_fn=set_output_fn,
        register_download_fn=register_download_fn
    )

    try:
        if act == "goto":
            url = params.get("url") or params.get("target_url")
            res_url = await tools.goto(url)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "url": res_url, "title": await page.title() if page else ""}

        elif act == "click":
            selector = params.get("selector")
            force = params.get("force", False)
            button = params.get("button", "left")
            click_count = params.get("click_count", 1)
            await tools.click(selector, force=force, button=button, click_count=click_count)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "clicked", "selector": selector}

        elif act in ("type", "fill"):
            selector = params.get("selector")
            text = params.get("text") or params.get("value") or ""
            if act == "type":
                await tools.type(selector, text, delay=params.get("delay", 35))
            else:
                await tools.fill(selector, text)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "filled", "selector": selector}

        elif act == "solve_captcha":
            selector = params.get("selector")
            captcha_text = await tools.solve_captcha(selector)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "captcha_text": captcha_text}

        elif act in ("press", "press_key"):
            key = params.get("key", "Enter")
            selector = params.get("selector")
            await tools.press(key, selector=selector)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "key_pressed", "key": key}

        elif act == "wait_for":
            selector = params.get("selector")
            state = params.get("state", "visible")
            timeout = params.get("timeout", 15000)
            await tools.wait(selector, state=state, timeout=timeout)
            return {"status": "success", "action": "found", "selector": selector}

        elif act == "extract_table":
            selector = params.get("selector", "table")
            table_data = await tools.extract_table(selector)
            return {"status": "success", "data": table_data}

        elif act == "upload_file":
            selector = params.get("selector")
            file_path = params.get("file_path") or params.get("filename")
            await page.set_input_files(selector, file_path, timeout=30000)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "uploaded", "file": file_path}

        elif act == "download_file":
            selector = params.get("selector")
            res_dl = await tools.download_file(selector)
            return {"status": "success", **res_dl}

        elif act in ("inspect", "get_dom", "inspect_dom"):
            inspect_text = await tools.inspect_dom()
            return {"status": "success", "inspect_text": inspect_text}

        elif act == "screenshot":
            b64_str = await tools.screenshot(
                filename=params.get("filename"),
                selector=params.get("selector"),
                full_page=bool(params.get("full_page", False))
            )
            if record_frame_fn: await record_frame_fn()
            return {
                "status": "success",
                "b64_image": b64_str,
                "data_uri": f"data:image/png;base64,{b64_str}",
                "size_bytes": len(b64_str)
            }

        elif act == "hover":
            selector = params.get("selector")
            await tools.hover(selector)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "hovered", "selector": selector}

        elif act == "select":
            selector = params.get("selector")
            value = params.get("value")
            await tools.select(selector, value)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "selected", "selector": selector, "value": value}

        elif act == "evaluate":
            script = params.get("script") or params.get("js_code")
            eval_res = await tools.evaluate(script)
            return {"status": "success", "result": eval_res}

        elif act == "get_html":
            content = await page.content() if page else ""
            return {"status": "success", "html": content}

        elif act == "scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 500)
            await tools.scroll(direction=direction, amount=amount)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "scrolled", "direction": direction, "amount": amount}

        elif act in ("back", "go_back"):
            if page:
                await page.go_back(wait_until='domcontentloaded', timeout=30000)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "navigated_back", "url": page.url if page else ""}

        elif act in ("run_code", "execute_code", "eval_python"):
            code_str = params.get("code", "")
            login_user = params.get("login_user", "")
            login_pass = params.get("login_pass", "")
            res = await execute_code_sandbox(
                page, context, browser, p_obj, code_str,
                login_user=login_user,
                login_pass=login_pass,
                extra_context=params,
                register_download_fn=register_download_fn
            )
            if record_frame_fn: await record_frame_fn()
            return res

        return {"status": "error", "error": f"Ação '{action}' não suportada pelo motor de navegação."}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# =============================================================================
# 5. INICIALIZADOR DE NAVEGADOR COM STEALTH ANTI-DETECTION
# =============================================================================

async def init_browser_engine(
    p_obj,
    engine: Optional[str] = None,
    headless: bool = True,
    proxy_config: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
    viewport: Optional[Dict[str, int]] = None
) -> Tuple[Any, Any, Any]:
    """
    Inicializa o navegador (Browser), Contexto com Proteção Anti-Detecção Stealth e Página ativa.
    Suporta Camoufox, Chromium nativo e conexão remota com servidor Playwright.
    """
    ws_url = os.environ.get("PLAYWRIGHT_SERVER_WS_URL")
    selected_engine = (engine or os.environ.get("BROWSER_ENGINE") or "").strip().lower()

    browser = None

    # 1. Tenta Camoufox se solicitado
    if "camoufox" in selected_engine:
        try:
            from camoufox.async_api import AsyncCamoufox
            camoufox_kwargs = {"headless": headless, "humanize": True}
            if proxy_config:
                camoufox_kwargs["proxy"] = proxy_config
            browser = await AsyncCamoufox(**camoufox_kwargs).__aenter__()
        except Exception:
            pass

    # 2. Conexão com microsserviço Playwright se disponível
    if not browser and ws_url and headless:
        try:
            browser = await p_obj.chromium.connect(ws_url, timeout=30000)
        except Exception:
            pass

    # 3. Chromium Local com Argumentos Stealth
    if not browser:
        stealth_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1280,800",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-dev-shm-usage",
            "--disable-gpu"
        ]
        launch_kwargs = {
            "headless": headless,
            "args": stealth_args
        }
        if proxy_config:
            launch_kwargs["proxy"] = proxy_config
        browser = await p_obj.chromium.launch(**launch_kwargs)

    # Criação de contexto com evasão anti-detecção
    ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    vp = viewport or {"width": 1280, "height": 800}

    context_kwargs = {
        "user_agent": ua,
        "viewport": vp,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "accept_downloads": True
    }
    if proxy_config:
        context_kwargs["proxy"] = proxy_config

    context = await browser.new_context(**context_kwargs)

    # Injeta script anti-detecção
    stealth_js = """
    (() => {
        try {
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            const originalQuery = window.navigator.permissions?.query;
            if (originalQuery) {
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            }
        } catch (e) {}
    })();
    """
    await context.add_init_script(stealth_js)
    page = await context.new_page()
    return browser, context, page
