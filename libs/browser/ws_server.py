import asyncio
import json
import logging
import websockets
from typing import Dict, Any, Optional

logger = logging.getLogger("Libs.Browser.WSServer")

_active_client_websocket = None
_client_lock = asyncio.Lock()
_pending_responses: Dict[str, asyncio.Future] = {}
_message_id_counter = 0

_studio_subscribers: Dict[int, list] = {}  # source_id -> list of websockets (passo a passo / interativo)
_run_subscribers: Dict[int, list] = {}     # run_id -> list of websockets (execuções em lote/geral)
_global_subscribers: list = []
_latest_frame_cache: Dict[int, str] = {}  # source_id -> cached payload json string
_run_frame_cache: Dict[int, str] = {}     # run_id -> cached payload json string


async def register_run_subscriber(run_id: Any, websocket: Any):
    """Registra um assinante interessado no streaming ao vivo de uma execução específica (run_id)."""
    try:
        rid = int(run_id) if run_id is not None else 0
    except (ValueError, TypeError):
        rid = 0
    if rid not in _run_subscribers:
        _run_subscribers[rid] = []
    if websocket not in _run_subscribers[rid]:
        _run_subscribers[rid].append(websocket)
    
    try:
        from libs.browser.viewport_observer import viewport_observer
        viewport_observer.notify_subscriber_joined(rid, websocket)
    except Exception:
        pass
    logger.info(f"Assinante conectado para stream da execução #{rid}")

    # Envia imediatamente o último frame em cache dessa execução
    cached_payload = _run_frame_cache.get(rid)
    if cached_payload:
        try:
            if hasattr(websocket, "send_text"):
                await websocket.send_text(cached_payload)
            elif hasattr(websocket, "send"):
                await websocket.send(cached_payload)
        except Exception:
            pass


async def unregister_run_subscriber(run_id: Any, websocket: Any):
    """Remove o assinante de uma execução específica."""
    try:
        rid = int(run_id) if run_id is not None else 0
    except (ValueError, TypeError):
        rid = 0
    if rid in _run_subscribers and websocket in _run_subscribers[rid]:
        _run_subscribers[rid].remove(websocket)
    try:
        from libs.browser.viewport_observer import viewport_observer
        viewport_observer.notify_subscriber_left(rid, websocket)
    except Exception:
        pass


async def register_studio_subscriber(source_id: Any, websocket: Any):
    """Registra um assinante interessado no streaming da sessão de desenvolvimento (source_id)."""
    try:
        sid = int(source_id) if source_id is not None else 0
    except (ValueError, TypeError):
        sid = 0
    if sid not in _studio_subscribers:
        _studio_subscribers[sid] = []
    if websocket not in _studio_subscribers[sid]:
        _studio_subscribers[sid].append(websocket)
    
    try:
        from libs.browser.viewport_observer import viewport_observer
        viewport_observer.notify_subscriber_joined(sid, websocket)
    except Exception:
        pass
    logger.info(f"Studio UI inscrito para stream da fonte #{sid}")

    # Envia imediatamente o último frame em cache (resiliência a F5 / troca de tela)
    cached_payload = _latest_frame_cache.get(sid) or _latest_frame_cache.get(0)
    if cached_payload:
        try:
            if hasattr(websocket, "send_text"):
                await websocket.send_text(cached_payload)
            elif hasattr(websocket, "send"):
                await websocket.send(cached_payload)
        except Exception:
            pass

register_step_subscriber = register_studio_subscriber


async def unregister_studio_subscriber(source_id: Any, websocket: Any):
    try:
        sid = int(source_id) if source_id is not None else 0
    except (ValueError, TypeError):
        sid = 0
    if sid in _studio_subscribers and websocket in _studio_subscribers[sid]:
        _studio_subscribers[sid].remove(websocket)
    try:
        from libs.browser.viewport_observer import viewport_observer
        viewport_observer.notify_subscriber_left(sid, websocket)
    except Exception:
        pass

unregister_step_subscriber = unregister_studio_subscriber


async def broadcast_run_frame(
    run_id: Optional[Any],
    frame_base64: str,
    url: str = "",
    step_info: Optional[dict] = None,
    source_id: Optional[Any] = None
):
    """Transmite um frame ao vivo para os assinantes de uma execução específica (run_id) e opcionalmente para o source_id."""
    rid = None
    if run_id is not None:
        try:
            rid = int(run_id)
        except (ValueError, TypeError):
            rid = None

    sid = None
    if source_id is not None:
        try:
            sid = int(source_id)
        except (ValueError, TypeError):
            sid = None

    payload = json.dumps({
        "type": "browser_frame",
        "run_id": rid,
        "source_id": sid,
        "frame": frame_base64 or "",
        "url": url,
        "step_info": step_info or {}
    })

    if rid is not None:
        _run_frame_cache[rid] = payload
    if sid is not None:
        _latest_frame_cache[sid] = payload

    targets = set()
    if rid is not None and rid in _run_subscribers:
        for ws in _run_subscribers[rid]:
            targets.add(ws)
    if sid is not None and sid in _studio_subscribers:
        for ws in _studio_subscribers[sid]:
            targets.add(ws)
    if 0 in _studio_subscribers:
        for ws in _studio_subscribers[0]:
            targets.add(ws)
    for ws in _global_subscribers:
        targets.add(ws)

    for ws in targets:
        try:
            if hasattr(ws, "send_text"):
                await ws.send_text(payload)
            elif hasattr(ws, "send"):
                await ws.send(payload)
        except Exception:
            pass


async def broadcast_browser_frame(source_id: Optional[Any], frame_base64: str, url: str = "", step_info: Optional[dict] = None):
    sid = None
    if source_id is not None:
        try:
            sid = int(source_id)
        except (ValueError, TypeError):
            sid = None

    payload = json.dumps({
        "type": "browser_frame",
        "source_id": sid,
        "frame": frame_base64 or "",
        "url": url,
        "step_info": step_info or {}
    })

    # Atualiza cache de frame mais recente para este source_id e global
    eff_sid = sid if sid is not None else 0
    _latest_frame_cache[eff_sid] = payload
    if eff_sid != 0:
        _latest_frame_cache[0] = payload

    targets = set()
    if sid is not None and sid in _studio_subscribers:
        for ws in _studio_subscribers[sid]:
            targets.add(ws)
    if 0 in _studio_subscribers and (sid is None or sid != 0):
        for ws in _studio_subscribers[0]:
            targets.add(ws)
    if sid is None:
        for sub_list in _studio_subscribers.values():
            for ws in sub_list:
                targets.add(ws)
    for ws in _global_subscribers:
        targets.add(ws)
    
    for ws in targets:
        try:
            if hasattr(ws, "send_text"):
                await ws.send_text(payload)
            elif hasattr(ws, "send"):
                await ws.send(payload)
        except Exception:
            pass

broadcast_step_frame = broadcast_browser_frame

_active_client_websocket = None
_user_client_websockets: Dict[int, Any] = {}  # user_id -> client websocket
_client_user_ids: Dict[Any, int] = {}          # client websocket -> user_id
_client_lock = asyncio.Lock()
_pending_responses: Dict[str, asyncio.Future] = {}
_message_id_counter = 0


def _get_next_id() -> str:
    global _message_id_counter
    _message_id_counter += 1
    return str(_message_id_counter)


def _extract_user_id_from_payload(data: dict) -> Optional[int]:
    uid = data.get("user_id") or data.get("uid")
    if uid is not None:
        try:
            return int(uid)
        except Exception:
            pass
    token_str = data.get("token") or data.get("access_token")
    if token_str:
        try:
            from libs import config
            import jwt
            payload = jwt.decode(token_str, config.JWT_SECRET_KEY, algorithms=["HS256"])
            token_uid = payload.get("user_id") or payload.get("id")
            if token_uid:
                return int(token_uid)
            sub = payload.get("sub")
            if sub:
                from libs.db import get_connection
                conn = get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM users WHERE email = %s;", (sub,))
                        row = cur.fetchone()
                        if row:
                            return int(row[0])
                finally:
                    conn.close()
        except Exception as e:
            logger.debug(f"Falha ao decodificar token do handshake: {e}")
    return None


async def handle_client_connection(websocket):
    global _active_client_websocket
    client_address = getattr(websocket, "remote_address", "cliente_remoto")
    logger.info(f"🟢 Cliente Playwright remoto conectado de: {client_address}")
    
    async with _client_lock:
        _active_client_websocket = websocket

    try:
        from libs.browser.viewport_observer import viewport_observer
        viewport_observer.notify_client_status(True)
    except Exception:
        pass

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                # Handshake de autenticação do cliente por user_id ou token
                if msg_type in ("handshake", "auth", "register_client"):
                    uid_int = _extract_user_id_from_payload(data)
                    if uid_int is not None:
                        async with _client_lock:
                            _user_client_websockets[uid_int] = websocket
                            _client_user_ids[websocket] = uid_int
                        logger.info(f"🟢 Cliente Playwright ({client_address}) vinculado ao usuário #{uid_int}")
                        await websocket.send(json.dumps({"type": "handshake_ack", "status": "authenticated", "user_id": uid_int}))
                    else:
                        logger.warning(f"Handshake recebido de {client_address} sem credenciais de usuário válidas.")

                msg_id = data.get("id")
                if msg_id and msg_id in _pending_responses:
                    future = _pending_responses.pop(msg_id)
                    if not future.done():
                        future.set_result(data)
                elif msg_type == "pong":
                    logger.debug("Received pong from client")
                elif msg_type == "browser_frame":
                    await broadcast_browser_frame(
                        source_id=data.get("source_id"),
                        frame_base64=data.get("frame"),
                        url=data.get("url", ""),
                        step_info=data.get("step_info")
                    )
            except Exception as parse_err:
                logger.error(f"Erro ao processar mensagem do cliente: {parse_err}")
    except websockets.exceptions.ConnectionClosed as cc:
        logger.info(f"🔴 Conexão do cliente fechada ({client_address}): {cc}")
    except Exception as e:
        logger.info(f"🔴 Conexão encerrada com erro ({client_address}): {e}")
    finally:
        async with _client_lock:
            if _active_client_websocket == websocket:
                _active_client_websocket = None
            uid_bound = _client_user_ids.pop(websocket, None)
            if uid_bound is not None:
                _user_client_websockets.pop(uid_bound, None)
                logger.info(f"🔴 Cliente do usuário #{uid_bound} desvinculado.")

        try:
            from libs.browser.viewport_observer import viewport_observer
            viewport_observer.notify_client_status(bool(_user_client_websockets or _active_client_websocket))
        except Exception:
            pass
        logger.info(f"Cliente {client_address} desconectado.")


class FastAPIWebSocketWrapper:
    def __init__(self, websocket):
        self._ws = websocket
        self.remote_address = getattr(websocket.client, "host", "fastapi_client")
    
    @property
    def open(self) -> bool:
        try:
            return self._ws.client_state.name == "CONNECTED"
        except Exception:
            return True
    
    async def send(self, data: str):
        await self._ws.send_text(data)


async def handle_fastapi_websocket(websocket):
    global _active_client_websocket
    wrapper = FastAPIWebSocketWrapper(websocket)
    client_address = wrapper.remote_address
    logger.info(f"🟢 Cliente Playwright remoto (FastAPI WSS) conectado de: {client_address}")
    
    # Extrai user_id ou token de query params se disponível (ex: /ws?user_id=1 ou /ws?token=...)
    query_params_dict = dict(websocket.query_params)
    init_uid = _extract_user_id_from_payload(query_params_dict)
    if init_uid is not None:
        async with _client_lock:
            _user_client_websockets[init_uid] = wrapper
            _client_user_ids[wrapper] = init_uid
        logger.info(f"🟢 Cliente FastAPI WSS vinculado imediatamente via query_param ao usuário #{init_uid}")

    async with _client_lock:
        _active_client_websocket = wrapper

    try:
        from libs.browser.viewport_observer import viewport_observer
        viewport_observer.notify_client_status(True)
    except Exception:
        pass

    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                # Handshake de autenticação por mensagem
                if msg_type in ("handshake", "auth", "register_client"):
                    uid_int = _extract_user_id_from_payload(data)
                    if uid_int is not None:
                        async with _client_lock:
                            _user_client_websockets[uid_int] = wrapper
                            _client_user_ids[wrapper] = uid_int
                        logger.info(f"🟢 Cliente FastAPI WSS ({client_address}) vinculado ao usuário #{uid_int}")
                        await wrapper.send(json.dumps({"type": "handshake_ack", "status": "authenticated", "user_id": uid_int}))
                    else:
                        logger.warning(f"Handshake recebido de FastAPI WSS {client_address} sem credenciais válidas.")

                msg_id = data.get("id")
                if msg_id and msg_id in _pending_responses:
                    future = _pending_responses.pop(msg_id)
                    if not future.done():
                        future.set_result(data)
                elif msg_type == "pong":
                    logger.debug("Received pong from client")
                elif msg_type == "browser_frame":
                    await broadcast_browser_frame(
                        source_id=data.get("source_id"),
                        frame_base64=data.get("frame"),
                        url=data.get("url", ""),
                        step_info=data.get("step_info")
                    )
            except Exception as parse_err:
                logger.error(f"Erro ao processar mensagem do cliente: {parse_err}")
    except Exception as cc:
        logger.info(f"🔴 Conexão do cliente FastAPI WSS fechada ({client_address}): {cc}")
    finally:
        async with _client_lock:
            if _active_client_websocket == wrapper:
                _active_client_websocket = None
            uid_bound = _client_user_ids.pop(wrapper, None)
            if uid_bound is not None:
                _user_client_websockets.pop(uid_bound, None)
                logger.info(f"🔴 Cliente do usuário #{uid_bound} desvinculado.")

        try:
            from libs.browser.viewport_observer import viewport_observer
            viewport_observer.notify_client_status(bool(_user_client_websockets or _active_client_websocket))
        except Exception:
            pass
        logger.info(f"Cliente FastAPI WSS {client_address} desconectado.")


async def start_ws_server(host: str = "0.0.0.0", port: int = 8384):
    """
    Inicia o servidor WebSocket na VPS escutando conexões de saída dos clientes.
    """
    logger.info(f"Iniciando Servidor WebSocket de Clientes na porta {port} ({host})...")
    async with websockets.serve(handle_client_connection, host, port):
        await asyncio.Future()  # Run forever


def is_client_connected(user_id: Optional[int] = None) -> bool:
    import os
    if os.getenv("FORCE_LOCAL_BROWSER") == "True":
        return False
    global _active_client_websocket, _user_client_websockets
    if user_id is not None:
        try:
            uid = int(user_id)
            ws = _user_client_websockets.get(uid)
            if ws is not None:
                try:
                    return bool(ws.open)
                except Exception:
                    return True
            # Se há pool multi-usuário e o usuário específico não está, não conecta no cliente de outro usuário
            if _user_client_websockets:
                return False
        except (ValueError, TypeError):
            return False

    # Se não especificou user_id e há pool, verifica qualquer client conectado
    if _user_client_websockets:
        for ws in _user_client_websockets.values():
            try:
                if bool(ws.open):
                    return True
            except Exception:
                return True

    if _active_client_websocket is not None:
        try:
            return bool(_active_client_websocket.open)
        except Exception:
            return True
    return False


def get_active_client_address(user_id: Optional[int] = None) -> Optional[str]:
    global _active_client_websocket, _user_client_websockets
    if user_id is not None:
        try:
            uid = int(user_id)
            ws = _user_client_websockets.get(uid)
            if ws:
                return getattr(ws, "remote_address", f"cliente_usuario_{uid}")
        except Exception:
            pass
    if not is_client_connected(user_id):
        return None
    if _user_client_websockets:
        first_ws = next(iter(_user_client_websockets.values()))
        return getattr(first_ws, "remote_address", "cliente_remoto")
    return getattr(_active_client_websocket, "remote_address", "cliente_remoto")


async def ping_client_connection(timeout: float = 4.0, user_id: Optional[int] = None) -> bool:
    """
    Envia comando leve de ping para verificar se o cliente remoto daquele usuário está respondendo.
    """
    if not is_client_connected(user_id=user_id):
        return False
    if len(_pending_responses) > 0:
        return True
    try:
        res = await execute_remote_action("evaluate", {"script": "1 + 1"}, timeout=timeout, user_id=user_id)
        return res.get("result") == 2
    except Exception as e:
        logger.warning(f"Ping client connection failed: {e}")
        return False


async def execute_remote_action(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 300.0,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Envia um comando para o cliente remoto de um usuário específico (ou default) e aguarda o resultado.
    """
    global _active_client_websocket, _user_client_websockets

    target_ws = None
    if user_id is not None:
        try:
            uid = int(user_id)
            target_ws = _user_client_websockets.get(uid)
        except Exception:
            pass

    if target_ws is None:
        target_ws = _active_client_websocket
        if target_ws is None and _user_client_websockets:
            target_ws = next(iter(_user_client_websockets.values()))

    if target_ws is None or (hasattr(target_ws, "open") and not target_ws.open):
        err_msg = f"Nenhum cliente Playwright remoto conectado para o usuário #{user_id}." if user_id else "Nenhum cliente Playwright remoto conectado no momento."
        raise RuntimeError(err_msg)

    msg_id = _get_next_id()
    payload = {
        "id": msg_id,
        "action": action,
        "params": params or {}
    }

    future = asyncio.get_running_loop().create_future()
    _pending_responses[msg_id] = future

    try:
        await target_ws.send(json.dumps(payload))
        result = await asyncio.wait_for(future, timeout=timeout)
        if result.get("status") == "error":
            raise RuntimeError(result.get("error", "Erro desconhecido no cliente remoto."))
        return result.get("result", {})
    except asyncio.TimeoutError:
        _pending_responses.pop(msg_id, None)
        raise TimeoutError(f"Tempo limite ({timeout}s) esgotado aguardando resposta do cliente para ação '{action}'.")
    except Exception as e:
        _pending_responses.pop(msg_id, None)
        raise RuntimeError(f"Falha ao executar ação remota '{action}': {e}")

