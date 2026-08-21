# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - REMOTE PLAYWRIGHT CLIENT (STANDALONE DESKTOP CLIENT)
  Cliente autônomo de automação para execução na máquina do usuário (Linux / Windows).
  Totalmente autocontido: executa Playwright, Camoufox Stealth e Sandbox sem dependências do backend.
=============================================================================
"""

import os
import sys
import io
import json
import base64
import asyncio
import inspect
import argparse
import time
import re
import random
import urllib.request
import hashlib
from typing import Optional, Dict, Any, Tuple, Union

# Limpa bloqueio de diretório se configurado incorretamente
if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == "0":
    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)

try:
    import websockets
except ImportError:
    print("❌ Pacote 'websockets' não encontrado. Instale com: pip install websockets")
    sys.exit(1)

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Pacote 'playwright' não encontrado. Instale com: pip install playwright && playwright install")
    sys.exit(1)

# =============================================================================
# SHIM DE COMPATIBILIDADE RETROATIVA (MOCK DO PACOTE LIBS PARA CLIENTE STANDALONE)
# =============================================================================
import types
if "libs" not in sys.modules:
    _libs_mod = types.ModuleType("libs")
    _browser_mod = types.ModuleType("libs.browser")
    _tools_mod = types.ModuleType("libs.browser.tools")
    _tools_mod.set_page = lambda p: None
    _tools_mod.get_page = lambda: None
    _tools_mod.get_downloaded_file = lambda: None
    _tools_mod.db_log_progress = lambda msg: None
    _browser_mod.tools = _tools_mod
    _libs_mod.browser = _browser_mod
    sys.modules["libs"] = _libs_mod
    sys.modules["libs.browser"] = _browser_mod
    sys.modules["libs.browser.tools"] = _tools_mod


async def inspect_dom(page) -> str:
    """
    Inspeciona o DOM da página ativa e de todos os iframes de forma profunda e recursiva.
    Gera seletores CSS prioritários (:has-text, IDs, names, aria-labels) e XPath correspondente.
    """
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

        frames = page.frames
        if len(frames) > 1:
            output.append(f"IFRAMES DETECTADOS NA PÁGINA: {len(frames) - 1}")

        all_elements = []
        for i, frame in enumerate(frames):
            frame_name = "main" if i == 0 else f"frame_{i} ({frame.url})"
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
# 2. ADAPTADOR DE FERRAMENTAS PARA SCRIPTS PROCEDURAIS (TOOLS STANDALONE)
# =============================================================================

class StandaloneTools:
    """Emulador de libs.browser.tools para compatibilidade com scripts compilados."""
    def __init__(self, page=None):
        self._page = page
        self._downloaded = None

    def set_page(self, page):
        self._page = page

    def get_page(self):
        return self._page

    def get_downloaded_file(self):
        return self._downloaded


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
    extra_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executa snippets ou scripts completos de código Python Playwright no contexto ativo da página,
    capturando stdout e chamadas a set_output().
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
    tools_adapter = StandaloneTools(page)

    try:
        global_context = {
            "page": page,
            "context": context,
            "browser": browser,
            "playwright": p_obj,
            "p": p_obj,
            "tools": tools_adapter,
            "asyncio": asyncio,
            "json": json,
            "set_output": set_output,
            "login_user": login_user,
            "login_pass": login_pass,
            "params": (extra_context or {}).get("params", {}),
            "time": time,
            "re": re,
            "random": random,
            "os": os,
            "sys": sys
        }
        if extra_context:
            global_context.update(extra_context)

        # Se contiver 'async def main' ou 'def main', executa a definição e invoca main()
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
            # Envolve o snippet em uma função assíncrona recebendo page, context, browser
            indented = "\n".join("        " + line for line in clean_code.split('\n'))
            wrapper = f"""async def __snippet_runner(page, context, browser, playwright, p, tools, asyncio, set_output, login_user, login_pass, params):
{indented}
        _locs = locals()
        for _k, _v in list(_locs.items()):
            if callable(_v) and _k not in ('page', 'context', 'browser', 'playwright', 'p', 'tools', 'asyncio', 'set_output', 'login_user', 'login_pass', 'params') and not _k.startswith('__'):
                try:
                    import inspect
                    sig = inspect.signature(_v)
                    params_count = len(sig.parameters)
                    if asyncio.iscoroutinefunction(_v):
                        _fn_res = await (_v(page) if params_count >= 1 else _v())
                    else:
                        _fn_res = _v(page) if params_count >= 1 else _v()
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
                page, context, browser, p_obj, p_obj, tools_adapter, asyncio, set_output,
                login_user, login_pass, global_context.get("params", {})
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
        "logs": stdout_buffer.getvalue()
    }


# =============================================================================
# 4. DESPACHANTE DE AÇÕES BROWSER (PARIDADE TOTAL VISUAL & INTERNAL)
# =============================================================================

async def execute_browser_action(
    page,
    context,
    browser,
    p_obj,
    action: str,
    params: Optional[Dict[str, Any]] = None,
    record_frame_fn=None,
    set_output_fn=None
) -> Dict[str, Any]:
    """
    Despachante de ações Playwright para o modo visual no cliente desktop.
    """
    params = params or {}
    act = (action or "").strip().lower()

    if act == "goto":
        url = params.get("url") or params.get("target_url")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "url": page.url, "title": await page.title()}

    elif act == "click":
        selector = params.get("selector")
        force = params.get("force", False)
        button = params.get("button", "left")
        click_count = params.get("click_count", 1)
        try:
            await page.click(selector, force=force, button=button, click_count=click_count, timeout=20000)
        except Exception:
            try:
                await page.click(selector, force=True, timeout=8000)
            except Exception:
                await page.evaluate("(sel) => document.querySelector(sel)?.click()", selector)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "clicked", "selector": selector}

    elif act in ("type", "fill"):
        selector = params.get("selector")
        text = str(params.get("text") or params.get("value") or "")
        try:
            await page.click(selector, force=True, timeout=5000)
        except Exception:
            pass
        try:
            await page.fill(selector, "", timeout=5000)
        except Exception:
            pass
        
        if act == "type":
            await page.type(selector, text, delay=35, timeout=15000)
        else:
            await page.fill(selector, text, timeout=30000)

        # Dispara eventos de reatividade em SPAs (Vue/React/Angular)
        await page.evaluate("""(sel) => {
            const el = document.querySelector(sel);
            if (el) {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            }
        }""", selector)

        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "filled", "selector": selector}

    elif act == "solve_captcha":
        selector = params.get("selector")
        el = await page.query_selector(selector)
        if not el:
            return {"status": "error", "error": f"Elemento '{selector}' não encontrado para resolução de captcha."}
        img_bytes = await el.screenshot()
        
        captcha_text = ""
        # 1. Tenta ddddocr local
        try:
            import ddddocr
            ocr = ddddocr.DdddOcr(show_ad=False)
            captcha_text = ocr.classification(img_bytes)
        except Exception:
            pass

        # 2. Fallback para Gemini Vision OCR se ddddocr não estiver instalado
        if not captcha_text:
            try:
                api_key = os.environ.get("GEMINI_API_KEY")
                if api_key:
                    from google import genai
                    from google.genai import types
                    client = genai.Client(api_key=api_key)
                    resp = await client.aio.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[
                            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                            "Retorne APENAS os caracteres do texto do captcha nesta imagem, sem pontuações ou explicações adicionais."
                        ]
                    )
                    captcha_text = resp.text.strip().replace(" ", "").replace("\n", "")
            except Exception:
                pass

        if not captcha_text:
            return {"status": "error", "error": "Falha ao resolver captcha com OCR local e multimodal."}

        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "captcha_text": captcha_text}

    elif act in ("press", "press_key"):
        key = params.get("key", "Enter")
        selector = params.get("selector")
        if selector:
            try: await page.focus(selector)
            except Exception: pass
        await page.keyboard.press(key)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "key_pressed", "key": key}

    elif act == "mouse_move":
        x = params.get("x", 0)
        y = params.get("y", 0)
        steps = params.get("steps", 5)
        await page.mouse.move(x, y, steps=steps)
        return {"status": "success", "action": "mouse_moved", "x": x, "y": y}

    elif act == "mouse_click_xy":
        x = params.get("x", 0)
        y = params.get("y", 0)
        button = params.get("button", "left")
        click_count = params.get("click_count", 1)
        await page.mouse.click(x, y, button=button, click_count=click_count)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "clicked_xy", "x": x, "y": y}

    elif act == "drag_and_drop":
        source = params.get("source_selector") or params.get("source")
        target = params.get("target_selector") or params.get("target")
        await page.drag_and_drop(source, target, timeout=30000)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "dragged", "source": source, "target": target}

    elif act == "wait_for":
        selector = params.get("selector")
        timeout = params.get("timeout", 30000)
        state = params.get("state", "visible")
        await page.wait_for_selector(selector, state=state, timeout=timeout)
        return {"status": "success", "action": "found", "selector": selector}

    elif act == "upload_file":
        selector = params.get("selector")
        file_path = params.get("file_path") or params.get("filename")
        await page.set_input_files(selector, file_path, timeout=30000)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "uploaded", "file": file_path}

    elif act == "download_file":
        selector = params.get("selector")
        async with page.expect_download(timeout=60000) as download_info:
            try:
                await page.click(selector, force=True, timeout=30000)
            except Exception:
                await page.evaluate(f"document.querySelector('{selector}')?.click()")
        download = await download_info.value
        os.makedirs("static/downloads", exist_ok=True)
        save_path = os.path.join("static/downloads", download.suggested_filename)
        await download.save_as(save_path)
        return {"status": "success", "downloaded_file": download.suggested_filename, "path": save_path}

    elif act in ("inspect", "get_dom", "inspect_dom"):
        inspect_text = await inspect_dom(page)
        return {"status": "success", "inspect_text": inspect_text}

    elif act == "screenshot":
        selector = params.get("selector") if params else None
        full_page = bool(params.get("full_page", False)) if params else False
        if selector:
            el = page.locator(selector).first
            await el.wait_for(state="visible", timeout=10000)
            screenshot_bytes = await el.screenshot()
        else:
            screenshot_bytes = await page.screenshot(full_page=full_page)
        b64_str = base64.b64encode(screenshot_bytes).decode('utf-8')
        if record_frame_fn: await record_frame_fn()
        return {
            "status": "success",
            "b64_image": b64_str,
            "data_uri": f"data:image/png;base64,{b64_str}",
            "size_bytes": len(screenshot_bytes),
            "selector": selector
        }

    elif act == "hover":
        selector = params.get("selector")
        await page.hover(selector, timeout=30000)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "hovered", "selector": selector}

    elif act == "select":
        selector = params.get("selector")
        value = params.get("value")
        await page.select_option(selector, value, timeout=30000)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "selected", "selector": selector, "value": value}

    elif act == "evaluate":
        script = params.get("script") or params.get("js_code")
        eval_res = await page.evaluate(script)
        return {"status": "success", "result": eval_res}

    elif act == "get_html":
        content = await page.content()
        return {"status": "success", "html": content}

    elif act == "scroll":
        direction = params.get("direction", "down")
        amount = params.get("amount", 500)
        delta = amount if direction.lower() == "down" else -amount
        await page.evaluate(f"window.scrollBy(0, {delta})")
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "scrolled", "direction": direction, "amount": amount}

    elif act in ("back", "go_back"):
        await page.go_back(wait_until='domcontentloaded', timeout=30000)
        if record_frame_fn: await record_frame_fn()
        return {"status": "success", "action": "navigated_back", "url": page.url, "title": await page.title()}

    elif act in ("run_code", "execute_code", "eval_python"):
        code_str = params.get("code", "")
        login_user = params.get("login_user", "")
        login_pass = params.get("login_pass", "")
        res = await execute_code_sandbox(page, context, browser, p_obj, code_str, login_user, login_pass, params)
        if record_frame_fn: await record_frame_fn()
        return res

    return {"status": "error", "error": f"Ação '{action}' não suportada pelo motor de navegação."}


# =============================================================================
# 5. GERENCIAMENTO DE NAVEGADORES E DEPENDÊNCIAS PLAYWRIGHT
# =============================================================================

def ensure_playwright_browsers():
    try:
        import subprocess
        print("🔍 Verificando navegadores e dependências (Chromium e Camoufox)...")
        # 1. Tenta instalar Chromium via driver embutido do Playwright
        try:
            from playwright._impl._driver import compute_driver_executable
            driver_executable, driver_env = compute_driver_executable()
            subprocess.run([str(driver_executable), "install", "chromium"], env=driver_env, check=False)
        except Exception:
            try:
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
            except Exception:
                pass

        # 2. Tenta verificar Camoufox se disponível
        try:
            from camoufox.pkg import download_official_browser
            download_official_browser()
        except Exception:
            try:
                subprocess.run([sys.executable, "-m", "camoufox", "fetch"], check=False)
            except Exception:
                pass
    except Exception as e:
        print(f"⚠️ Aviso ao verificar navegadores: {e}")


# =============================================================================
# 6. CICLO DE VIDA DO CLIENTE WEBSOCKET
# =============================================================================

async def run_client(urls: list, engine: str = "chromium"):
    print("========================================================")
    print("  Omni Remote Client (Outbound Connection)")
    print(f"  Motor Selecionado: {engine.upper()}")
    print(f"  URLs de Conexão: {', '.join(urls)}")
    print("========================================================")
    print("")

    url_index = 0
    while True:
        target_url = urls[url_index % len(urls)]
        try:
            print(f"🔗 Conectando ao servidor VPS em {target_url}...")
            async with websockets.connect(target_url, ping_interval=None) as websocket:
                print(f"✅ Conectado com sucesso ao servidor VPS em {target_url}! Aguardando missões...")

                browser = None
                context = None
                page = None
                p = None

                if engine.lower() == "camoufox":
                    try:
                        from camoufox.async_api import AsyncCamoufox
                        print("🦊 Inicializando motor Camoufox Anti-Detect (Firefox C++ Stealth)...")
                        try:
                            camou_manager = AsyncCamoufox(
                                headless=False,
                                humanize=True,
                                locale="pt-BR",
                                geoip=True
                            )
                            browser = await camou_manager.start()
                        except Exception as geoip_err:
                            print(f"⚠️ GeoIP desativado no Camoufox ({geoip_err}). Inicializando sem GeoIP...")
                            camou_manager = AsyncCamoufox(
                                headless=False,
                                humanize=True,
                                locale="pt-BR",
                                geoip=False
                            )
                            browser = await camou_manager.start()

                        context = await browser.new_context(
                            viewport={"width": 1280, "height": 800},
                            locale="pt-BR",
                            timezone_id="America/Sao_Paulo"
                        )
                        page = await context.new_page()
                        print("✅ Camoufox inicializado com sucesso!")
                    except Exception as camou_err:
                        print(f"⚠️ Não foi possível iniciar o Camoufox ({camou_err}). Alternando para Chromium Stealth...")
                        browser = None

                if browser is None:
                    print("🌐 Inicializando motor Chromium Stealth...")
                    p = await async_playwright().start()
                    stealth_args = [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                        "--window-size=1280,800",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-extensions"
                    ]
                    browser = await p.chromium.launch(
                        headless=False,
                        args=stealth_args
                    )
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        locale="pt-BR",
                        timezone_id="America/Sao_Paulo",
                        permissions=[
                            "geolocation",
                            "notifications",
                            "camera",
                            "microphone",
                            "clipboard-read",
                            "clipboard-write",
                            "accelerometer",
                            "gyroscope",
                            "magnetometer"
                        ],
                        device_scale_factor=1,
                        has_touch=False,
                        is_mobile=False
                    )
                    
                    stealth_js = """
                    (() => {
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                        Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
                        window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                        const originalQuery = window.navigator.permissions ? window.navigator.permissions.query : null;
                        if (originalQuery) {
                            window.navigator.permissions.query = (parameters) => (
                                parameters.name === 'notifications' ?
                                    Promise.resolve({ state: Notification.permission }) :
                                    originalQuery(parameters)
                            );
                        }
                    })();
                    """
                    await context.add_init_script(stealth_js)
                    page = await context.new_page()

                frames_dir = "scratch/frames"
                os.makedirs(frames_dir, exist_ok=True)
                os.makedirs("static/screenshots", exist_ok=True)
                frame_counter = 0

                async def record_frame():
                    nonlocal frame_counter
                    try:
                        frame_counter += 1
                        frame_path = os.path.join(frames_dir, f"frame_{frame_counter:04d}.png")
                        await page.screenshot(path=frame_path, full_page=False)
                    except Exception:
                        pass

                try:
                    async for message in websocket:
                        data = json.loads(message)
                        msg_id = data.get("id")
                        action = data.get("action")
                        params = data.get("params", {})

                        print(f"📩 Ação recebida da VPS [{msg_id}]: {action}")
                        response = {"id": msg_id, "status": "success", "result": {}}

                        try:
                            action_res = await execute_browser_action(
                                page, context, browser, p, action, params, record_frame_fn=record_frame
                            )
                            if action_res.get("status") == "error":
                                response["status"] = "error"
                                response["error"] = action_res.get("error")
                            else:
                                response["result"] = action_res
                                print(f"   ✔ Ação '{action}' executada com sucesso.")

                        except Exception as action_err:
                            print(f"⚠️ Erro ao executar ação '{action}': {action_err}")
                            response["status"] = "error"
                            response["error"] = str(action_err)

                            # Auto-recovery: Se o navegador ou página foi fechado, força reconexão/reinício da sessão
                            err_msg = str(action_err).lower()
                            if "closed" in err_msg or "target page" in err_msg:
                                print("⚠️ Detectado que o navegador ou a página foi fechada. Reiniciando sessão...")
                                raise RuntimeError("Navegador fechado localmente")

                        await websocket.send(json.dumps(response))

                finally:
                    print("Fechando navegador local...")
                    if browser:
                        try: await browser.close()
                        except Exception: pass
                    if p:
                        try: await p.stop()
                        except Exception: pass

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as conn_err:
            print(f"🔴 Conexão falhou/perdida em {target_url} ({conn_err}). Tentando próxima URL em 3 segundos...")
            url_index += 1
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️ Erro inesperado em {target_url}: {e}. Reconectando em 3 segundos...")
            url_index += 1
            await asyncio.sleep(3)


# =============================================================================
# 7. AUTO-ATUALIZAÇÃO DO CÓDIGO FONTE DO CLIENTE A PARTIR DA VPS
# =============================================================================

def check_and_auto_update(vps_url: str):
    """
    Compara o hash MD5 e tamanho do script local com o servidor VPS (/api/client/version).
    Se houver divergência, baixa a nova versão e reinicia o cliente automaticamente.
    """
    try:
        http_base = vps_url.replace("wss://", "https://").replace("ws://", "http://")
        if "/ws" in http_base:
            http_base = http_base.split("/ws")[0]
        
        version_url = f"{http_base}/api/client/version"
        download_url = f"{http_base}/api/client/download/remote_client.py"
        
        req = urllib.request.Request(version_url, headers={'User-Agent': 'OmniClientAutoUpdater'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                remote_hash = data.get("hash")
                remote_size = data.get("size")
                
                current_file = os.path.abspath(__file__)
                with open(current_file, "rb") as f:
                    local_content = f.read()
                local_hash = hashlib.md5(local_content).hexdigest()
                local_size = len(local_content)
                
                if remote_hash and (remote_hash != local_hash or remote_size != local_size):
                    print("🔄 [AUTO-UPDATER] Nova versão do cliente detectada na VPS!")
                    print(f"   Hash Local:  {local_hash[:8]} ({local_size} bytes)")
                    print(f"   Hash Remoto: {remote_hash[:8]} ({remote_size} bytes)")
                    print("⏬ Baixando código remote_client.py atualizado da VPS...")
                    
                    dl_req = urllib.request.Request(download_url, headers={'User-Agent': 'OmniClientAutoUpdater'})
                    with urllib.request.urlopen(dl_req, timeout=8) as dl_resp:
                        if dl_resp.status == 200:
                            new_code = dl_resp.read()
                            with open(current_file, "wb") as f:
                                f.write(new_code)
                            print("✅ [AUTO-UPDATER] Código do cliente atualizado com sucesso! Reiniciando cliente...")
                            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        pass


# =============================================================================
# 8. ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CBR Agents Desktop Remote Client")
    parser.add_argument("--url", default="", help="URL WebSocket da VPS (ex: wss://ia.creditobr.com.br/ws ou ws://localhost:8384)")
    parser.add_argument("--engine", default="chromium", choices=["chromium", "camoufox", "playwright"], help="Motor de navegação: chromium (padrão) ou camoufox")
    args = parser.parse_args()

    urls_to_try = []
    if args.url:
        urls_to_try.append(args.url)
        if "localhost" in args.url or "127.0.0.1" in args.url:
            urls_to_try.append("ws://localhost:8384")
            urls_to_try.append("ws://localhost:8080/ws")
        else:
            if args.url != "wss://ia.creditobr.com.br/ws":
                urls_to_try.append("wss://ia.creditobr.com.br/ws")
    else:
        urls_to_try = [
            "wss://ia.creditobr.com.br/ws",
            "ws://ia.creditobr.com.br:8384",
            "ws://localhost:8384"
        ]

    try:
        if urls_to_try:
            check_and_auto_update(urls_to_try[0])
        ensure_playwright_browsers()
        asyncio.run(run_client(urls_to_try, engine=args.engine))
    except KeyboardInterrupt:
        print("\nCliente encerrado pelo usuário.")
        sys.exit(0)
