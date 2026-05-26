from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import subprocess
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app_logging import get_app_logger


logger = get_app_logger(__name__)
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "dist"


class DialogueEngine:
    def update_container(self) -> dict[str, Any]:
        command = os.environ.get(
            "DEPLOY_UPDATE_COMMAND",
            "docker compose pull hhs-class-1-v2 && docker compose up -d hhs-class-1-v2",
        )
        completed = subprocess.run(
            command,
            shell=True,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=600,
        )
        output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
        logger.info("Deploy update command finished. returnCode=%s", completed.returncode)
        return {
            "ok": completed.returncode == 0,
            "returnCode": completed.returncode,
            "output": output[-4000:],
        }


class DialogueRequestHandler(BaseHTTPRequestHandler):
    server_version = "LessonTemplateV2/2.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        logger.info("GET %s", parsed.path)
        self._send_static(parsed.path)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        logger.info("HEAD %s", parsed.path)
        self._send_static(parsed.path, head_only=True)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        logger.info("POST %s", parsed.path)

        if parsed.path == "/api/deploy/update":
            if not self._is_deploy_request_authorized(parsed.query):
                self._send_json({"ok": False, "error": "forbidden"}, HTTPStatus.FORBIDDEN)
                return
            try:
                result = self.server.engine.update_container()
            except subprocess.TimeoutExpired:
                self._send_json({"ok": False, "error": "update_timeout"}, HTTPStatus.GATEWAY_TIMEOUT)
                return
            except OSError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(result, HTTPStatus.OK if result["ok"] else HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.info("[%s] %s %s", timestamp, self.address_string(), format % args)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _is_deploy_request_authorized(self, query: str) -> bool:
        expected_token = os.environ.get("DEPLOY_WEBHOOK_TOKEN", "").strip()
        if not expected_token:
            return False
        tokens = parse_qs(query).get("token", [])
        return bool(tokens and tokens[0] == expected_token)

    def _send_static(self, request_path: str, head_only: bool = False) -> None:
        if not STATIC_DIR.exists():
            self._send_json({"error": "dist_not_built"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return

        clean_path = request_path.lstrip("/") or "index.html"
        candidate = (STATIC_DIR / clean_path).resolve()
        if not str(candidate).startswith(str(STATIC_DIR.resolve())):
            self._send_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.exists():
            candidate = STATIC_DIR / "index.html"

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix == ".js":
            content_type = "text/javascript"
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") or content_type == "application/json" else content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class DialogueHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(server_address, handler_class)
        self.engine = DialogueEngine()


def find_available_port(start_port: int) -> int:
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No available port found.")


def run(host: str, port: int) -> None:
    actual_port = port if host != "127.0.0.1" else find_available_port(port)
    server = DialogueHTTPServer((host, actual_port), DialogueRequestHandler)
    print(f"课堂模板平台已启动：http://{host}:{actual_port}")
    print("按 Ctrl+C 结束服务。")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="课堂模板平台 v2")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
