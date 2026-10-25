import asyncio
import json
import websockets

class VisorWebSocketServer:
    """
    負責與 V.I.S.O.R. 手機 App 進行雙向通訊的 WebSocket 伺服器。
    """
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.server = None
        self.command_callback = None

    async def handler(self, websocket):
        """
        處理單一客戶端連線。
        """
        self.clients.add(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if self.command_callback:
                        # Ensure callback is awaited if it's async
                        if asyncio.iscoroutinefunction(self.command_callback):
                            await self.command_callback(data)
                        else:
                            self.command_callback(data)
                except json.JSONDecodeError:
                    print(f"Received non-JSON from App: {message}")
        except websockets.exceptions.ConnectionClosedError:
            pass
        finally:
            self.clients.remove(websocket)

    async def broadcast(self, data: dict):
        """
        將數據廣播給所有連線中的客戶端。
        """
        if not self.clients:
            return
        
        message = json.dumps(data)
        await asyncio.gather(
            *[client.send(message) for client in self.clients],
            return_exceptions=True
        )

    def start(self):
        """
        啟動伺服器 (返回 serve 物件以便於 async with 使用)。
        支援 socket reuse_address / reuse_port，避免服務快速重啟時 [errno 98] address already in use
        """
        import socket
        kwargs = {"reuse_address": True}
        if hasattr(socket, "SO_REUSEPORT"):
            kwargs["reuse_port"] = True
        try:
            return websockets.serve(self.handler, self.host, self.port, **kwargs)
        except TypeError:
            return websockets.serve(self.handler, self.host, self.port)

    async def stop(self):
        """
        停止伺服器。
        """
        if self.server:
            self.server.close()
            await self.server.wait_closed()
