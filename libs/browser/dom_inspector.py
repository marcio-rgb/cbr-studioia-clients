# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - DEEP DOM & IFRAMES INSPECTOR
  Módulo de varredura profunda e recursiva do DOM da página ativa e de todos
  os iframes para identificação e priorização de seletores CSS e XPath.
=============================================================================
"""

import logging
from typing import Any

logger = logging.getLogger("Browser.DOMInspector")


async def inspect_dom(page: Any) -> str:
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
