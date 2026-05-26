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

from ai_provider import RemoteLessonAI
from app_logging import get_app_logger


logger = get_app_logger(__name__)
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "dist"


class DialogueEngine:
    def answer_student_question(self, payload: dict[str, Any]) -> dict[str, Any]:
        lesson = _dict(payload.get("lesson"))
        question = str(payload.get("question", ""))
        fallback = _dict(payload.get("fallback"))
        ai = self._build_ai(payload, lesson)
        if not ai.is_remote_configured():
            return {
                "answer": fallback.get("answer", "请先配置 AI 后端，或使用本地模板继续课堂。"),
                "source": fallback.get("source", "local"),
                "matchedTitle": fallback.get("matchedTitle", ""),
                "runtimeStatus": ai.get_runtime_status(),
                "usingRemote": False,
            }
        context = self._lesson_context(lesson)
        answer = ai.answer_student_question(question, context)
        return {
            "answer": answer,
            "source": "generated" if ai.is_using_remote() else fallback.get("source", "local"),
            "matchedTitle": fallback.get("matchedTitle", ""),
            "runtimeStatus": ai.get_runtime_status(),
            "usingRemote": ai.is_using_remote(),
        }

    def respond_to_reflection(self, payload: dict[str, Any]) -> dict[str, Any]:
        lesson = _dict(payload.get("lesson"))
        response = str(payload.get("response", ""))
        fallback = _dict(payload.get("fallback"))
        ai = self._build_ai(payload, lesson)
        if not ai.is_remote_configured():
            return {
                "feedback": fallback.get("feedback", "请先配置 AI 后端，或使用本地模板继续课堂。"),
                "followUp": fallback.get("followUp", self._build_follow_up(response)),
                "runtimeStatus": ai.get_runtime_status(),
                "usingRemote": False,
            }
        feedback = ai.respond_to_reflection(response)
        return {
            "feedback": feedback,
            "followUp": fallback.get("followUp", self._build_follow_up(response)),
            "runtimeStatus": ai.get_runtime_status(),
            "usingRemote": ai.is_using_remote(),
        }

    def respond_to_follow_up(self, payload: dict[str, Any]) -> dict[str, Any]:
        lesson = _dict(payload.get("lesson"))
        response = str(payload.get("response", ""))
        follow_up = str(payload.get("followUp", ""))
        fallback = _dict(payload.get("fallback"))
        if not response.strip():
            return {
                "response": "可以先让学生用一句话回应这个追问，再补充一个具体理由。",
                "runtimeStatus": "课堂模式：本地",
                "usingRemote": False,
            }
        ai = self._build_ai(payload, lesson)
        if not ai.is_remote_configured():
            return {
                "response": fallback.get("response", "请先配置 AI 后端，或使用本地模板继续课堂。"),
                "runtimeStatus": ai.get_runtime_status(),
                "usingRemote": False,
            }
        prompt = (
            "你是一名七年级语文课堂助手。请根据 AI 追问和学生回应，给出 80 到 160 字的课堂式二次回应。"
            "先接住学生观点，再推进到文本核心，不要模板腔。\n"
            f"课文：{lesson.get('title', '当前课文')}\n"
            f"追问：{follow_up}\n"
            f"学生回应：{response}"
        )
        ai_answer = ai._ask_remote(prompt, str(fallback.get("response", "")))  # noqa: SLF001 - keep legacy provider small.
        return {
            "response": ai_answer,
            "runtimeStatus": ai.get_runtime_status(),
            "usingRemote": ai.is_using_remote(),
        }

    def test_runtime(self, payload: dict[str, Any]) -> dict[str, Any]:
        lesson = _dict(payload.get("lesson"))
        ai = self._build_ai(payload, lesson)
        connected = ai.try_remote_mode()
        return {
            "runtimeStatus": ai.get_runtime_status(),
            "usingRemote": ai.is_using_remote(),
            "connected": connected,
            "configured": ai.is_remote_configured(),
        }

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

    def _build_ai(self, payload: dict[str, Any], lesson: dict[str, Any]) -> RemoteLessonAI:
        config = _dict(payload.get("clientConfig"))
        endpoint = str(config.get("endpoint") or os.getenv("V2_LESSON_AI_ENDPOINT") or os.getenv("LESSON_AI_ENDPOINT") or "").strip()
        api_key = str(config.get("apiKey") or os.getenv("V2_LESSON_AI_API_KEY") or os.getenv("LESSON_AI_API_KEY") or "").strip()
        model = str(config.get("model") or os.getenv("V2_LESSON_AI_MODEL") or os.getenv("LESSON_AI_MODEL") or "deepseek-ai/DeepSeek-V4-Flash").strip()
        return RemoteLessonAI(
            reflection_prompt=str(lesson.get("aiStudentPrompt") or ""),
            endpoint=endpoint or None,
            api_key=api_key or None,
            model=model or None,
        )

    @staticmethod
    def _lesson_context(lesson: dict[str, Any]) -> str:
        return (
            f"当前课文：{lesson.get('title', '')}\n"
            f"学习目标：{'；'.join(str(item) for item in lesson.get('goals', []) if item)}\n"
            f"学习重点：{lesson.get('keyPoints', '')}\n"
            f"学习难点：{lesson.get('difficultPoints', '')}\n"
            f"核心问题：{lesson.get('aiStudentPrompt', '')}"
        )

    @staticmethod
    def _build_follow_up(student_text: str) -> str:
        if not student_text.strip():
            return "请先用一句话表明你的立场，再补充一个生活中的例子。"
        if _contains_any(student_text, ("两种", "辩证", "既", "也", "一方面", "另一方面")):
            return "如果环境会影响人，而人也能作选择，你认为哪一步更关键？"
        if _contains_any(student_text, ("环境", "影响", "近墨者黑", "很难")):
            return "当环境确实会影响人时，一个人可以靠哪些具体做法减少负面影响？"
        return "请把你的观点和课文中的一句话连起来，再说明这句话为什么能支持你的看法。"


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
        payload = self._read_json()
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

        routes = {
            "/api/ask": self.server.engine.answer_student_question,
            "/api/reflect": self.server.engine.respond_to_reflection,
            "/api/follow-up": self.server.engine.respond_to_follow_up,
            "/api/runtime/test": self.server.engine.test_runtime,
        }
        handler = routes.get(parsed.path)
        if handler:
            try:
                self._send_json(handler(payload))
            except Exception as exc:  # noqa: BLE001 - API boundary should return JSON.
                logger.exception("API request failed. path=%s", parsed.path)
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
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


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


if __name__ == "__main__":
    main()
