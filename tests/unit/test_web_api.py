"""Unit tests for spec-eng web API server."""

from __future__ import annotations

import json
import socket
import shutil
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from spec_eng.web_api import WorkflowHandler


def _setup_project(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    (tmp_path / "specs").mkdir(parents=True)
    shutil.copy(repo / "specs" / "vocab.yaml", tmp_path / "specs" / "vocab.yaml")
    shutil.copy(repo / "tests" / "fixtures" / "dual-spec-sample.txt", tmp_path / "specs" / "sample.txt")


def _request(method: str, url: str, payload: dict | None = None) -> dict:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def test_web_api_health_compile_and_interrogate(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    host = "127.0.0.1"
    sock = socket.socket()
    sock.bind((host, 0))
    port = sock.getsockname()[1]
    sock.close()

    WorkflowHandler.project_root = tmp_path
    server = ThreadingHTTPServer((host, port), WorkflowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        health = _request("GET", f"http://{host}:{port}/health")
        assert health["ok"] is True

        compiled = _request(
            "POST",
            f"http://{host}:{port}/compile",
            {"input_path": "specs/sample.txt"},
        )
        assert compiled["ok"] is True

        interrogated = _request(
            "POST",
            f"http://{host}:{port}/interrogate",
            {
                "idea": "Checkout",
                "answers": [
                    "success_criteria=user can checkout",
                    "failure_case=declined card is rejected",
                    "constraints=checkout under 2 minutes",
                ],
            },
        )
        assert interrogated["ok"] is True
        assert interrogated["session"]["iteration"] == 1
    finally:
        server.shutdown()
        server.server_close()
