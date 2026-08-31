# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - VIEWPORT STATE OBSERVER (UNIFIED RENDERING INTELLIGENCE)
  Observador reativo do estado do viewport. Monitora:
  1. Conexão do Desktop Client (Modo Visual Local)
  2. Presença de assinantes WebSocket (Studio UI e Inspector Popup)
  3. Decisão dinâmica de captura de frames (Zero CPU em background)
=============================================================================
"""

import logging
from enum import Enum
from typing import Optional, Set, Dict, Any

logger = logging.getLogger("Browser.ViewportObserver")


class ViewportMode(str, Enum):
    CLIENT_ACTIVE = "CLIENT_ACTIVE"        # Desktop Client conectado operando localmente
    ACTIVE_STREAMING = "ACTIVE_STREAMING"  # Assinantes ativos no Studio ou Popup (Cloud Headless)
    HEADLESS_DORMANT = "HEADLESS_DORMANT"  # Sem assinantes (Execução Batch em background / Zero CPU)


class ViewportStateObserver:
    """
    Observador Singleton que centraliza as decisões de renderização do viewport.
    Evita capturas de tela desnecessárias quando não há assinantes ou quando o
    Desktop Client já está exibindo a janela nativa no computador do operador.
    """

    _instance: Optional["ViewportStateObserver"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ViewportStateObserver, cls).__new__(cls)
            cls._instance._subscribers = {}  # source_id -> Set of ws references
            cls._instance._client_connected = False
            cls._instance._popup_open = {}  # source_id -> bool
        return cls._instance

    def notify_client_status(self, connected: bool) -> None:
        """Notifica alteração de status de conexão do Desktop Client."""
        prev = self._client_connected
        self._client_connected = connected
        if prev != connected:
            logger.info(f"ViewportStateObserver: Desktop Client status alterado -> {'CONECTADO' if connected else 'DESCONECTADO'}")

    def notify_client_connected(self) -> None:
        """Convenience method para conexão do Desktop Client."""
        self.notify_client_status(True)

    def notify_client_disconnected(self) -> None:
        """Convenience method para desconexão do Desktop Client."""
        self.notify_client_status(False)

    def notify_subscriber_joined(self, source_id: Optional[int] = None, ws_ref: Optional[Any] = None) -> None:
        """Registra um novo assinante de viewport (Studio ou Popup)."""
        sid = int(source_id) if source_id is not None else 0
        if sid not in self._subscribers:
            self._subscribers[sid] = set()
        ref = ws_ref if ws_ref is not None else f"sub_{len(self._subscribers[sid]) + 1}"
        self._subscribers[sid].add(ref)
        logger.debug(f"ViewportStateObserver: Assinante conectado para source_id #{sid} (Total: {len(self._subscribers[sid])})")

    def notify_subscriber_left(self, source_id: Optional[int] = None, ws_ref: Optional[Any] = None) -> None:
        """Remove um assinante desconectado."""
        sid = int(source_id) if source_id is not None else 0
        if sid in self._subscribers:
            if ws_ref is not None and ws_ref in self._subscribers[sid]:
                self._subscribers[sid].remove(ws_ref)
            elif ws_ref is None and self._subscribers[sid]:
                self._subscribers[sid].pop()
            if not self._subscribers[sid]:
                self._subscribers.pop(sid, None)
        logger.debug(f"ViewportStateObserver: Assinante removido para source_id #{sid}")

    def notify_popup_status(self, source_id: Optional[int], is_open: bool) -> None:
        """Registra se a janela Popup do Inspector está aberta."""
        sid = int(source_id) if source_id is not None else 0
        self._popup_open[sid] = is_open

    def get_subscribers_count(self, source_id: Optional[int] = None) -> int:
        """Retorna a contagem total de assinantes para o source_id especificado."""
        sid = int(source_id) if source_id is not None else 0
        count = len(self._subscribers.get(sid, set()))
        if sid != 0 and 0 in self._subscribers:
            count += len(self._subscribers[0])
        return count

    def get_mode(self, source_id: Optional[int] = None) -> ViewportMode:
        """Determina o modo de operação do viewport para o source_id."""
        if self._client_connected:
            return ViewportMode.CLIENT_ACTIVE
        if self.get_subscribers_count(source_id) > 0:
            return ViewportMode.ACTIVE_STREAMING
        return ViewportMode.HEADLESS_DORMANT

    def should_capture_frame(self, source_id: Optional[int] = None, force: bool = False) -> bool:
        """
        Avalia se um screenshot deve ser capturado no momento.
        - Se force=True: sempre captura (ex: requisição direta do usuário).
        - Se Desktop Client conectado: não captura (suspensão na VPS).
        - Se não houver assinantes no Studio nem Popup: não captura (zero CPU).
        - Se houver assinantes ativos: captura normalmente.
        """
        if force:
            return True
        mode = self.get_mode(source_id)
        return mode == ViewportMode.ACTIVE_STREAMING


# Instância Singleton global
viewport_observer = ViewportStateObserver()
