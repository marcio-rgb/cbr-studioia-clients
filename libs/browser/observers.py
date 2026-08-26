# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - EXECUTION OBSERVERS (OBSERVER PATTERN IMPLEMENTATIONS)
  Implementações concretas de IExecutionObserver para desacoplar a camada
  de banco de dados, console de desktop e testes unitários.
=============================================================================
"""

import os
import sys
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from libs.browser.interfaces import IExecutionObserver

logger = logging.getLogger("Browser.Observers")
_db_executor = ThreadPoolExecutor(max_workers=5)


# =============================================================================
# 1. OBSERVADOR DE BANCO DE DADOS (POSTGRESQL / VPS)
# =============================================================================

def _sync_db_log_progress(message: str, run_id: int) -> None:
    try:
        from libs.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_line = f"[{timestamp}] {message}\n"
                cur.execute(
                    """
                    UPDATE webpilot_runs
                    SET log_output = COALESCE(log_output, '') || %s
                    WHERE id = %s;
                    """,
                    (log_line, run_id)
                )
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Erro ao gravar log no banco em tempo real: {e}")


def _sync_register_download_in_db(filename: str, filepath: str, run_id: int) -> None:
    try:
        from libs.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO webpilot_downloads (run_id, filename, filepath)
                    VALUES (%s, %s, %s);
                    """,
                    (run_id, filename, filepath)
                )
                conn.commit()
                logger.info(f"Download registrado no DB: {filename} para run {run_id}")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Erro ao registrar download no banco: {e}")


class DatabaseExecutionObserver(IExecutionObserver):
    """
    Observador de execução padrão no Servidor/VPS que persiste logs em tempo real
    e downloads diretamente nas tabelas webpilot_runs e webpilot_downloads.
    """

    def log_progress(self, message: str, run_id: Optional[int] = None) -> None:
        if not run_id:
            return
        _db_executor.submit(_sync_db_log_progress, message, run_id)

    def register_download(self, filename: str, filepath: str, run_id: Optional[int] = None) -> None:
        if not run_id:
            return
        _db_executor.submit(_sync_register_download_in_db, filename, filepath, run_id)


# =============================================================================
# 2. OBSERVADOR DE CONSOLE / DESKTOP (CLIENTE STANDALONE)
# =============================================================================

class ConsoleExecutionObserver(IExecutionObserver):
    """
    Observador de execução para o Cliente Desktop que exibe progresso no terminal
    sem nenhuma dependência de conexões de banco de dados.
    """

    def log_progress(self, message: str, run_id: Optional[int] = None) -> None:
        prefix = f"[RUN #{run_id}] " if run_id else ""
        print(f"ℹ️ {prefix}{message}")

    def register_download(self, filename: str, filepath: str, run_id: Optional[int] = None) -> None:
        print(f"📥 [DOWNLOAD CONCLUÍDO] Arquivo salvo em: {filepath}")


# =============================================================================
# 3. OBSERVADOR NULO (TESTES UNITÁRIOS / SILENCIAMENTO)
# =============================================================================

class NullExecutionObserver(IExecutionObserver):
    """
    Observador nulo (Null Object Pattern) que descarta eventos para execução de testes unitários.
    """

    def __init__(self):
        self.logs = []
        self.downloads = []

    def log_progress(self, message: str, run_id: Optional[int] = None) -> None:
        self.logs.append((message, run_id))

    def register_download(self, filename: str, filepath: str, run_id: Optional[int] = None) -> None:
        self.downloads.append((filename, filepath, run_id))


# =============================================================================
# 4. REGISTRY DE OBSERVADORES
# =============================================================================

class ObserverRegistry:
    _current_observer: Optional[IExecutionObserver] = None

    @classmethod
    def get_observer(cls) -> IExecutionObserver:
        if cls._current_observer is None:
            # Se libs.db estiver acessível, usa DatabaseExecutionObserver por padrão
            try:
                import psycopg
                cls._current_observer = DatabaseExecutionObserver()
            except ImportError:
                cls._current_observer = ConsoleExecutionObserver()
        return cls._current_observer

    @classmethod
    def set_observer(cls, observer: IExecutionObserver) -> None:
        cls._current_observer = observer
