"""Lightweight web API for dual-spec workflow operations."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from spec_eng.workflow_mcp import _interrogate, _spec_check, _spec_compile


class WorkflowHandler(BaseHTTPRequestHandler):
    """JSON HTTP interface for compile/check/interrogate operations."""

    project_root = Path(".")

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write_json({"ok": True, "service": "spec-eng-web"}, HTTPStatus.OK)
            return
        self._write_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/compile", "/check", "/interrogate"}:
            self._write_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json_body()
            response = self._dispatch(self.path, payload)
            self._write_json(response, HTTPStatus.OK)
        except Exception as exc:  # broad by design for API boundary
            self._write_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _dispatch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        root = str(self.project_root)
        if path == "/compile":
            return _spec_compile(
                input_path=str(payload["input_path"]),
                project_root=str(payload.get("project_root", root)),
            )
        if path == "/check":
            return _spec_check(
                input_path=str(payload["input_path"]),
                project_root=str(payload.get("project_root", root)),
            )
        return _interrogate(
            idea=str(payload["idea"]),
            project_root=str(payload.get("project_root", root)),
            slug=payload.get("slug"),
            answers=list(payload.get("answers", [])),
            approve=bool(payload.get("approve", False)),
        )

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _write_json(self, payload: dict[str, Any], status: HTTPStatus) -> None:
        body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_web_api(host: str = "127.0.0.1", port: int = 8765, project_root: str = ".") -> None:
    WorkflowHandler.project_root = Path(project_root)
    server = ThreadingHTTPServer((host, port), WorkflowHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run spec-eng web API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    run_web_api(host=args.host, port=args.port, project_root=args.project_root)


if __name__ == "__main__":
    main()
