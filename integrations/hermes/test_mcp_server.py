import importlib.util
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

spec = importlib.util.spec_from_file_location("bridge", Path(__file__).with_name("mcp_server.py"))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class BridgeTest(unittest.TestCase):
    def test_protocol_and_read_only_tools(self):
        self.assertEqual(bridge.dispatch({"method":"initialize"})["protocolVersion"], "2024-11-05")
        names = [t["name"] for t in bridge.dispatch({"method":"tools/list"})["tools"]]
        self.assertEqual(names, ["receive_support_event", "get_support_ticket"])

    def test_forbidden_tools_and_extra_arguments_are_blocked(self):
        for name, args in [("execute_sql", {"sql":"DROP TABLE policies"}), ("receive_support_event", {"message":"test"}), ("get_support_ticket", {"id":"one", "url":"https://evil.invalid"})]:
            result = bridge.dispatch({"method":"tools/call", "params":{"name":name,"arguments":args}})
            self.assertTrue(result["isError"])

    def test_receives_conflict_without_losing_identity(self):
        captured = {}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured["event"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                captured["auth"] = self.headers.get("Authorization")
                self.send_response(409); self.end_headers()
                self.wfile.write(b'{"outcome":"CONFLICT","conflictId":"conflict-one"}')
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        previous = bridge.BASE, bridge.TOKEN
        try:
            bridge.BASE = "http://127.0.0.1:" + str(server.server_port)
            bridge.TOKEN = "test-only-token"
            event = {k:"fictional-value" for k in bridge.EVENT_FIELDS}
            result, error = bridge.call_tool("receive_support_event", event)
            self.assertFalse(error); self.assertEqual(result["outcome"], "CONFLICT")
            self.assertEqual(captured["event"], event)
            self.assertEqual(captured["auth"], "Bearer test-only-token")
        finally:
            bridge.BASE, bridge.TOKEN = previous
            server.shutdown(); server.server_close(); worker.join()

if __name__ == "__main__":
    unittest.main()
