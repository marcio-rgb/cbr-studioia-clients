import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

async def init_camoufox_headless(
    headless: bool = True,
    user_agent: Optional[str] = None,
    viewport: Optional[dict] = None
) -> Tuple[object, object, object]:
    """
    Initializes a Camoufox (Firefox C++ Anti-Detect) browser session in headless mode.
    Returns (browser, context, page) compatible with standard Playwright API.
    """
    from camoufox.async_api import AsyncCamoufox

    if viewport is None:
        viewport = {"width": 1280, "height": 800}

    logger.info(f"🦊 Inicializando motor Camoufox Headless no Servidor (headless={headless})...")

    try:
        camou_manager = AsyncCamoufox(
            headless=headless,
            humanize=True,
            locale="pt-BR",
            geoip=True
        )
        browser = await camou_manager.start()
    except Exception as geoip_err:
        logger.warning(f"⚠️ GeoIP desativado no Camoufox ({geoip_err}). Inicializando sem GeoIP...")
        camou_manager = AsyncCamoufox(
            headless=headless,
            humanize=True,
            locale="pt-BR",
            geoip=False
        )
        browser = await camou_manager.start()

    context_kwargs = {
        "viewport": viewport,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo"
    }
    if user_agent:
        context_kwargs["user_agent"] = user_agent

    context = await browser.new_context(**context_kwargs)
    page = await context.new_page()

    logger.info("✅ Camoufox Headless Server inicializado com sucesso!")
    return browser, context, page
