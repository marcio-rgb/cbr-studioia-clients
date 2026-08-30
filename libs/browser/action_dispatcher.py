# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER ACTION DISPATCHER
  Roteador e despachante central de comandos RPC/WebSocket para ações do
  navegador Playwright, delegando operações para a classe BrowserTools.
=============================================================================
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("Browser.ActionDispatcher")


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
    from libs.browser.engine import BrowserTools
    from libs.browser.sandbox import execute_code_sandbox

    params = params or {}
    act = (action or "").strip().lower()

    # Garante que temos uma página aberta e ativa
    if context:
        try:
            pages = context.pages
            if page is None or (hasattr(page, "is_closed") and page.is_closed()):
                for p_cand in reversed(pages):
                    if hasattr(p_cand, "is_closed") and not p_cand.is_closed():
                        page = p_cand
                        break
                if page is None or (hasattr(page, "is_closed") and page.is_closed()):
                    page = await context.new_page()
        except Exception as e:
            logger.warning(f"Erro ao recuperar página ativa em action_dispatcher: {e}")

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
            if record_frame_fn:
                await record_frame_fn()
            return {"status": "success", "url": res_url, "title": await page.title() if page else ""}

        elif act == "click":
            selector = params.get("selector")
            force = params.get("force", False)
            button = params.get("button", "left")
            click_count = params.get("click_count", 1)
            await tools.click(selector, force=force, button=button, click_count=click_count)
            if record_frame_fn:
                await record_frame_fn()
            return {"status": "success", "action": "clicked", "selector": selector}

        elif act in ("type", "fill"):
            selector = params.get("selector")
            text = params.get("text") or params.get("value") or ""
            if act == "type":
                await tools.type(selector, text, delay=params.get("delay", 35))
            else:
                await tools.fill(selector, text)
            if record_frame_fn:
                await record_frame_fn()
            return {"status": "success", "action": "filled", "selector": selector}

        elif act == "solve_captcha":
            selector = params.get("selector")
            captcha_text = await tools.solve_captcha(selector)
            if record_frame_fn:
                await record_frame_fn()
            return {"status": "success", "captcha_text": captcha_text}

        elif act in ("press", "press_key"):
            key = params.get("key", "Enter")
            selector = params.get("selector")
            await tools.press(key, selector=selector)
            if record_frame_fn:
                await record_frame_fn()
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
            if record_frame_fn:
                await record_frame_fn()
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
            if record_frame_fn:
                await record_frame_fn()
            return {
                "status": "success",
                "b64_image": b64_str,
                "data_uri": f"data:image/png;base64,{b64_str}",
                "size_bytes": len(b64_str)
            }

        elif act == "get_value":
            selector = params.get("selector")
            val = await tools.get_value(selector, timeout=params.get("timeout", 5000))
            return {"status": "success", "value": val, "selector": selector}

        elif act == "get_text":
            selector = params.get("selector")
            txt = await tools.get_text(selector, timeout=params.get("timeout", 5000))
            return {"status": "success", "text": txt, "selector": selector}

        elif act == "get_attribute":
            selector = params.get("selector")
            attr = params.get("attribute") or params.get("attr")
            attr_val = await tools.get_attribute(selector, attr, timeout=params.get("timeout", 5000))
            return {"status": "success", "attribute": attr, "value": attr_val, "selector": selector}

        elif act == "is_visible":
            selector = params.get("selector")
            vis = await tools.is_visible(selector, timeout=params.get("timeout", 5000))
            return {"status": "success", "visible": vis, "selector": selector}

        elif act == "is_hidden":
            selector = params.get("selector")
            hid = await tools.is_hidden(selector, timeout=params.get("timeout", 5000))
            return {"status": "success", "hidden": hid, "selector": selector}

        elif act == "exists":
            selector = params.get("selector")
            ex = await tools.exists(selector)
            return {"status": "success", "exists": ex, "selector": selector}

        elif act == "is_checked":
            selector = params.get("selector")
            chk = await tools.is_checked(selector, timeout=params.get("timeout", 5000))
            return {"status": "success", "checked": chk, "selector": selector}

        elif act == "is_disabled":
            selector = params.get("selector")
            dis = await tools.is_disabled(selector, timeout=params.get("timeout", 5000))
            return {"status": "success", "disabled": dis, "selector": selector}

        elif act == "is_enabled":
            selector = params.get("selector")
            enb = await tools.is_enabled(selector, timeout=params.get("timeout", 5000))
            return {"status": "success", "enabled": enb, "selector": selector}

        elif act == "hover":
            selector = params.get("selector")
            await tools.hover(selector)
            if record_frame_fn:
                await record_frame_fn()
            return {"status": "success", "action": "hovered", "selector": selector}

        elif act == "select":
            selector = params.get("selector")
            value = params.get("value")
            await tools.select(selector, value)
            if record_frame_fn:
                await record_frame_fn()
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
            if record_frame_fn:
                await record_frame_fn()
            return {"status": "success", "action": "scrolled", "direction": direction, "amount": amount}

        elif act in ("back", "go_back"):
            if page:
                await page.go_back(wait_until='domcontentloaded', timeout=30000)
            if record_frame_fn:
                await record_frame_fn()
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
            if record_frame_fn:
                await record_frame_fn()
            return res

        return {"status": "error", "error": f"Ação '{action}' não suportada pelo motor de navegação."}

    except Exception as e:
        logger.error(f"Erro ao despachar ação '{action}': {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
