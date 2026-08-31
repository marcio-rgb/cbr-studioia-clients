# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER FRAME STREAMER (CENTRALIZED SCREENCAST)
  Módulo de responsabilidade única para captura, compressão JPEG e broadcast
  de frames do Playwright para os assinantes WebSocket do WebPilot Studio.
  Guiado pelas decisões inteligentes do ViewportStateObserver.
=============================================================================
"""

import base64
import logging
from typing import Optional, Dict, Any

from libs.browser.viewport_observer import viewport_observer, ViewportMode
from libs.browser.ws_server import broadcast_browser_frame, broadcast_run_frame

logger = logging.getLogger("Browser.FrameStreamer")


async def capture_and_broadcast_frame(
    page: Any,
    source_id: Optional[int] = None,
    run_id: Optional[int] = None,
    step_info: Optional[Dict[str, Any]] = None,
    quality: int = 75,
    timeout_ms: int = 3000,
    force: bool = False
) -> Optional[str]:
    """
    Captura o screenshot da página ativa em JPEG comprimido e transmite
    via WebSocket para os assinantes do WebPilotStudio e da Execução ao Vivo (/runs).
    
    Consulta o ViewportStateObserver:
    - Se Desktop Client estiver conectado, suspende captura headless e emite status.
    - Se não houver assinantes no source_id nem no run_id, suspende a captura para poupar 100% de CPU.
    - Se houver assinantes ativos ou force=True, executa a captura e transmite.
    """
    eff_run_id = run_id
    if eff_run_id is None and step_info and "run_id" in step_info:
        eff_run_id = step_info.get("run_id")
    if eff_run_id is None:
        try:
            from libs.browser.client_internal import _run_id_var
            eff_run_id = _run_id_var.get()
        except Exception:
            pass

    has_run_subscribers = eff_run_id is not None and viewport_observer.get_subscribers_count(eff_run_id) > 0
    has_source_subscribers = viewport_observer.get_subscribers_count(source_id) > 0
    mode = viewport_observer.get_mode(source_id)

    # 1. Se o Desktop Client estiver ativo, transmite apenas metadados de status sem capturar na VPS
    if mode == ViewportMode.CLIENT_ACTIVE and not force:
        logger.debug(f"Desktop Client ativo: suspendendo screenshot headless na VPS para source_id #{source_id}")
        info = dict(step_info or {})
        info["client_active"] = True
        try:
            if eff_run_id is not None:
                await broadcast_run_frame(
                    run_id=eff_run_id,
                    source_id=source_id,
                    frame_base64="",
                    url=getattr(page, "url", "") if page else "",
                    step_info=info
                )
            else:
                await broadcast_browser_frame(
                    source_id=source_id,
                    frame_base64="",
                    url=getattr(page, "url", "") if page else "",
                    step_info=info
                )
        except Exception:
            pass
        return None

    # 2. Se estiver dormente (sem assinantes no Studio nem no Run) e não for forçado, ignora screenshot (Zero CPU)
    if not has_run_subscribers and not has_source_subscribers and not force and mode == ViewportMode.HEADLESS_DORMANT:
        logger.debug(f"Modo HEADLESS_DORMANT: nenhum assinante WS para source #{source_id} / run #{eff_run_id}. Screenshot ignorado.")
        return None

    if not page:
        return None

    try:
        if hasattr(page, "is_closed") and page.is_closed():
            return None

        shot_bytes = await page.screenshot(
            type="jpeg",
            quality=quality,
            timeout=timeout_ms
        )
        b64_frame = base64.b64encode(shot_bytes).decode("utf-8")
        current_url = getattr(page, "url", "")

        # Transmite para o canal de execução específica e para o canal do Studio
        if eff_run_id is not None:
            await broadcast_run_frame(
                run_id=eff_run_id,
                source_id=source_id,
                frame_base64=b64_frame,
                url=current_url,
                step_info=step_info
            )
        else:
            await broadcast_browser_frame(
                source_id=source_id,
                frame_base64=b64_frame,
                url=current_url,
                step_info=step_info
            )
        return b64_frame
    except Exception as e:
        logger.debug(f"Falha ao capturar/transmitir frame (source_id={source_id}, run_id={eff_run_id}): {e}")
        return None
