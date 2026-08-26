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
import unicodedata
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List, Tuple, Union

try:
    from libs.browser.dom_inspector import inspect_dom
    from libs.browser.captcha import CaptchaSolver, solve_captcha_image
    from libs.browser.sandbox import execute_code_sandbox, TeeStream
    from libs.browser.action_dispatcher import execute_browser_action
    from libs.browser.launcher import init_browser_engine
except ImportError:
    # =========================================================================
    # IMPLEMENTAÇÃO STANDALONE COMPLETA (CLIENTE DESKTOP / RUNTIME ISOLADO)
    # =========================================================================
    
    class TeeStream:
        def __init__(self, orig, buf):
            self.orig = orig
            self.buf = buf

        def write(self, s):
            try:
                self.orig.write(s)
            except Exception:
                pass
            self.buf.write(s)

        def flush(self):
            try:
                self.orig.flush()
            except Exception:
                pass
            self.buf.flush()

    class CaptchaSolver:
        @classmethod
        async def solve(cls, page: Any, selector: str) -> str:
            if not page:
                raise RuntimeError("Página do navegador não inicializada.")

            el = await page.query_selector(selector)
            if not el:
                for s in [selector, f"img{selector}", f"#{selector.lstrip('#')}", "img[id*='captcha' i]", "img[src*='captcha' i]", "#cipCaptchaImg", "#captchaImg"]:
                    try:
                        el = await page.query_selector(s)
                        if el:
                            break
                    except Exception:
                        pass

            if not el:
                raise ValueError(f"Elemento de captcha '{selector}' não encontrado no DOM.")

            try:
                await el.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass

            img_bytes = None
            try:
                img_bytes = await el.screenshot()
            except Exception:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        img_bytes = await el.screenshot()
                except Exception as e:
                    raise ValueError(f"Não foi possível capturar imagem do captcha: {e}")

            if not img_bytes:
                raise ValueError("Imagem do captcha vazia.")

            captcha_text = ""
            try:
                import ddddocr
                ocr = ddddocr.DdddOcr(show_ad=False)
                captcha_text = ocr.classification(img_bytes)
            except Exception:
                pass

            if not captcha_text:
                try:
                    import urllib.request
                    b64_img = base64.b64encode(img_bytes).decode("utf-8")
                    server_url = os.environ.get("CBR_SERVER_URL") or "https://ia.creditobr.com.br"
                    token = os.environ.get("CBR_AUTH_TOKEN") or ""
                    
                    app_session = os.path.expanduser("~/.cbragents/session.json")
                    if os.path.exists(app_session):
                        try:
                            with open(app_session, "r", encoding="utf-8") as sf:
                                sdata = json.load(sf)
                                if sdata.get("server_url"):
                                    server_url = sdata.get("server_url").rstrip("/")
                                if sdata.get("token"):
                                    token = sdata.get("token")
                        except Exception:
                            pass
                    
                    req_url = f"{server_url}/api/webpilot/solve-captcha"
                    req_payload = json.dumps({"b64_image": b64_img, "mime_type": "image/png"}).encode("utf-8")
                    headers = {"Content-Type": "application/json", "User-Agent": "CBR-Agents-Engine/2.5"}
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    req = urllib.request.Request(req_url, data=req_payload, headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as res:
                        if res.status == 200:
                            resp_dict = json.loads(res.read().decode("utf-8"))
                            captcha_text = resp_dict.get("text", "").strip()
                except Exception:
                    pass

            if not captcha_text:
                raise RuntimeError("Não foi possível resolver o captcha automaticamente.")
            return captcha_text

    async def solve_captcha_image(page: Any, selector: str) -> str:
        return await CaptchaSolver.solve(page, selector)

    async def inspect_dom(page: Any) -> str:
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
                        if (style && style.display === 'none' && !['input', 'select', 'textarea'].includes(tag)) return;
                        
                        let selector = '';
                        let xpath = '';
                        const id = el.id ? el.id.trim() : null;
                        const name = el.getAttribute('name') ? el.getAttribute('name').trim() : null;
                        const type = el.getAttribute('type') ? el.getAttribute('type').trim() : null;
                        const placeholder = el.getAttribute('placeholder') ? el.getAttribute('placeholder').trim() : null;
                        const text = (el.textContent || el.value || '').trim().substring(0, 60).replace(/\\s+/g, ' ');
                        const ariaLabel = el.getAttribute('aria-label') || el.getAttribute('title') || null;

                        if (id) { selector = `#${id}`; xpath = `//${tag}[@id="${id}"]`; }
                        else if (name) { selector = `${tag}[name="${name}"]`; xpath = `//${tag}[@name="${name}"]`; }
                        else if (type && tag === 'input') { selector = `input[type="${type}"]`; xpath = `//input[@type="${type}"]`; }
                        else if (placeholder) { selector = `${tag}[placeholder="${placeholder}"]`; xpath = `//${tag}[@placeholder="${placeholder}"]`; }
                        else if (ariaLabel) { selector = `${tag}[aria-label="${ariaLabel}"]`; xpath = `//${tag}[@aria-label="${ariaLabel}"]`; }
                        else if (text && text.length > 0 && text.length < 40) {
                            const cleanText = text.replace(/"/g, '\\"');
                            selector = `${tag}:has-text("${cleanText}")`;
                            xpath = `//${tag}[contains(text(), "${cleanText}")]`;
                        } else {
                            const cls = el.className && typeof el.className === 'string' ? `.${el.className.split(' ').filter(c => c).join('.')}` : '';
                            selector = `${tag}${cls}`;
                            xpath = `//${tag}`;
                        }

                        elements.push({ frame: frameName, tag: tag.toUpperCase(), id, name, type, placeholder, text, ariaLabel, selector, xpath });
                    });
                } catch (err) {}
            }
            scanDocument(document, 'main');
            return elements.slice(0, 80);
        }
        """
        try:
            title = await page.title()
            url = page.url
            output = [f"PÁGINA ATUAL: {url}", f"TÍTULO: {title}"]
            elements = await page.evaluate(js_code)
            for idx, el in enumerate(elements):
                info = f"[{idx + 1}] <{el['tag']}> Seletor: `{el['selector']}`"
                if el.get("text"): info += f" | Texto: \"{el['text']}\""
                if el.get("name"): info += f" | Name: \"{el['name']}\""
                if el.get("id"): info += f" | ID: \"{el['id']}\""
                output.append(info)
            return "\n".join(output)
        except Exception as e:
            return f"Erro ao inspecionar DOM: {e}"

    async def execute_code_sandbox(page, context, browser, p_obj, code_str: str, login_user: str = "", login_pass: str = "", extra_context: Optional[Dict[str, Any]] = None, register_download_fn=None) -> Dict[str, Any]:
        import textwrap
        clean_code = code_str.strip()
        captured_output = getattr(page, "_accumulated_output", None) if page else None

        def set_output(data):
            nonlocal captured_output
            if data is None: return
            if page:
                if not hasattr(page, "_accumulated_output") or page._accumulated_output is None:
                    try: page._accumulated_output = dict(data) if isinstance(data, dict) else data
                    except Exception: page._accumulated_output = data
                    captured_output = page._accumulated_output
                elif isinstance(page._accumulated_output, dict) and isinstance(data, dict):
                    for k, v in data.items():
                        if v is not None and v != "" and v != [] and v != {}:
                            page._accumulated_output[k] = v
                        elif k not in page._accumulated_output:
                            page._accumulated_output[k] = v
                    captured_output = page._accumulated_output
                elif isinstance(page._accumulated_output, list) and isinstance(data, list):
                    page._accumulated_output.extend(data)
                    captured_output = page._accumulated_output
                else:
                    page._accumulated_output = data
                    captured_output = data
            else:
                captured_output = data

        stdout_buffer = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = TeeStream(original_stdout, stdout_buffer)

        tools_instance = BrowserTools(
            page=page, context=context, browser=browser, playwright=p_obj,
            login_user=login_user, login_pass=login_pass,
            params=(extra_context or {}).get("params"),
            set_output_fn=set_output, register_download_fn=register_download_fn
        )

        try:
            global_context = {
                "tools": tools_instance, "page": page, "context": context, "browser": browser,
                "playwright": p_obj, "p": p_obj, "asyncio": asyncio, "json": json,
                "set_output": set_output, "login_user": login_user, "login_pass": login_pass,
                "params": tools_instance.get_params(), "time": time, "re": re, "random": random, "os": os, "sys": sys
            }
            if extra_context: global_context.update(extra_context)

            if "async def main" in clean_code or "def main" in clean_code:
                script_ns = dict(global_context)
                exec(clean_code, script_ns)
                main_fn = script_ns.get("main")
                if main_fn:
                    exec_res = await main_fn() if asyncio.iscoroutinefunction(main_fn) else main_fn()
                else:
                    exec_res = "Main executado"
            else:
                dedented_code = textwrap.dedent(clean_code).strip()
                indented = "\n".join("        " + line for line in dedented_code.split('\n'))
                wrapper = f"""async def __snippet_runner(tools, page, context, browser, playwright, p, asyncio, set_output, login_user, login_pass, params):
{indented}
        _locs = locals()
        for _k, _v in list(_locs.items()):
            if callable(_v) and _k not in ('tools', 'page', 'context', 'browser', 'playwright', 'p', 'asyncio', 'set_output', 'login_user', 'login_pass', 'params') and not _k.startswith('__'):
                try:
                    import inspect
                    sig = inspect.signature(_v)
                    params_count = len(sig.parameters)
                    _fn_res = await (_v(tools) if params_count >= 1 else _v()) if asyncio.iscoroutinefunction(_v) else (_v(tools) if params_count >= 1 else _v())
                    if _fn_res is not None:
                        set_output(_fn_res)
                        return _fn_res
                except Exception: pass
        for _v_key in ('resultado', 'result', 'output', 'data', 'dados', 'extracted_data', 'final_result', 'dados_extraidos', 'contratos', 'margem', 'res'):
            if _v_key in _locs and _locs[_v_key] is not None:
                set_output(_locs[_v_key])
                return _locs[_v_key]
"""
                local_ns = {}
                exec(wrapper, global_context, local_ns)
                runner_func = local_ns.get("__snippet_runner")
                exec_res = await runner_func(tools_instance, page, context, browser, p_obj, p_obj, asyncio, set_output, login_user, login_pass, tools_instance.get_params())
        finally:
            sys.stdout = original_stdout

        raw_logs = stdout_buffer.getvalue()
        if raw_logs.strip():
            for line in raw_logs.strip().splitlines():
                if "[JSON_RESULT]" in line:
                    try:
                        extracted = json.loads(line.replace("[JSON_RESULT]", "").strip())
                        set_output(extracted)
                    except Exception: pass

        return {"result": exec_res or "Executado com sucesso", "data": captured_output, "logs": raw_logs}

    async def execute_browser_action(page, context, browser, p_obj, action: str, params: Optional[Dict[str, Any]] = None, record_frame_fn=None, set_output_fn=None, register_download_fn=None) -> Dict[str, Any]:
        params = params or {}
        act = (action or "").strip().lower()
        tools = BrowserTools(page=page, context=context, browser=browser, playwright=p_obj, login_user=str(params.get("login_user", "")), login_pass=str(params.get("login_pass", "")), params=params.get("params"), set_output_fn=set_output_fn, register_download_fn=register_download_fn)
        if act == "goto":
            url = params.get("url") or params.get("target_url")
            res_url = await tools.goto(url)
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "url": res_url, "title": await page.title() if page else ""}
        elif act == "click":
            await tools.click(params.get("selector"), force=params.get("force", False), button=params.get("button", "left"), click_count=params.get("click_count", 1))
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "clicked"}
        elif act in ("type", "fill"):
            if act == "type": await tools.type(params.get("selector"), params.get("text") or params.get("value") or "", delay=params.get("delay", 35))
            else: await tools.fill(params.get("selector"), params.get("text") or params.get("value") or "")
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "filled"}
        elif act == "solve_captcha":
            txt = await tools.solve_captcha(params.get("selector"))
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "captcha_text": txt}
        elif act in ("press", "press_key"):
            await tools.press(params.get("key", "Enter"), selector=params.get("selector"))
            if record_frame_fn: await record_frame_fn()
            return {"status": "success", "action": "key_pressed"}
        elif act == "wait_for":
            await tools.wait(params.get("selector"), state=params.get("state", "visible"), timeout=params.get("timeout", 15000))
            return {"status": "success", "action": "found"}
        elif act == "extract_table":
            dt = await tools.extract_table(params.get("selector", "table"))
            return {"status": "success", "data": dt}
        elif act == "run_code":
            code = params.get("code") or params.get("script") or ""
            return await execute_code_sandbox(page=page, context=context, browser=browser, p_obj=p_obj, code_str=code, login_user=params.get("login_user", ""), login_pass=params.get("login_pass", ""), extra_context={"params": params.get("params")}, register_download_fn=register_download_fn)
        elif act == "inspect_dom":
            return {"status": "success", "dom": await inspect_dom(page)}
        return {"status": "error", "error": f"Ação desconhecida: {act}"}

    async def init_browser_engine(p_obj, engine: Optional[str] = None, headless: bool = True, proxy_config: Optional[Dict[str, str]] = None, user_agent: Optional[str] = None, viewport: Optional[Dict[str, int]] = None) -> Tuple[Any, Any, Any]:
        ws_url = os.environ.get("PLAYWRIGHT_SERVER_WS_URL")
        browser = None
        if ws_url and headless:
            try: browser = await p_obj.chromium.connect(ws_url, timeout=30000)
            except Exception: pass
        if not browser:
            stealth_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled", "--disable-infobars", "--window-size=1280,800", "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-dev-shm-usage", "--disable-gpu"]
            launch_kwargs = {"headless": headless, "args": stealth_args}
            if proxy_config: launch_kwargs["proxy"] = proxy_config
            browser = await p_obj.chromium.launch(**launch_kwargs)

        ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        context_kwargs = {"user_agent": ua, "viewport": viewport or {"width": 1280, "height": 800}, "locale": "pt-BR", "timezone_id": "America/Sao_Paulo", "accept_downloads": True}
        if proxy_config: context_kwargs["proxy"] = proxy_config
        context = await browser.new_context(**context_kwargs)
        stealth_js = "(() => { try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] }); Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] }); window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} }; } catch (e) {} })();"
        await context.add_init_script(stealth_js)
        page = await context.new_page()
        return browser, context, page

logger = logging.getLogger("Browser.Engine")

# Limpa bloqueio de diretório se configurado incorretamente
if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == "0":
    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)


# =============================================================================
# SDK DE ALTO NÍVEL DE AUTOMAÇÃO (BROWSER TOOLS)
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

        # Normalização de parâmetros de entrada (suporta string JSON, dict aninhado ou objeto)
        self._params: Dict[str, Any] = {}
        if params:
            if isinstance(params, dict):
                self._params = dict(params)
                if "test_input_mock" in self._params and isinstance(self._params["test_input_mock"], dict):
                    self._params.update(self._params["test_input_mock"])
                if "params" in self._params and isinstance(self._params["params"], dict):
                    self._params.update(self._params["params"])
            elif isinstance(params, str) and params.strip():
                try:
                    parsed = json.loads(params.strip())
                    if isinstance(parsed, dict):
                        self._params = parsed
                        if "test_input_mock" in self._params and isinstance(self._params["test_input_mock"], dict):
                            self._params.update(self._params["test_input_mock"])
                    else:
                        self._params = {"raw_input": parsed}
                except Exception:
                    self._params = {"raw_input": params.strip()}

        # Agrega credenciais se não presentes em params
        if self._login_user and "login_user" not in self._params and "user" not in self._params:
            self._params["login_user"] = self._login_user
        if self._login_pass and "login_pass" not in self._params and "senha" not in self._params and "password" not in self._params:
            self._params["login_pass"] = self._login_pass

    # -------------------------------------------------------------------------
    # Gerenciador de Contexto Assíncrono Oficial (Sessão Completa do Navegador)
    # -------------------------------------------------------------------------
    @classmethod
    @asynccontextmanager
    async def session(
        cls,
        headless: Optional[bool] = None,
        default_mock: Optional[Any] = None,
        login_user: str = "",
        login_pass: str = "",
        proxy_config: Optional[Dict[str, str]] = None
    ):
        """
        Gerenciador de contexto assíncrono para inicialização, execução e encerramento
        automático do ciclo de vida do navegador Playwright com anti-bot stealth e proxy.
        
        Uso:
            async with BrowserTools.session(headless=True, default_mock={"cpf": "123"}) as tools:
                await tools.goto("https://exemplo.com")
                ...
        """
        from playwright.async_api import async_playwright
        
        env_headless = os.getenv("HEADLESS")
        if headless is None:
            headless = env_headless.lower() in ("true", "1") if env_headless is not None else True
        
        ws_url = os.environ.get("PLAYWRIGHT_SERVER_WS_URL")
        if not proxy_config:
            proxy_server = os.environ.get("PROXY_SERVER")
            if proxy_server and proxy_server.strip():
                proxy_config = {"server": proxy_server.strip()}
                p_user = os.environ.get("PROXY_USERNAME")
                p_pass = os.environ.get("PROXY_PASSWORD")
                if p_user and p_pass:
                    proxy_config["username"] = p_user.strip()
                    proxy_config["password"] = p_pass.strip()

        async with async_playwright() as p:
            launch_kwargs = {
                "headless": headless,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1280,800",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-extensions"
                ]
            }
            if proxy_config:
                launch_kwargs["proxy"] = proxy_config

            browser = None
            if ws_url and headless:
                try:
                    browser = await p.chromium.connect(ws_url)
                except Exception:
                    pass
            if not browser:
                browser = await p.chromium.launch(**launch_kwargs)

            context_kwargs = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 800},
                "locale": "pt-BR",
                "timezone_id": "America/Sao_Paulo",
                "accept_downloads": True
            }
            if proxy_config:
                context_kwargs["proxy"] = proxy_config
            
            context = await browser.new_context(**context_kwargs)
            
            stealth_js = """
            (() => {
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
                window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            })();
            """
            await context.add_init_script(stealth_js)
            page = await context.new_page()

            raw_params = os.environ.get("EXECUTION_PARAMS", "").strip()
            params = {}
            if raw_params:
                try:
                    params = json.loads(raw_params)
                except Exception:
                    params = {"input": raw_params}
            elif default_mock:
                params = dict(default_mock) if isinstance(default_mock, dict) else {"input": default_mock}

            eff_user = (
                params.get("email") or
                params.get("user") or
                params.get("login_user") or
                params.get("cpf") or
                os.environ.get("LOGIN_USER", "") or
                login_user
            )
            eff_pass = (
                params.get("password") or
                params.get("pwd") or
                params.get("senha") or
                params.get("login_pass") or
                os.environ.get("LOGIN_PASS", "") or
                login_pass
            )

            output_holder = {"data": None}
            def set_output(data):
                if data is None:
                    return
                if isinstance(output_holder["data"], dict) and isinstance(data, dict):
                    output_holder["data"].update(data)
                else:
                    output_holder["data"] = data
                try:
                    print(f"[JSON_RESULT] {json.dumps(output_holder['data'], ensure_ascii=False)}")
                except Exception:
                    print(f"[JSON_RESULT] {output_holder['data']}")

            tools = cls(
                page=page,
                context=context,
                browser=browser,
                playwright=p,
                login_user=eff_user,
                login_pass=eff_pass,
                params=params,
                set_output_fn=set_output
            )
            tools._output_holder = output_holder

            try:
                yield tools
            finally:
                final_res = output_holder.get("data") if isinstance(output_holder, dict) else getattr(tools, "_captured_output", None)
                if final_res is not None:
                    print("\n=== RESULTADO CONSOLIDADO DA EXTRAÇÃO ===")
                    try:
                        print("[JSON_RESULT] " + json.dumps(final_res, ensure_ascii=False))
                    except Exception:
                        print(f"[JSON_RESULT] {final_res}")
                try:
                    await context.close()
                except Exception:
                    pass
                try:
                    await browser.close()
                except Exception:
                    pass

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

    @property
    def login_user(self) -> str:
        return self._login_user

    @property
    def login_pass(self) -> str:
        return self._login_pass

    def set_page(self, page):
        self._page = page

    def get_page(self):
        return self._page

    # -------------------------------------------------------------------------
    # Gestão de Parâmetros e Credenciais (Início da Execução)
    # -------------------------------------------------------------------------
    def get_param(self, key: str, default: Any = None) -> Any:
        """Obtém o valor de um parâmetro de entrada/mock pelo nome com fallback inteligente."""
        if not key:
            return default
        if key in self._params and self._params[key] is not None:
            return self._params[key]
            
        k = key.strip().lower()
        for pk, pv in self._params.items():
            if pk.strip().lower() == k and pv is not None:
                return pv

        # Fallbacks semânticos automáticos
        if k in ("cpf", "login_cpf", "user", "login_user", "usuario", "login", "username"):
            return (
                self._params.get("cpf") or
                self._params.get("login_user") or
                self._params.get("user") or
                self._params.get("login") or
                self._login_user or
                os.environ.get("LOGIN_USER") or
                os.environ.get("LOGIN_CPF") or
                os.environ.get("CPF") or
                default
            )
        if k in ("senha", "pwd", "password", "login_pass", "pass"):
            return (
                self._params.get("senha") or
                self._params.get("pwd") or
                self._params.get("password") or
                self._params.get("login_pass") or
                self._login_pass or
                os.environ.get("LOGIN_PASS") or
                os.environ.get("SENHA") or
                default
            )
        if k in ("identificador", "matricula", "mat", "id", "beneficio"):
            return (
                self._params.get("identificador") or
                self._params.get("matricula") or
                self._params.get("mat") or
                os.environ.get("LOGIN_MATRICULA") or
                os.environ.get("MATRICULA") or
                default
            )

        return default

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

    def set_output(self, data: Any) -> None:
        """Grava dados estruturados de saída, mesclando dicionários e emitindo [JSON_RESULT] em linha única."""
        if data is None:
            return
            
        if isinstance(self._captured_output, dict) and isinstance(data, dict):
            self._captured_output.update(data)
            out_data = self._captured_output
        else:
            self._captured_output = data
            out_data = data

        if callable(self._set_output_fn):
            try:
                self._set_output_fn(out_data)
            except Exception:
                pass
        try:
            json_str = json.dumps(out_data, ensure_ascii=False)
            print(f"[JSON_RESULT] {json_str}")
        except Exception:
            print(f"[JSON_RESULT] {out_data}")

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
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        last_err = None
        for attempt in range(retries):
            try:
                await self._page.goto(url, wait_until=wait_until, timeout=timeout)
                if wait_for:
                    await self.wait(wait_for, state="visible", timeout=5000, retries=retries)
                return self._page.url
            except Exception as e:
                last_err = e
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
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        last_err = None
        for attempt in range(retries):
            try:
                await self._page.wait_for_selector(selector, state=state, timeout=timeout)
                return
            except Exception as e:
                last_err = e
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
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self._page.go_back(wait_until="domcontentloaded", timeout=30000)
        return self._page.url

    async def reload(self) -> str:
        """Recarrega a página ativa."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self._page.reload(wait_until="domcontentloaded", timeout=30000)
        return self._page.url

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
        
        Args:
            selector: Seletor CSS, XPath ou Playwright (ex: '#btnLogin', 'button:has-text("Entrar")').
            wait_for: Seletor opcional para aguardar após o clique (ex: '#dashboard', 'table').
            force: Força o clique mesmo se o elemento estiver sobreposto ou bloqueado.
            button: 'left', 'right', 'middle'.
            click_count: 1 (clique simples), 2 (duplo clique).
            timeout: Tempo limite em MILISSEGUNDOS (ms) por tentativa (padrão: 5000ms = 5s).
            retries: Quantidade de tentativas se o elemento falhar no clique (padrão: 3x).
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        last_err = None

        for attempt in range(retries):
            try:
                # 1. Aguarda visibilidade do elemento
                try:
                    await self._page.wait_for_selector(selector, state="visible", timeout=timeout)
                except Exception:
                    pass

                # 2. Tenta clique nativo Playwright
                try:
                    await self._page.click(selector, force=force, button=button, click_count=click_count, timeout=timeout)
                except Exception:
                    # 3. Fallback via Locator direto
                    loc = self._page.locator(selector).first
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
                return
            except Exception as e:
                last_err = e
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
        
        Args:
            selector: Seletor do campo (ex: '#txtCPF', 'input[name="senha"]').
            text: Valor a ser preenchido (string, int, etc.).
            timeout: Tempo limite em MILISSEGUNDOS (ms) por tentativa (padrão: 5000ms = 5s).
            retries: Mínimo de 3 tentativas se o elemento não carregar ou valor não for setado.
            verify: Se True (padrão), confere obrigatoriamente se o valor do campo foi setado no DOM.
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        target_val = str(text if text is not None else "")
        last_err = None

        for attempt in range(retries):
            try:
                # 1. Aguarda visibilidade do elemento
                await self._page.wait_for_selector(selector, state="visible", timeout=timeout)
                
                # 2. Limpeza prévia
                loc = self._page.locator(selector).first
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
                        return
                    else:
                        # Fallback de digitação se a atribuição direta falhou
                        try:
                            await loc.click(force=True, timeout=1000)
                            await self._page.keyboard.press("Control+A")
                            await self._page.keyboard.press("Backspace")
                            await self._page.keyboard.type(target_val, delay=25)
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

                        actual_val2 = await loc.input_value(timeout=1000)
                        if actual_val2 == target_val or (digits_target and digits_target == re.sub(r'\D', '', str(actual_val2))):
                            return

                return
            except Exception as e:
                last_err = e
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
        
        Args:
            selector: Seletor do campo.
            text: Texto a ser digitado.
            delay: Intervalo entre teclas em MILISSEGUNDOS (ms) (padrão: 35ms).
            timeout: Tempo limite em ms (padrão: 5000ms = 5s).
            retries: Quantidade de retentativas (padrão: 3).
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        target_val = str(text if text is not None else "")
        last_err = None
        for attempt in range(retries):
            try:
                await self._page.wait_for_selector(selector, state="visible", timeout=timeout)
                loc = self._page.locator(selector).first
                await loc.click(force=True, timeout=timeout)
                await loc.type(target_val, delay=delay, timeout=timeout)
                return
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    await asyncio.sleep(0.3)
        raise RuntimeError(f"Falha ao digitar no campo '{selector}' após {retries} tentativas: {last_err}")

    async def press(self, key: str, selector: Optional[str] = None) -> None:
        """
        Pressiona uma tecla do teclado ('Enter', 'Tab', 'Escape', 'ArrowDown').
        Se selector for informado, foca no elemento antes de pressionar.
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        if selector:
            loc = self._page.locator(selector).first
            await loc.press(key)
        else:
            await self._page.keyboard.press(key)

    async def hover(self, selector: str, timeout: int = 5000) -> None:
        """Passa o mouse (hover) sobre um elemento para abrir menus dropdown e tooltips."""
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        await self._page.wait_for_selector(selector, state="visible", timeout=timeout)
        await self._page.locator(selector).first.hover(timeout=timeout)

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
        
        Args:
            selector: Seletor do <select> (ex: '#selectOrgao').
            value: Valor ('value'), texto ('label') ou índice ('index').
            timeout: Tempo limite em MILISSEGUNDOS (ms) por tentativa (padrão: 5000ms = 5s).
            retries: Mínimo de 3 tentativas se a opção ainda estiver carregando via Ajax.
            verify: Confere se a opção foi selecionada.
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        target = str(value if value is not None else "")
        last_err = None

        for attempt in range(retries):
            try:
                await self._page.wait_for_selector(selector, state="visible", timeout=timeout)
                loc = self._page.locator(selector).first
                
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
                            return selected_val
                    except Exception:
                        pass

                return target
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    await asyncio.sleep(0.3)

        raise RuntimeError(f"Falha ao selecionar opção '{target}' no seletor '{selector}' após {retries} tentativas: {last_err}")

    # -------------------------------------------------------------------------
    # Extração de Dados & Tabelas com Espera Reativa
    # -------------------------------------------------------------------------
    async def get_value(self, selector: str, timeout: int = 5000, retries: int = 3) -> str:
        """
        Obtém o valor (.value ou input_value) de um campo de formulário (<input>, <textarea>, <select>).
        Aguarda o elemento com até 3 retentativas automáticas e timeouts curtos.
        
        Args:
            selector: Seletor do campo.
            timeout: Tempo limite em MILISSEGUNDOS (ms) por tentativa (padrão: 5000ms = 5s).
            retries: Quantidade de tentativas (padrão: 3).
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        last_err = None
        for attempt in range(retries):
            try:
                await self._page.wait_for_selector(selector, state="attached", timeout=timeout)
                val = await self._page.locator(selector).first.input_value(timeout=timeout)
                return val.strip() if val is not None else ""
            except Exception as e:
                last_err = e
                try:
                    val = await self._page.locator(selector).first.evaluate("el => el ? (el.value || el.innerText || '') : null")
                    if val is not None:
                        return str(val).strip()
                except Exception:
                    pass
                if attempt < retries - 1:
                    await asyncio.sleep(0.25)
        raise RuntimeError(f"Falha ao obter valor do seletor '{selector}' após {retries} tentativas: {last_err}")

    async def get_text(self, selector: str, timeout: int = 5000, retries: int = 3) -> str:
        """
        Obtém o texto visível de um elemento com espera reativa e até 3 retentativas.
        
        Args:
            selector: Seletor do elemento.
            timeout: Tempo limite em MILISSEGUNDOS (ms) por tentativa (padrão: 5000ms = 5s).
            retries: Quantidade de tentativas (padrão: 3).
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        last_err = None
        for attempt in range(retries):
            try:
                await self.wait(selector, state="visible", timeout=timeout, retries=1)
                txt = await self._page.locator(selector).first.inner_text(timeout=timeout)
                return txt.strip() if txt else ""
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    await asyncio.sleep(0.25)
        raise RuntimeError(f"Falha ao obter texto de '{selector}' após {retries} tentativas: {last_err}")

    async def get_attribute(self, selector: str, attribute: str, timeout: int = 5000, retries: int = 3) -> Optional[str]:
        """
        Obtém o valor de um atributo HTML (ex: 'href', 'src', 'value') com espera reativa e retries.
        
        Args:
            selector: Seletor do elemento.
            attribute: Nome do atributo HTML.
            timeout: Tempo limite em MILISSEGUNDOS (ms) por tentativa (padrão: 5000ms = 5s).
            retries: Quantidade de tentativas (padrão: 3).
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        last_err = None
        for attempt in range(retries):
            try:
                await self.wait(selector, state="attached", timeout=timeout, retries=1)
                return await self._page.locator(selector).first.get_attribute(attribute, timeout=timeout)
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    await asyncio.sleep(0.25)
        raise RuntimeError(f"Falha ao obter atributo '{attribute}' de '{selector}' após {retries} tentativas: {last_err}")

    async def extract_table(self, selector: str = "table", timeout: int = 5000, retries: int = 3) -> List[Dict[str, Any]]:
        """
        Extrai qualquer tabela HTML convertendo-a para uma lista de dicionários Python:
        [{coluna1: valor, coluna2: valor}, ...] com espera reativa do elemento da tabela.
        
        Args:
            selector: Seletor da tabela (padrão: 'table').
            timeout: Tempo limite em MILISSEGUNDOS (ms) por tentativa (padrão: 5000ms = 5s).
            retries: Quantidade de tentativas para aguardar a tabela estar anexada ao DOM (padrão: 3).
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
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
        data = await self._page.evaluate(js_extract, selector)
        return data or []

    # -------------------------------------------------------------------------
    # Resolução de Captcha & OCR (Delegado para CaptchaSolver)
    # -------------------------------------------------------------------------
    async def solve_captcha(self, selector: str) -> str:
        """
        Resolve automaticamente um captcha de imagem delegando para o módulo CaptchaSolver.
        """
        if not self._page:
            raise RuntimeError("Página do navegador não inicializada.")
        return await CaptchaSolver.solve(self._page, selector)

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
        """Inspeciona o DOM da página ativa delegando para dom_inspector."""
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
# EXPORTAÇÕES PÚBLICAS (100% RETROCOMPATIBILIDADE)
# =============================================================================

__all__ = [
    "BrowserTools",
    "inspect_dom",
    "CaptchaSolver",
    "solve_captcha_image",
    "execute_code_sandbox",
    "TeeStream",
    "execute_browser_action",
    "init_browser_engine",
]
