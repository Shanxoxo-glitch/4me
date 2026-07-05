"""
Brian AI Assistant — HUD WebSocket Server
Serves the HUD frontend and pushes real-time state updates via WebSocket.
Also opens the HUD window using pywebview.
"""

import asyncio
import json
import logging
import threading
import time
import os
from pathlib import Path
from typing import Any, Set, TYPE_CHECKING

import websockets
from websockets.server import WebSocketServerProtocol
from http.server import HTTPServer, SimpleHTTPRequestHandler

if TYPE_CHECKING:
    from main import Brian

logger = logging.getLogger(__name__)

HUD_DIR   = Path(__file__).parent.parent / "brian-hud"
WS_PORT   = 9000
HTTP_PORT = 9001


class HudServer:
    """
    Runs two servers:
    1. HTTP server (port 9001) — serves brian-hud/ static files
    2. WebSocket server (port 9000) — pushes real-time updates to HUD
    Also opens pywebview window pointing to the HUD.
    """

    def __init__(self, brian: Any):
        self._brian   = brian
        self._clients: Set[WebSocketServerProtocol] = set()
        self._loop    = None
        self._queue   = asyncio.Queue()

    def broadcast(self, message: dict):
        """Thread-safe: queue a message to broadcast to all HUD clients."""
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._enqueue(message), self._loop
            )

    async def _enqueue(self, message: dict):
        await self._queue.put(message)

    async def _broadcaster(self):
        """Async task that drains the queue and sends to all connected clients."""
        while True:
            msg = await self._queue.get()
            if self._clients:
                data = json.dumps(msg)
                dead = set()
                for ws in self._clients:
                    try:
                        await ws.send(data)
                    except Exception:
                        dead.add(ws)
                self._clients -= dead

    async def _ws_handler(self, websocket: WebSocketServerProtocol):
        """Handle new WebSocket connection from HUD."""
        logger.info(f"HUD client connected: {websocket.remote_address}")
        self._clients.add(websocket)
        try:
            # Send initial state
            await websocket.send(json.dumps({
                "type":    "state",
                "state":   "idle",
                "emotion": {"name": "neutral", "color": "#4FC3F7", "orb_color": "#0288D1"},
            }))
            async for _ in websocket:
                pass  # HUD sends nothing back (read-only display)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info("HUD client disconnected.")

    async def _run_ws_server(self):
        """Start WebSocket server."""
        self._loop = asyncio.get_event_loop()
        asyncio.ensure_future(self._broadcaster())
        async with websockets.serve(self._ws_handler, "localhost", WS_PORT):
            logger.info(f"WebSocket server on ws://localhost:{WS_PORT}")
            await asyncio.Future()  # run forever

    def _run_http_server(self):
        """Serve the HUD HTML/CSS/JS files on HTTP."""
        class QuietHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(HUD_DIR), **kwargs)
            def log_message(self, format, *args):
                pass   # suppress access logs

        server = HTTPServer(("localhost", HTTP_PORT), QuietHandler)
        logger.info(f"HUD HTTP server on http://localhost:{HTTP_PORT}")
        server.serve_forever()

    def _open_hud_window(self):
        """Open the HUD in a pywebview window (always on top, no chrome)."""
        time.sleep(2.0)   # Wait for HTTP server to be ready
        try:
            import webview
            window = webview.create_window(
                title          = "BRIAN",
                url            = f"http://localhost:{HTTP_PORT}",
                width          = 420,
                height         = 680,
                x              = None,   # auto position (bottom-right via JS)
                y              = None,
                resizable      = True,
                frameless      = True,   # No OS title bar — HUD has its own
                on_top         = True,
                transparent    = True,
                background_color = "#050d1a",
            )
            webview.start(debug=False)
        except Exception as e:
            logger.warning(f"pywebview not available or failed: {e}. Open http://localhost:{HTTP_PORT} in your browser.")

    def run(self):
        """Start all HUD servers. Called from a background thread."""
        # HTTP server
        http_thread = threading.Thread(target=self._run_http_server, daemon=True, name="HUD-HTTP")
        http_thread.start()

        # HUD window
        win_thread = threading.Thread(target=self._open_hud_window, daemon=True, name="HUD-Window")
        win_thread.start()

        # WebSocket server (blocks this thread)
        asyncio.run(self._run_ws_server())
