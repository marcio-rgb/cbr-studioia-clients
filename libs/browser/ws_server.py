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

_studio_subscribers: Dict[int, list] = {}  # source_id -> list of websockets
_global_subscribers: list = []

async def register_studio_subscriber(source_id: int, websocket: Any):
    if source_id not in _studio_subscribers:
        _studio_subscribers[source_id] = []
    if websocket not in _studio_subscribers[source_id]:
        _studio_subscribers[source_id].append(websocket)
    logger.info(f"Studio UI inscrito para stream da fonte #{source_id}")

async def unregister_studio_subscriber(source_id: int, websocket: Any):
    if source_id in _studio_subscribers and websocket in _studio_subscribers[source_id]:
        _studio_subscribers[source_id].remove(websocket)

async def broadcast_browser_frame(source_id: Optional[int], frame_base64: str, url: str = "", step_info: Optional[dict] = None):
    if not frame_base64:
        return
    payload = json.dumps({
        "type": "browser_frame",
        "source_id": source_id,
        "frame": frame_base64,
        "url": url,
        "step_info": step_info or {}
    })
    targets = []
    if source_id and source_id in _studio_subscribers:
        targets.extend(_studio_subscribers[source_id])
    targets.extend(_global_subscribers)
    
    for ws in list(targets):
        try:
            if hasattr(ws, "send_text"):
                await ws.send_text(payload)
            elif hasattr(ws, "send"):
                await ws.send(payload)
        except Exception:
            pass

def _get_next_id() -> str:
    global _message_id_counter
    _message_id_counter += 1
    return str(_message_id_counter)

async def handle_client_connection(websocket):
    global _active_client_websocket
    client_address = getattr(websocket, "remote_address", "cliente_remoto")
    logger.info(f"🟢 Cliente Playwright remoto conectado de: {client_address}")
    
    async with _client_lock:
        _active_client_websocket = websocket

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_id = data.get("id")
                if msg_id and msg_id in _pending_responses:
                    future = _pending_responses.pop(msg_id)
                    if not future.done():
                        future.set_result(data)
                elif data.get("type") == "pong":
                    logger.debug("Received pong from client")
                elif data.get("type") == "browser_frame":
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
    
    async with _client_lock:
        _active_client_websocket = wrapper

    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                msg_id = data.get("id")
                if msg_id and msg_id in _pending_responses:
                    future = _pending_responses.pop(msg_id)
                    if not future.done():
                        future.set_result(data)
                elif data.get("type") == "pong":
                    logger.debug("Received pong from client")
                elif data.get("type") == "browser_frame":
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
        logger.info(f"Cliente {client_address} desconectado.")

async def start_ws_server(host: str = "0.0.0.0", port: int = 8384):
    """
    Inicia o servidor WebSocket na VPS escutando conexões de saída dos clientes.
    """
    logger.info(f"Iniciando Servidor WebSocket de Clientes na porta {port} ({host})...")
    async with websockets.serve(handle_client_connection, host, port):
        await asyncio.Future()  # Run forever

def is_client_connected() -> bool:
    import os
    if os.getenv("FORCE_LOCAL_BROWSER") == "True":
        return False
    global _active_client_websocket
    if _active_client_websocket is None:
        return False
    try:
        return bool(_active_client_websocket.open)
    except Exception:
        return True

def get_active_client_address() -> Optional[str]:
    global _active_client_websocket
    if not is_client_connected():
        return None
    return getattr(_active_client_websocket, "remote_address", "cliente_remoto")

async def ping_client_connection(timeout: float = 4.0) -> bool:
    """
    Sends a lightweight ping command (evaluate 1+1) to verify that the remote client is active and responding.
    If the client is already executing a long-running action (_pending_responses is active),
    we know it is connected and actively processing, so return True immediately.
    """
    if not is_client_connected():
        return False
    if len(_pending_responses) > 0:
        return True
    try:
        res = await execute_remote_action("evaluate", {"script": "1 + 1"}, timeout=timeout)
        return res.get("result") == 2
    except Exception as e:
        logger.warning(f"Ping client connection failed: {e}")
        return False


async def execute_remote_action(action: str, params: Optional[Dict[str, Any]] = None, timeout: float = 300.0) -> Dict[str, Any]:
    """
    Envia um comando para o cliente remoto ativo e aguarda o resultado via WebSocket.
    Timeout padrão expandido para 300s (5 minutos) para permitir loops e extrações longas.
    """
    global _active_client_websocket
    if not is_client_connected():
        raise RuntimeError("Nenhum cliente Playwright remoto conectado no momento.")

    msg_id = _get_next_id()
    payload = {
        "id": msg_id,
        "action": action,
        "params": params or {}
    }

    future = asyncio.get_running_loop().create_future()
    _pending_responses[msg_id] = future

    try:
        await _active_client_websocket.send(json.dumps(payload))
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

