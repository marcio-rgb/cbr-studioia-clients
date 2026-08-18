import os
os.environ["PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"] = "ubuntu24.04-x64"
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
import asyncio
import json
import argparse
import sys
import base64
import websockets
from playwright.async_api import async_playwright


async def inspect_dom(page) -> str:
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

        # 2. Tenta verificar Camoufox
        try:
            print("🦊 Verificando binários antidetect do Camoufox...")
            try:
                from camoufox.pkg import download_official_browser
                download_official_browser()
            except Exception:
                subprocess.run([sys.executable, "-m", "camoufox", "fetch"], check=False)
        except Exception as camou_fetch_err:
            pass
    except Exception as e:
        print(f"⚠️ Aviso ao verificar navegadores: {e}")


async def run_client(urls: list, engine: str = "camoufox"):
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
                        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
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
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
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
                        print(f"   🎥 Quadro #{frame_counter} capturado em: {frame_path}")
                        try:
                            from PIL import Image
                            frame_files = sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir) if f.endswith(".png")])
                            if frame_files:
                                images = [Image.open(f) for f in frame_files]
                                gif_path_scratch = "scratch/test_navigation.gif"
                                gif_path_static = "static/screenshots/test_navigation.gif"
                                images[0].save(gif_path_scratch, save_all=True, append_images=images[1:], duration=600, loop=0)
                                images[0].save(gif_path_static, save_all=True, append_images=images[1:], duration=600, loop=0)
                                print(f"   🎬 GIF de navegação atualizado ({len(images)} quadros) -> {gif_path_scratch}")
                        except Exception as gif_err:
                            print(f"   ⚠️ Erro ao compilar GIF: {gif_err}")
                    except Exception as frame_err:
                        print(f"   ⚠️ Erro ao capturar quadro: {frame_err}")

                try:
                    async for message in websocket:
                        data = json.loads(message)
                        msg_id = data.get("id")
                        action = data.get("action")
                        params = data.get("params", {})

                        print(f"📩 Ação recebida da VPS [{msg_id}]: {action} -> {params}")
                        response = {"id": msg_id, "status": "success", "result": {}}

                        try:
                            if action == "goto":
                                url = params.get("url")
                                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                                response["result"] = {"url": page.url, "title": await page.title()}
                                print(f"   ✔ Navegado para: {page.url} ({await page.title()})")
                                await record_frame()

                            elif action == "click":
                                selector = params.get("selector")
                                force = params.get("force", False)
                                button = params.get("button", "left")
                                click_count = params.get("click_count", 1)
                                try:
                                    await page.click(selector, force=force, button=button, click_count=click_count, timeout=30000)
                                except Exception:
                                    print(f"   ⚠️ Tentando clique forçado em '{selector}'...")
                                    await page.click(selector, force=True, timeout=10000)
                                response["result"] = {"status": "clicked", "selector": selector}
                                print(f"   ✔ Clicou em: {selector}")
                                await record_frame()

                            elif action == "type":
                                selector = params.get("selector")
                                text = params.get("text", "")
                                await page.click(selector, force=True, timeout=5000)
                                try:
                                    await page.fill(selector, "", timeout=5000)
                                except Exception:
                                    pass
                                await page.type(selector, text, delay=50, timeout=15000)
                                
                                await page.evaluate("""(sel) => {
                                    const el = document.querySelector(sel);
                                    if (el) {
                                        el.dispatchEvent(new Event('input', { bubbles: true }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                }""", selector)
                                
                                response["result"] = {"status": "typed", "selector": selector}
                                print(f"   ✔ Digitou em {selector} com: {'[SENHA]' if 'senha' in selector.lower() or 'password' in selector.lower() else text}")
                                await record_frame()

                            elif action == "fill":
                                selector = params.get("selector")
                                text = params.get("text", "")
                                await page.fill(selector, text, timeout=30000)
                                
                                await page.evaluate("""(sel) => {
                                    const el = document.querySelector(sel);
                                    if (el) {
                                        el.dispatchEvent(new Event('input', { bubbles: true }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                }""", selector)
                                
                                response["result"] = {"status": "filled", "selector": selector}
                                print(f"   ✔ Preencheu {selector} com: {'[SENHA]' if 'senha' in selector.lower() or 'password' in selector.lower() else text}")
                                await record_frame()

                            elif action == "solve_captcha":
                                selector = params.get("selector")
                                try:
                                    el = await page.query_selector(selector)
                                    if not el:
                                        response["error"] = f"Elemento '{selector}' não encontrado."
                                    else:
                                        img_bytes = await el.screenshot()
                                        import ddddocr
                                        ocr = ddddocr.DdddOcr(show_ad=False)
                                        captcha_text = ocr.classification(img_bytes)
                                        response["result"] = {"status": "success", "captcha_text": captcha_text}
                                        print(f"   ✔ Captcha resolvido localmente via ddddocr: {captcha_text}")
                                except Exception as e:
                                    response["error"] = f"Erro ao resolver captcha localmente: {str(e)}"
                                await record_frame()

                            elif action == "press_key":
                                key = params.get("key", "Enter")
                                selector = params.get("selector")
                                if selector:
                                    try:
                                        await page.focus(selector)
                                    except Exception:
                                        pass
                                await page.keyboard.press(key)
                                response["result"] = {"status": "key_pressed", "key": key}
                                print(f"   ✔ Pressionou tecla: {key}")
                                await record_frame()

                            elif action == "mouse_move":
                                x = params.get("x", 0)
                                y = params.get("y", 0)
                                steps = params.get("steps", 5)
                                await page.mouse.move(x, y, steps=steps)
                                response["result"] = {"status": "mouse_moved", "x": x, "y": y}
                                print(f"   ✔ Mouse movido para ({x}, {y})")

                            elif action == "mouse_click_xy":
                                x = params.get("x", 0)
                                y = params.get("y", 0)
                                button = params.get("button", "left")
                                click_count = params.get("click_count", 1)
                                await page.mouse.click(x, y, button=button, click_count=click_count)
                                response["result"] = {"status": "clicked_xy", "x": x, "y": y}
                                print(f"   ✔ Clique nas coordenadas ({x}, {y})")
                                await record_frame()

                            elif action == "drag_and_drop":
                                source = params.get("source_selector") or params.get("source")
                                target = params.get("target_selector") or params.get("target")
                                await page.drag_and_drop(source, target, timeout=30000)
                                response["result"] = {"status": "dragged", "source": source, "target": target}
                                print(f"   ✔ Arrastou de {source} para {target}")
                                await record_frame()

                            elif action == "wait_for":
                                selector = params.get("selector")
                                timeout = params.get("timeout", 30000)
                                state = params.get("state", "visible")
                                await page.wait_for_selector(selector, state=state, timeout=timeout)
                                response["result"] = {"status": "found", "selector": selector}
                                print(f"   ✔ Aguardou elemento: {selector}")

                            elif action == "upload_file":
                                selector = params.get("selector")
                                file_path = params.get("file_path") or params.get("filename")
                                await page.set_input_files(selector, file_path, timeout=30000)
                                response["result"] = {"status": "uploaded", "file": file_path}
                                print(f"   ✔ Arquivo enviado para {selector}: {file_path}")

                            elif action == "download_file":
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
                                response["result"] = {"downloaded_file": download.suggested_filename, "path": save_path}
                                print(f"   ✔ Arquivo baixado: {download.suggested_filename}")

                            elif action == "inspect":
                                inspect_text = await inspect_dom(page)
                                response["result"] = {"inspect_text": inspect_text}
                                print(f"   ✔ Página inspecionada ({len(inspect_text)} caracteres)")

                            elif action == "screenshot":
                                screenshot_bytes = await page.screenshot(full_page=False)
                                response["result"] = {"b64_image": base64.b64encode(screenshot_bytes).decode('utf-8')}
                                print(f"   ✔ Captura de tela gerada ({len(screenshot_bytes)} bytes)")
                                await record_frame()

                            elif action == "hover":
                                selector = params.get("selector")
                                await page.hover(selector, timeout=30000)
                                response["result"] = {"status": "hovered", "selector": selector}
                                print(f"   ✔ Hover sobre: {selector}")
                                await record_frame()

                            elif action == "select":
                                selector = params.get("selector")
                                value = params.get("value")
                                await page.select_option(selector, value, timeout=30000)
                                response["result"] = {"status": "selected", "selector": selector, "value": value}
                                print(f"   ✔ Opção '{value}' selecionada em: {selector}")
                                await record_frame()

                            elif action == "evaluate":
                                script = params.get("script")
                                eval_res = await page.evaluate(script)
                                response["result"] = {"result": eval_res}
                                print(f"   ✔ JS executado: {eval_res}")

                            elif action == "get_html":
                                content = await page.content()
                                response["result"] = {"html": content}
                                print(f"   ✔ HTML capturado ({len(content)} caracteres)")

                            elif action == "scroll":
                                direction = params.get("direction", "down")
                                amount = params.get("amount", 500)
                                delta = amount if direction.lower() == "down" else -amount
                                await page.evaluate(f"window.scrollBy(0, {delta})")
                                response["result"] = {"status": "scrolled", "direction": direction, "amount": amount}
                                print(f"   ✔ Rolo da página ({direction} {amount}px)")
                                await record_frame()

                            elif action in ("back", "go_back"):
                                await page.go_back(wait_until='domcontentloaded', timeout=30000)
                                response["result"] = {"status": "navigated_back", "url": page.url, "title": await page.title()}
                                print(f"   ✔ Navegado de volta para: {page.url}")
                                await record_frame()

                            elif action in ("run_code", "execute_code", "eval_python"):
                                code_str = params.get("code", "")
                                print(f"   🐍 Executando snippet Python no cliente remoto...")
                                clean_code = code_str.strip()
                                
                                import io
                                import sys

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
                                        self.orig.write(s)
                                        self.buf.write(s)
                                    def flush(self):
                                        self.orig.flush()
                                        self.buf.flush()

                                original_stdout = sys.stdout
                                sys.stdout = TeeStream(original_stdout, stdout_buffer)

                                try:
                                    login_user = params.get("login_user", "")
                                    login_pass = params.get("login_pass", "")
                                    global_context = {
                                        "page": page,
                                        "context": context,
                                        "browser": browser,
                                        "playwright": p,
                                        "p": p,
                                        "asyncio": asyncio,
                                        "json": json,
                                        "set_output": set_output,
                                        "login_user": login_user,
                                        "login_pass": login_pass,
                                        "time": __import__("time"),
                                        "re": __import__("re"),
                                        "random": __import__("random")
                                    }

                                    # Se contiver 'def main', executa o script completo e chama main()
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
                                        # Envolve o snippet em uma função assíncrona com 'page', 'context', 'browser'
                                        indented = "\n".join("        " + line for line in clean_code.split('\n'))
                                        wrapper = f"""async def __snippet_runner(page, context, browser, playwright, p, asyncio, set_output, login_user, login_pass):
{indented}
        # Se uma função foi definida no snippet, executa-a automaticamente com page se necessário
        _locs = locals()
        for _k, _v in list(_locs.items()):
            if callable(_v) and _k not in ('page', 'context', 'browser', 'playwright', 'p', 'asyncio', 'set_output', 'login_user', 'login_pass') and not _k.startswith('__'):
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
                                        exec_res = await runner_func(page, context, browser, p, p, asyncio, set_output, login_user, login_pass)
                                finally:
                                    sys.stdout = original_stdout

                                captured_stdout_str = stdout_buffer.getvalue().strip()

                                # Extrair dados estruturados (retornados de set_output(), main() ou parse de stdout)
                                structured_data = captured_output if captured_output is not None else exec_res
                                
                                # Se não houver retorno explícito, tenta extrair JSON do que foi impresso via print()
                                if structured_data in (None, "Main executado", "Snippet executado") and captured_stdout_str:
                                    try:
                                        structured_data = json.loads(captured_stdout_str)
                                    except Exception:
                                        for line in captured_stdout_str.splitlines():
                                            clean_l = line.strip()
                                            if (clean_l.startswith('{') and clean_l.endswith('}')) or (clean_l.startswith('[') and clean_l.endswith(']')):
                                                try:
                                                    structured_data = json.loads(clean_l)
                                                    break
                                                except Exception:
                                                    pass

                                # Se structured_data for string e for JSON válido, decodifica para dict/list
                                if isinstance(structured_data, str) and (structured_data.strip().startswith('{') or structured_data.strip().startswith('[')):
                                    try:
                                        structured_data = json.loads(structured_data)
                                    except Exception:
                                        pass

                                response["result"] = {
                                    "status": "success",
                                    "data": structured_data if structured_data not in ("Main executado", "Snippet executado") else None,
                                    "output": str(exec_res) if exec_res is not None else "Snippet executado",
                                    "url": page.url,
                                    "title": await page.title()
                                }
                                print(f"   ✔ Snippet executado com sucesso no cliente! URL: {page.url}")
                                await record_frame()

                            else:
                                response["status"] = "error"
                                response["error"] = f"Ação desconhecida: {action}"

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
                        await browser.close()

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as conn_err:
            print(f"🔴 Conexão falhou/perdida em {target_url} ({conn_err}). Tentando próxima URL em 3 segundos...")
            url_index += 1
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️ Erro inesperado em {target_url}: {e}. Reconectando em 3 segundos...")
            url_index += 1
            await asyncio.sleep(3)

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
        
        import urllib.request
        import json
        import hashlib
        
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
    except Exception as e:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Omni Remote Client com suporte ao Camoufox Anti-Detect e Playwright")
    parser.add_argument("--url", default="", help="URL WebSocket da VPS (ex: wss://ia.creditobr.com.br/ws/remote ou ws://ia.creditobr.com.br:8384)")
    parser.add_argument("--engine", default="camoufox", choices=["camoufox", "playwright", "chromium"], help="Motor de navegação: camoufox (Firefox C++ Stealth) ou playwright")
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
            "wss://ia.creditobr.com.br/ws/remote"
        ]

    try:
        if urls_to_try:
            check_and_auto_update(urls_to_try[0])
        ensure_playwright_browsers()
        asyncio.run(run_client(urls_to_try, engine=args.engine))
    except KeyboardInterrupt:
        print("\nCliente encerrado pelo usuário.")
        sys.exit(0)
