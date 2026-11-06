"""VPS bridge: private inference and a restricted support ingress, never master API."""
import hmac
import http.client
import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONTAINER = "hermes-agent-gj42-hermes-agent-1"
UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
LIMIT = threading.BoundedSemaphore(2)
SECRETS = json.loads(Path("/etc/kipper-triagem/bridge.json").read_text()) if __name__ == "__main__" else {}


def backend(method, path, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", 18080, timeout=350)
    try:
        connection.request(method, path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, response.read(1_000_001)
    finally:
        connection.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log bodies, Authorization or transport identifiers.

    def send_json(self, status, data):
        payload = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        inference = self.server.server_address[0] == "127.0.0.1"
        expected_ip = "127.0.0.1" if inference else SECRETS["container_ip"]
        key = SECRETS["ai_key" if inference else "ingress_key"]
        if self.client_address[0] != expected_ip or not hmac.compare_digest(
                self.headers.get("Authorization", ""), "Bearer " + key):
            return self.send_json(403, {"error": "Forbidden"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 100_000:
                return self.send_json(413, {"error": "Too large"})
            data = self.rfile.read(length)
            if inference:
                if method != "POST" or self.path != "/v1/chat/completions":
                    return self.send_json(404, {})
                request = json.loads(data)
                if len(request["tools"]) != 1 or request["tools"][0]["function"]["name"] != "consult_policy":
                    return self.send_json(400, {"error": "Unsupported tool"})
                if not LIMIT.acquire(blocking=False):
                    return self.send_json(429, {"error": "Busy"})
                try:
                    result = subprocess.run([
                        "/usr/bin/docker", "exec", "-i", "--user", "10000:10000",
                        "-e", "HERMES_HOME=/opt/data/profiles/kipper-triagem",
                        "-e", "PYTHONPATH=/opt/hermes:/opt/hermes/.venv/lib/python3.14/site-packages",
                        CONTAINER, "/opt/hermes/.venv/bin/python", "/opt/kipper-triagem-runtime/ai_worker.py"
                    ], input=data, capture_output=True, timeout=53, check=True)
                    response = json.loads(result.stdout)
                    if "choices" not in response:
                        raise ValueError()
                    return self.send_json(200, response)
                finally:
                    LIMIT.release()
            if method == "POST" and self.path == "/api/events":
                event = json.loads(data)
                if event.get("source") != "whatsapp-kipper":
                    return self.send_json(400, {"error": "Unsupported source"})
                return self.send_json(*backend(method, self.path, data))
            match = re.fullmatch(r"/api/tickets/(" + UUID + r")(/process)?", self.path)
            if not match or (method == "POST") != bool(match[2]):
                return self.send_json(404, {})
            status, detail = backend("GET", "/api/tickets/" + match[1])
            if status != 200 or json.loads(detail)["ticket"]["source"] != "whatsapp-kipper":
                return self.send_json(404, {})
            return self.send_json(*backend(method, self.path, data if method == "POST" else None))
        except Exception:
            self.send_json(502, {"error": "Private integration unavailable; query state before retrying"})


if __name__ == "__main__":
    ingress = ThreadingHTTPServer((SECRETS["gateway_ip"], 18081), Handler)
    threading.Thread(target=ingress.serve_forever, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", 18082), Handler).serve_forever()
