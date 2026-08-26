# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - CAPTCHA SOLVER MODULE
  Motor especializado na captura e resolução multicamadas de captchas visuais
  (OCR local ddddocr -> Gemini Vision gemini-2.5-flash -> API Remota CBR Agents).
=============================================================================
"""

import os
import sys
import json
import base64
import logging
import urllib.request
from typing import Any, Optional

logger = logging.getLogger("Browser.Captcha")


class CaptchaSolver:
    """
    Resolvedor de captchas multicamadas resiliente e assíncrono.
    """

    @classmethod
    async def solve(cls, page: Any, selector: str) -> str:
        """
        Resolve automaticamente um captcha de imagem localizando o elemento,
        executando OCR local (ddddocr), fallback com Gemini Vision direto
        e fallback com a API oficial do CBR Agents (/api/webpilot/solve-captcha).
        """
        if not page:
            raise RuntimeError("Página do navegador não inicializada.")

        # 1. Localiza o elemento na página com seletores flexíveis
        el = await page.query_selector(selector)
        if not el:
            common_sels = [
                selector,
                f"img{selector}",
                f"#{selector.lstrip('#')}",
                "img[id*='captcha' i]",
                "img[src*='captcha' i]",
                "#cipCaptchaImg",
                "#captchaImg"
            ]
            for s in common_sels:
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
                raise ValueError(f"Não foi possível capturar a imagem do captcha '{selector}': {e}")

        if not img_bytes or len(img_bytes) == 0:
            raise ValueError(f"Não foi possível capturar a imagem do captcha '{selector}'.")

        captcha_text = ""

        # 1. OCR local via ddddocr (se instalado na máquina)
        try:
            import ddddocr
            ocr = ddddocr.DdddOcr(show_ad=False)
            captcha_text = ocr.classification(img_bytes)
            if captcha_text:
                logger.info(f"Captcha resolvido com sucesso via OCR local (ddddocr): {captcha_text}")
        except Exception:
            pass

        # 2. Fallback Gemini Vision Local / libs.gemini (com API key de env ou DB)
        if not captcha_text:
            try:
                from libs.gemini import get_client, generate_content_with_retry
                from google.genai import types
                client = get_client("gemini-3.5-flash")
                resp = await generate_content_with_retry(
                    client=client,
                    model="gemini-3.5-flash",
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                        "Retorne APENAS os caracteres do texto do captcha nesta imagem, sem pontuações ou explicações."
                    ]
                )
                if resp and resp.text:
                    captcha_text = resp.text.strip().replace(" ", "").replace("\n", "").upper()
                    logger.info(f"Captcha resolvido via Gemini Vision: {captcha_text}")
            except Exception:
                try:
                    from google import genai
                    from google.genai import types
                    api_key = os.environ.get("GEMINI_API_KEY")
                    if api_key:
                        client = genai.Client(api_key=api_key)
                        resp = await client.aio.models.generate_content(
                            model="gemini-3.5-flash",
                            contents=[
                                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                                "Retorne APENAS os caracteres do texto do captcha nesta imagem, sem pontuações ou explicações."
                            ]
                        )
                        if resp and resp.text:
                            captcha_text = resp.text.strip().replace(" ", "").replace("\n", "").upper()
                            logger.info(f"Captcha resolvido via Google GenAI Client: {captcha_text}")
                except Exception:
                    pass

        # 3. Fallback Oficial via API Remota CBR Agents (/api/webpilot/solve-captcha)
        if not captcha_text:
            try:
                b64_img = base64.b64encode(img_bytes).decode("utf-8")
                
                # Obtém server_url e token da sessão salva (~/.cbragents/session.json) ou variáveis de ambiente
                server_url = os.environ.get("CBR_SERVER_URL") or "https://ia.creditobr.com.br"
                token = os.environ.get("CBR_AUTH_TOKEN") or ""
                
                app_session_file = os.path.expanduser("~/.cbragents/session.json")
                if os.path.exists(app_session_file):
                    try:
                        with open(app_session_file, "r", encoding="utf-8") as sf:
                            sess_data = json.load(sf)
                            if sess_data.get("server_url"):
                                server_url = sess_data.get("server_url").rstrip("/")
                            if sess_data.get("token"):
                                token = sess_data.get("token")
                    except Exception:
                        pass
                
                req_url = f"{server_url}/api/webpilot/solve-captcha"
                req_payload = json.dumps({"b64_image": b64_img, "mime_type": "image/png"}).encode("utf-8")
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "CBR-Agents-Engine/2.5"
                }
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                
                req = urllib.request.Request(req_url, data=req_payload, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as res:
                    if res.status == 200:
                        resp_dict = json.loads(res.read().decode("utf-8"))
                        captcha_text = resp_dict.get("captcha_text", "").strip()
                        if captcha_text:
                            logger.info(f"Captcha resolvido via API remota CBR Agents: {captcha_text}")
            except Exception as api_err:
                logger.warning(f"Aviso na resolução remota de captcha via API: {api_err}")

        if not captcha_text:
            raise RuntimeError("Falha ao reconhecer caracteres do captcha.")

        return captcha_text


async def solve_captcha_image(page: Any, selector: str) -> str:
    """Função utilitária direta para resolução de captcha."""
    return await CaptchaSolver.solve(page, selector)
