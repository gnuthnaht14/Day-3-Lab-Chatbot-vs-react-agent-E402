"""HTTP server tối giản cho giao diện chat OrderCare, không cần thêm dependency."""

import argparse
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import inspect
import json
import mimetypes
from pathlib import Path
import threading
from urllib.parse import unquote, urlparse
import webbrowser

from app import classify_request, run_baseline_chatbot, run_react_agent
from prompts import MAX_ITERATIONS, MAX_POLICY_RETRIES, TIMEOUT_SECONDS
from providers import get_llm_provider
from tools import AVAILABLE_TOOLS, RETURN_WINDOW_DAYS


PROJECT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_DIR / "web"
MAX_REQUEST_BYTES = 16_384
CHAT_LOCK = threading.Lock()


def _agent_capabilities() -> dict:
    tools = []
    for name, tool in AVAILABLE_TOOLS.items():
        signature = inspect.signature(tool)
        docstring = inspect.getdoc(tool) or "Không có mô tả."
        tools.append(
            {
                "name": name,
                "signature": f"{name}{signature}",
                "description": docstring.splitlines()[0],
                "parameters": list(signature.parameters),
                "mutating": name == "create_return_request",
            }
        )
    return {
        "tools": tools,
        "guardrails": [
            {
                "name": "Intent allowlist",
                "description": "Mỗi yêu cầu chỉ được gọi đúng chuỗi tool do policy xác định.",
            },
            {
                "name": "Write protection",
                "description": "Chỉ tạo yêu cầu đổi trả khi người dùng yêu cầu rõ ràng.",
            },
            {
                "name": "Ordered execution",
                "description": "Bắt buộc tra cứu và kiểm tra điều kiện trước thao tác ghi.",
            },
            {
                "name": "Failure stop",
                "description": "Dừng ngay khi tool báo lỗi hoặc đơn không đủ điều kiện.",
            },
        ],
        "limits": {
            "max_business_steps": MAX_ITERATIONS,
            "max_policy_retries": MAX_POLICY_RETRIES,
            "tool_timeout_seconds": TIMEOUT_SECONDS,
            "return_window_days": RETURN_WINDOW_DAYS,
        },
    }


def _event_type(line: str) -> str:
    if line.startswith("Thought:"):
        return "thought"
    if line.startswith("Action:"):
        return "action"
    if "Observation" in line:
        return "observation"
    if line.startswith(("🔒", "🛡️")):
        return "guardrail"
    if line.startswith("🎯"):
        return "intent"
    if line.startswith("🏁"):
        return "complete"
    if line.startswith("---"):
        return "step"
    return "detail"


def _parse_trace(raw_log: str, mode: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    if mode == "baseline":
        events.append(
            {
                "type": "intent",
                "content": "Baseline: trả lời bằng kiến thức và chính sách tĩnh; không gọi tool.",
            }
        )

    for raw_line in raw_log.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("💬 [", "🧠 [")):
            continue
        events.append({"type": _event_type(line), "content": line})
    return events


def _run_single_mode(message: str, mode: str, provider) -> dict:
    """Chạy một mode và trả cùng một schema để UI có thể đối chiếu."""
    output = io.StringIO()
    with redirect_stdout(output):
        if mode == "baseline":
            answer = run_baseline_chatbot(message, provider)
            intent = "BASELINE"
            policy: list[str] = []
        else:
            plan = classify_request(message)
            intent = plan.intent
            policy = list(plan.tool_sequence)
            answer = run_react_agent(message, provider)
    return {
        "answer": answer,
        "mode": mode,
        "intent": intent,
        "policy": policy,
        "trace": _parse_trace(output.getvalue(), mode),
    }


class OrderCareHandler(BaseHTTPRequestHandler):
    server_version = "OrderCare/1.0"

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, target: Path) -> None:
        if not target.is_file():
            self.send_error(404, "Không tìm thấy tài nguyên")
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed_path = urlparse(self.path).path
        if parsed_path == "/api/health":
            provider = self.server.provider
            self._send_json(
                {
                    "status": "ok",
                    "provider": provider.__class__.__name__,
                    "model": getattr(provider, "model_name", "offline"),
                }
            )
            return
        if parsed_path == "/api/capabilities":
            self._send_json(_agent_capabilities())
            return

        relative_path = "index.html" if parsed_path == "/" else unquote(parsed_path.lstrip("/"))
        target = (WEB_DIR / relative_path).resolve()
        if target != WEB_DIR and WEB_DIR not in target.parents:
            self.send_error(403, "Đường dẫn không hợp lệ")
            return
        self._send_file(target)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/chat":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise ValueError("Kích thước request không hợp lệ.")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            message = str(payload.get("message", "")).strip()
            mode = str(payload.get("mode", "agent")).lower()
            if not message:
                raise ValueError("Vui lòng nhập câu hỏi.")
            if mode not in {"agent", "baseline", "compare"}:
                raise ValueError("Mode phải là agent, baseline hoặc compare.")
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        provider = self.server.provider
        try:
            # redirect_stdout là trạng thái toàn cục, lock giúp trace không bị trộn giữa request.
            with CHAT_LOCK:
                if mode == "compare":
                    baseline_result = _run_single_mode(message, "baseline", provider)
                    agent_result = _run_single_mode(message, "agent", provider)
                    result = {
                        "mode": "compare",
                        "baseline": baseline_result,
                        "agent": agent_result,
                    }
                else:
                    result = _run_single_mode(message, mode, provider)
        except Exception as exc:  # API luôn trả lỗi có cấu trúc thay vì đóng kết nối.
            self._send_json({"error": f"Không thể xử lý yêu cầu: {exc}"}, status=500)
            return

        self._send_json(result)

    def log_message(self, format: str, *args) -> None:
        print(f"🌐 {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), OrderCareHandler)
    server.provider = get_llm_provider()
    url = f"http://{args.host}:{args.port}"
    provider_name = server.provider.__class__.__name__
    model_name = getattr(server.provider, "model_name", "offline")
    print(f"💬 OrderCare đang chạy tại {url}")
    print(f"🔌 Provider: {provider_name} ({model_name})")
    print("Nhấn Ctrl+C để dừng.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng OrderCare.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
