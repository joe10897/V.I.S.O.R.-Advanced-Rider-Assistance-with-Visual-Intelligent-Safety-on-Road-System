import unittest
import json
import socket
from communication.udp_broadcaster import UdpBroadcaster

class TestUdpBroadcaster(unittest.TestCase):
    def test_instantiation(self):
        broadcaster = UdpBroadcaster(port=5005)
        self.assertEqual(broadcaster.port, 5005)

    def test_send_data(self):
        # Setup a listener to capture the broadcast
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener.bind(('', 5005))
        listener.settimeout(1.0)

        broadcaster = UdpBroadcaster(port=5005)
        test_data = {"speed": 60, "alert": "none"}
        broadcaster.send_data(test_data)

        data, addr = listener.recvfrom(1024)
        received_json = json.loads(data.decode('utf-8'))
        
        self.assertEqual(received_json, test_data)
        listener.close()

if __name__ == "__main__":
    unittest.main()
