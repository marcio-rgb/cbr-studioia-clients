# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER TOOLS BASE (LIFECYCLE, CONTEXT & PROPERTIES)
  Classe base para o SDK BrowserTools: ciclo de vida de sessão, gestão de
  parâmetros de entrada, credenciais, downloads e streaming de frames.
=============================================================================
"""

import os
import json
import base64
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List, Tuple, Union

logger = logging.getLogger("Browser.ToolsBase")


class BrowserToolsBase:
    """
    Núcleo base do SDK BrowserTools para gerenciamento de sessão, propriedades,
    parâmetros dinâmicos e emissão de frames ao WebSocket do estúdio.
    """

    def __init__(
        self,
        page: Any = None,
        context: Any = None,
        browser: Any = None,
        playwright: Any = None,
        login_user: str = "",
        login_pass: str = "",
        params: Optional[Union[Dict[str, Any], str]] = None,
        set_output_fn: Optional[Any] = None,
        register_download_fn: Optional[Any] = None,
        source_id: Optional[int] = None
    ) -> None:
        self._page = page
        self._context = context
        self._browser = browser
        self._playwright = playwright
        self._login_user: str = str(login_user or "")
        self._login_pass: str = str(login_pass or "")
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

        self._source_id: Optional[int] = source_id
        if self._source_id is None and "source_id" in self._params:
            try:
                self._source_id = int(self._params["source_id"])
            except (ValueError, TypeError):
                pass
        if not self._source_id:
            env_sid = os.getenv("SOURCE_ID") or os.getenv("WEBPILOT_ID")
            if env_sid:
                try:
                    self._source_id = int(env_sid)
                except (ValueError, TypeError):
                    pass

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
        proxy_config: Optional[Dict[str, str]] = None,
        source_id: Optional[int] = None
    ):
        """
        Gerenciador de contexto assíncrono para inicialização, execução e encerramento
        automático do ciclo de vida do navegador Playwright com anti-bot stealth e proxy.
        """
        from playwright.async_api import async_playwright
        
        env_headless = os.getenv("HEADLESS")
        if headless is None:
            headless = env_headless.lower() in ("true", "1") if env_headless is not None else True
        
        from libs.browser.launcher import init_browser_engine

        async with async_playwright() as p:
            browser, context, page = await init_browser_engine(
                p,
                headless=headless,
                proxy_config=proxy_config
            )

            raw_params = os.environ.get("EXECUTION_PARAMS", "").strip()
            params: Dict[str, Any] = {}
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

            eff_source_id = source_id or params.get("source_id") or os.environ.get("SOURCE_ID") or os.environ.get("WEBPILOT_ID")
            if eff_source_id is not None:
                try:
                    eff_source_id = int(eff_source_id)
                except (ValueError, TypeError):
                    pass

            output_holder: Dict[str, Any] = {"data": None}
            def set_output(data: Any) -> None:
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
                set_output_fn=set_output,
                source_id=eff_source_id
            )
            tools._output_holder = output_holder

            # Sincroniza referências globais para inspeção e preview
            try:
                from libs.browser.client_internal import set_page, set_context, set_browser
                set_page(page, source_id=eff_source_id)
                set_context(context, source_id=eff_source_id)
                set_browser(browser)
            except Exception:
                pass

            try:
                await tools.broadcast_frame(step_info={"status": "INITIALIZED"})
            except Exception:
                pass

            try:
                yield tools
            finally:
                try:
                    await tools.broadcast_frame(step_info={"status": "FINISHED"})
                except Exception:
                    pass

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
    def page(self) -> Any:
        return self._page

    @page.setter
    def page(self, value: Any) -> None:
        self._page = value

    @property
    def context(self) -> Any:
        return self._context

    @context.setter
    def context(self, value: Any) -> None:
        self._context = value

    @property
    def browser(self) -> Any:
        return self._browser

    @browser.setter
    def browser(self, value: Any) -> None:
        self._browser = value

    @property
    def login_user(self) -> str:
        return self._login_user

    @property
    def login_pass(self) -> str:
        return self._login_pass

    def set_page(self, page: Any) -> None:
        self._page = page

    def get_page(self) -> Any:
        return self._page

    async def broadcast_frame(
        self,
        step_info: Optional[Dict[str, Any]] = None,
        step_index: Optional[int] = None,
        step_title: Optional[str] = None
    ) -> None:
        """Captura e transmite um frame da página ativa para o WebSocket do Studio em tempo real."""
        try:
            p = await self.ensure_active_page()
            info = dict(step_info or {})
            if step_index is not None:
                info["step_index"] = step_index
            if step_title is not None:
                info["step_title"] = step_title

            from libs.browser.frame_streamer import capture_and_broadcast_frame
            await capture_and_broadcast_frame(
                page=p,
                source_id=self._source_id,
                step_info=info
            )
        except Exception as e:
            logger.debug(f"Falha ao executar broadcast_frame no tools_base: {e}")

    async def ensure_active_page(self) -> Any:
        """Garante que self._page seja uma página aberta e válida."""
        if self._page is not None:
            try:
                if hasattr(self._page, "is_closed") and self._page.is_closed():
                    self._page = None
            except Exception:
                self._page = None

        if self._page is None and self._context is not None:
            try:
                pages = self._context.pages
                for p in reversed(pages):
                    if hasattr(p, "is_closed") and not p.is_closed():
                        self._page = p
                        break
                if self._page is None:
                    self._page = await self._context.new_page()
            except Exception as e:
                logger.warning(f"Erro ao recuperar página ativa no contexto: {e}")

        if not self._page:
            raise RuntimeError("Página do navegador não inicializada ou contexto fechado.")
        return self._page

    # -------------------------------------------------------------------------
    # Gestão de Parâmetros e Credenciais
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

    # -------------------------------------------------------------------------
    # Gestão de Saída e Downloads
    # -------------------------------------------------------------------------
    def set_output(self, data: Any) -> None:
        """Grava dados estruturados de saída, mesclando dicionários e emitindo [JSON_RESULT] em linha única."""
        if data is None:
            return
            
        # Se os dados novos forem vazios (ex: [] ou {}) e já existirem dados válidos capturados, preserva
        if not data and self._captured_output:
            return

        if isinstance(self._captured_output, dict) and isinstance(data, dict):
            self._captured_output.update(data)
            out_data = self._captured_output
        elif isinstance(self._captured_output, list) and isinstance(data, list):
            # Se for lista nova não vazia, atualiza se não vazia
            if data:
                self._captured_output = data
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
        **kwargs: Any
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
