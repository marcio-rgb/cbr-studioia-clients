# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER SANDBOX RUNNER
  Executor seguro de snippets de código Python no contexto do navegador ativo,
  com captura em tempo real de stdout via TeeStream e extração de resultados.
=============================================================================
"""

import os
import sys
import io
import json
import asyncio
import time
import re
import random
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("Browser.Sandbox")


class TeeStream:
    """
    Duplica a saída de stdout para o console original e para um buffer StringIO em memória.
    """
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
    from libs.browser.engine import BrowserTools

    clean_code = code_str.strip()
    captured_output = getattr(page, "_accumulated_output", None) if page else None

    def set_output(data):
        nonlocal captured_output
        if data is None:
            return
        if page:
            if not hasattr(page, "_accumulated_output") or page._accumulated_output is None:
                try:
                    page._accumulated_output = dict(data) if isinstance(data, dict) else data
                except Exception:
                    page._accumulated_output = data
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
            import textwrap
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
                    if asyncio.iscoroutinefunction(_v):
                        _fn_res = await (_v(tools) if params_count >= 1 else _v())
                    else:
                        _fn_res = _v(tools) if params_count >= 1 else _v()
                    if _fn_res is not None:
                        set_output(_fn_res)
                        return _fn_res
                except Exception:
                    pass
        for _v_key in ('resultado', 'result', 'output', 'data', 'dados', 'extracted_data', 'final_result', 'dados_extraidos', 'contratos', 'margem', 'res'):
            if _v_key in _locs and _locs[_v_key] is not None:
                set_output(_locs[_v_key])
                return _locs[_v_key]
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
        "json_result": structured_data,
        "logs": stdout_buffer.getvalue(),
        "downloaded_files": tools_instance.get_downloaded_files()
    }
