import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web_app import RequestHandler, ThreadedHTTPServer


def test_http_api_endpoints():
    port = 8765
    server = ThreadedHTTPServer(("127.0.0.1", port), RequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.1)

    base_url = f"http://127.0.0.1:{port}"

    try:
        # Test GET /
        with urllib.request.urlopen(f"{base_url}/") as res:
            assert res.status == 200
            html = res.read().decode("utf-8")
            assert "Continuous Double Auction" in html
            assert "TypeSafe Cloud" in html

        # Test GET /api/state
        with urllib.request.urlopen(f"{base_url}/api/state") as res:
            assert res.status == 200
            state = json.loads(res.read().decode("utf-8"))
            assert "steps_taken" in state
            assert "max_steps" in state

        # Test POST /api/step
        req = urllib.request.Request(
            f"{base_url}/api/step",
            data=json.dumps({"dt": 1.0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as res:
            assert res.status == 200
            step_state = json.loads(res.read().decode("utf-8"))
            assert step_state["steps_taken"] >= 1

        # Test POST /api/stop
        req_stop = urllib.request.Request(
            f"{base_url}/api/stop",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_stop) as res:
            assert res.status == 200
            stop_res = json.loads(res.read().decode("utf-8"))
            assert stop_res["status"] == "stopped"

        # Test GET /api/test_connection
        with urllib.request.urlopen(f"{base_url}/api/test_connection") as res:
            assert res.status == 200
            conn = json.loads(res.read().decode("utf-8"))
            assert "tested" in conn
    finally:
        server.shutdown()
        server.server_close()
