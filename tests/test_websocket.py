import unittest
import asyncio
import json
import websockets
from communication.websocket_server import VisorWebSocketServer

class TestWebSocketServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.host = "127.0.0.1"
        self.port = 8766  # Use a different port for testing
        self.server = VisorWebSocketServer(host=self.host, port=self.port)
        self.server_task = asyncio.create_task(self.server.start())
        await asyncio.sleep(0.1)  # Wait for server to start

    async def asyncTearDown(self):
        await self.server.stop()
        self.server_task.cancel()
        try:
            await self.server_task
        except asyncio.CancelledError:
            pass

    async def test_client_connection(self):
        uri = f"ws://{self.host}:{self.port}"
        async with websockets.connect(uri) as websocket:
            # Test broadcasting from server to client
            test_msg = {"status": "ok"}
            await self.server.broadcast(test_msg)
            
            response = await websocket.recv()
            self.assertEqual(json.loads(response), test_msg)

if __name__ == "__main__":
    unittest.main()
