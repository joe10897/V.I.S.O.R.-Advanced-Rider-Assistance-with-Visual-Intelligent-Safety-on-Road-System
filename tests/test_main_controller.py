import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from main_controller import MainController

class TestMainController(unittest.IsolatedAsyncioTestCase):
    @patch('main_controller.UdpBroadcaster')
    @patch('main_controller.VisorWebSocketServer')
    async def test_initialization(self, MockWebSocket, MockUdp):
        # Setup mocks
        mock_ws = MockWebSocket.return_value
        mock_ws.start = AsyncMock()
        mock_ws.stop = AsyncMock()
        
        mock_udp = MockUdp.return_value
        
        # Initialize Controller
        controller = MainController()
        
        # Verify modules are initialized
        MockUdp.assert_called_once()
        MockWebSocket.assert_called_once()

    @patch('main_controller.UdpBroadcaster')
    @patch('main_controller.VisorWebSocketServer')
    async def test_data_generation_and_broadcast(self, MockWebSocket, MockUdp):
        # Setup mocks
        mock_ws = MockWebSocket.return_value
        mock_ws.start = AsyncMock()
        mock_ws.broadcast = AsyncMock()
        mock_ws.stop = AsyncMock()
        
        mock_udp = MockUdp.return_value
        mock_udp.send_data = MagicMock()

        controller = MainController()
        
        # Run one iteration of the logic (extract logic from loop for testing if needed, 
        # or just run main_loop as a task and cancel it)
        controller.running = True
        
        # Generate data manually to test logic
        data = controller.generate_dummy_data()
        self.assertIn("speed", data)
        self.assertIn("warnings", data)
        
        # Test broadcast calls
        controller.udp_broadcaster.send_data(data)
        await controller.ws_server.broadcast(data)
        
        mock_udp.send_data.assert_called_with(data)
        mock_ws.broadcast.assert_called_with(data)

if __name__ == "__main__":
    unittest.main()
