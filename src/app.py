"""Ứng dụng so sánh chatbot và ReAct Agent hỗ trợ quản lý đơn hàng."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
import inspect
import json
import os
import re
import sys
from typing import Any
import unicodedata

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from prompts import (  # noqa: E402
    CHATBOT_BASELINE_PROMPT,
    MAX_ITERATIONS,
    MAX_POLICY_RETRIES,
    REACT_SYSTEM_PROMPT,
    TIMEOUT_SECONDS,
)
from providers import get_llm_provider  # noqa: E402
from tools import AVAILABLE_TOOLS, get_return_policy_text  # noqa: E402


ACTION_PATTERN = re.compile(
    r"^\s*Action\s*:\s*([A-Za-z_]\w*)\s*\[(.*)\]\s*$",
    re.IGNORECASE | re.MULTILINE,
)
FINAL_ANSWER_PATTERN = re.compile(
    r"Final\s+Answer\s*:\s*(.+)", re.IGNORECASE | re.DOTALL
)
ORDER_ID_PATTERN = re.compile(r"\bORD\d+\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+84|0)(?:[\s.-]?\d){9}(?!\d)")


@dataclass(frozen=True)
class RequestPlan:
    """Policy do code xác định; LLM không được tự mở rộng phạm vi này."""

    intent: str
    description: str
    tool_sequence: tuple[str, ...]


def _normalize_for_intent(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")


def classify_request(user_query: str) -> RequestPlan:
    """Phân loại ý định và tạo chuỗi tool tối đa được phép thực thi."""
    normalized = _normalize_for_intent(user_query)
    has_order_id = ORDER_ID_PATTERN.search(user_query) is not None
    has_phone = PHONE_PATTERN.search(user_query) is not None

    create_markers = (
        "tao yeu cau doi tra",
        "tao yeu cau tra don",
        "tao yeu cau tra hang",
    )
    return_markers = (
        "doi tra",
        "tra don",
        "tra hang",
        "hoan hang",
        "du dieu kien tra",
    )
    explicitly_create = any(marker in normalized for marker in create_markers)
    asks_about_return = any(marker in normalized for marker in return_markers)

    if explicitly_create and has_order_id:
        return RequestPlan(
            intent="CREATE_RETURN_REQUEST",
            description="Tạo yêu cầu đổi trả được người dùng yêu cầu rõ ràng",
            tool_sequence=(
                "lookup_order",
                "check_return_eligibility",
                "create_return_request",
            ),
        )
    if asks_about_return and has_order_id:
        return RequestPlan(
            intent="CHECK_RETURN_ELIGIBILITY",
            description="Chỉ kiểm tra điều kiện đổi trả, không tạo yêu cầu",
            tool_sequence=("lookup_order", "check_return_eligibility"),
        )
    if has_phone:
        return RequestPlan(
            intent="FIND_ORDER_IDS",
            description="Chỉ tìm mã đơn theo số điện thoại",
            tool_sequence=("look_order_id",),
        )
    if has_order_id:
        return RequestPlan(
            intent="LOOKUP_ORDER",
            description="Chỉ tra cứu thông tin một đơn hàng",
            tool_sequence=("lookup_order",),
        )
    return RequestPlan(
        intent="GENERAL_QUESTION",
        description="Trả lời thông tin chung, không gọi tool",
        tool_sequence=(),
    )


def _system_prompt_for_plan(plan: RequestPlan) -> str:
    sequence = " -> ".join(plan.tool_sequence) if plan.tool_sequence else "không gọi tool"
    return (
        f"{REACT_SYSTEM_PROMPT}\n\n"
        "POLICY CỨNG DO ỨNG DỤNG XÁC ĐỊNH:\n"
        f"- Ý định: {plan.intent}.\n"
        f"- Phạm vi: {plan.description}.\n"
        f"- Chuỗi tool duy nhất được phép: {sequence}.\n"
        "- Không suy diễn thêm nhu cầu. Không được gọi tool ngoài chuỗi trên.\n"
        "- Dữ liệu returnable từ lookup_order không thay thế cho check_return_eligibility.\n"
        "- Khi đã hoàn tất tool cuối cùng, phải dừng."
    )


def _is_terminal_observation(observation: str) -> bool:
    return observation.startswith(("LỖI", "KHÔNG ĐỦ ĐIỀU KIỆN"))


def _format_phone_number(phone_number: str) -> str:
    digits = "".join(character for character in str(phone_number) if character.isdigit())
    if len(digits) == 10:
        return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
    return str(phone_number)


def _format_price_vnd(price: Any) -> str:
    try:
        return f"{int(price):,}".replace(",", ".") + " VNĐ"
    except (TypeError, ValueError):
        return f"{price} VNĐ"


def _join_vietnamese(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" và {items[-1]}"


def _format_lookup_order(observation: str) -> str | None:
    try:
        order = json.loads(observation)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(order, dict) or "order_id" not in order:
        return None

    status_labels = {
        "processing": "đang được xử lý",
        "confirmed": "đã được xác nhận",
        "shipping": "đang được vận chuyển",
        "delivered": "đã được giao",
        "cancelled": "đã bị hủy",
        "canceled": "đã bị hủy",
    }
    status = status_labels.get(str(order.get("status", "")).lower(), order.get("status"))
    sentences = [f"Đơn {order['order_id']} hiện {status}."]

    product = order.get("product")
    price = order.get("price_vnd")
    if product and price is not None:
        sentences.append(f"Sản phẩm là {product}, có giá {_format_price_vnd(price)}.")
    elif product:
        sentences.append(f"Sản phẩm là {product}.")

    phone_number = order.get("phone_number")
    if phone_number:
        sentences.append(
            f"Số điện thoại đặt hàng là {_format_phone_number(phone_number)}."
        )

    delivered_days_ago = order.get("delivered_days_ago")
    if delivered_days_ago is not None and order.get("status") == "delivered":
        sentences.append(f"Đơn đã được giao {delivered_days_ago} ngày trước.")
    return " ".join(sentences)


def _format_order_ids(observation: str) -> str | None:
    try:
        result = json.loads(observation)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(result, dict) or not isinstance(result.get("order_ids"), list):
        return None

    order_ids = [str(order_id) for order_id in result["order_ids"]]
    phone_number = _format_phone_number(result.get("phone_number", ""))
    if not order_ids:
        return f"Mình không tìm thấy đơn hàng nào của số điện thoại {phone_number}."
    noun = "đơn hàng" if len(order_ids) == 1 else f"{len(order_ids)} đơn hàng"
    return (
        f"Số điện thoại {phone_number} có {noun}: "
        f"{_join_vietnamese(order_ids)}."
    )


def _finalize_plan(plan: RequestPlan, observation: str) -> str:
    if observation.startswith("LỖI:"):
        return f"Mình chưa thể hoàn tất yêu cầu. {observation.removeprefix('LỖI:').strip()}"

    if plan.intent == "LOOKUP_ORDER":
        return _format_lookup_order(observation) or observation
    if plan.intent == "FIND_ORDER_IDS":
        return _format_order_ids(observation) or observation
    if plan.intent == "CHECK_RETURN_ELIGIBILITY":
        if observation.startswith("ĐỦ ĐIỀU KIỆN:"):
            detail = observation.removeprefix("ĐỦ ĐIỀU KIỆN:").strip()
            return f"Đơn hàng đủ điều kiện đổi trả. {detail}"
        if observation.startswith("KHÔNG ĐỦ ĐIỀU KIỆN:"):
            detail = observation.removeprefix("KHÔNG ĐỦ ĐIỀU KIỆN:").strip()
            return f"Đơn hàng chưa đủ điều kiện đổi trả. {detail}"
    if plan.intent == "CREATE_RETURN_REQUEST":
        return observation
    return observation


def load_test_cases() -> list[dict[str, Any]]:
    """Đọc bộ test của Role 1 từ ``config/test_cases.json``."""
    config_path = os.path.join(PROJECT_DIR, "config", "test_cases.json")
    with open(config_path, "r", encoding="utf-8") as file:
        test_cases = json.load(file)
    if not isinstance(test_cases, list):
        raise ValueError("config/test_cases.json phải chứa một JSON array.")
    return test_cases


def run_baseline_chatbot(user_query: str, provider) -> str:
    """Chạy chatbot không có quyền truy cập tool để làm mốc so sánh."""
    print(f"\n💬 [CHATBOT BASELINE] {user_query}")
    system_prompt = f"{CHATBOT_BASELINE_PROMPT}\n\n{get_return_policy_text()}"
    response = provider.generate(user_query, system_prompt=system_prompt)
    print(f"🤖 {response}")
    return response


def _parse_action(response: str) -> tuple[str, list[Any]] | None:
    """Đọc ``Action: tool[args]`` mà không thực thi biểu thức từ LLM."""
    match = ACTION_PATTERN.search(response)
    if not match:
        return None

    tool_name, raw_arguments = match.groups()
    if not raw_arguments.strip():
        return tool_name, []

    try:
        arguments = json.loads(f"[{raw_arguments}]")
    except json.JSONDecodeError:
        # Chấp nhận dấu nháy đơn để demo bền hơn, ast.literal_eval vẫn không chạy code.
        try:
            arguments = ast.literal_eval(f"[{raw_arguments}]")
        except (SyntaxError, ValueError) as exc:
            raise ValueError(
                "Tham số Action phải là chuỗi JSON, ví dụ lookup_order[\"ORD001\"]."
            ) from exc

    if not isinstance(arguments, list):
        raise ValueError("Danh sách tham số Action không hợp lệ.")
    return tool_name, arguments


def _call_tool(tool_name: str, arguments: list[Any]) -> str:
    """Xác thực và chạy đúng tool trong registry với giới hạn thời gian."""
    tool = AVAILABLE_TOOLS.get(tool_name)
    if tool is None:
        return f"LỖI: Tool '{tool_name}' không tồn tại hoặc không được phép sử dụng."

    try:
        inspect.signature(tool).bind(*arguments)
    except TypeError as exc:
        return f"LỖI: Tham số của tool '{tool_name}' không hợp lệ: {exc}."

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(tool, *arguments)
    try:
        result = future.result(timeout=TIMEOUT_SECONDS)
        return str(result)
    except FutureTimeoutError:
        future.cancel()
        return f"LỖI: Tool '{tool_name}' vượt quá timeout {TIMEOUT_SECONDS} giây."
    except Exception as exc:  # Tool lỗi phải trở thành Observation, không làm app crash.
        return f"LỖI: Tool '{tool_name}' gặp sự cố: {exc}."
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _provider_failed(response: str) -> bool:
    first_line = response.strip().splitlines()[0] if response.strip() else ""
    return first_line.startswith("[") and (
        " Error]" in first_line or " Exception]" in first_line
    )


def run_react_agent(user_query: str, provider) -> str:
    """Chạy vòng lặp Thought → Action → Observation với dispatch tool động."""
    print(f"\n🧠 [REACT AGENT] {user_query}")
    plan = classify_request(user_query)
    system_prompt = _system_prompt_for_plan(plan)
    completed_tools: list[str] = []
    policy_violations = 0
    max_llm_attempts = MAX_ITERATIONS + MAX_POLICY_RETRIES
    print(f"🎯 Ý định: {plan.intent}")
    print(
        "🔒 Tool policy: "
        + (" → ".join(plan.tool_sequence) if plan.tool_sequence else "không gọi tool")
    )
    transcript = f"Câu hỏi người dùng: {user_query}"

    for attempt in range(1, max_llm_attempts + 1):
        business_step = min(len(completed_tools) + 1, max(len(plan.tool_sequence), 1))
        print(
            f"\n--- Lần gọi LLM {attempt}/{max_llm_attempts} "
            f"| Bước nghiệp vụ {business_step}/{max(len(plan.tool_sequence), 1)} ---"
        )
        valid_action_executed = False
        response = provider.generate(transcript, system_prompt=system_prompt)
        response = response.strip()
        print(response)

        if not response:
            observation = "LỖI: LLM trả về nội dung rỗng."
        elif _provider_failed(response):
            final_answer = f"Không thể kết nối LLM: {response}"
            print(f"🛡️ {final_answer}")
            return final_answer
        else:
            final_match = FINAL_ANSWER_PATTERN.search(response)
            if final_match:
                if len(completed_tools) == len(plan.tool_sequence):
                    return final_match.group(1).strip()
                next_tool = plan.tool_sequence[len(completed_tools)]
                observation = (
                    "LỖI QUY TRÌNH: Agent trả lời quá sớm; "
                    f"bước bắt buộc tiếp theo là '{next_tool}'."
                )
                print(f"🔒 {observation}")
                transcript += (
                    f"\n\nPhản hồi trước của Agent:\n{response}"
                    f"\nObservation: {observation}"
                )
                policy_violations += 1
                if policy_violations >= MAX_POLICY_RETRIES:
                    break
                continue

            try:
                action = _parse_action(response)
            except ValueError as exc:
                action = None
                observation = f"LỖI ĐỊNH DẠNG: {exc}"
            else:
                if action is None:
                    observation = (
                        "LỖI ĐỊNH DẠNG: Phản hồi phải chứa một Action hoặc Final Answer."
                    )
                else:
                    tool_name, arguments = action
                    next_tool = (
                        plan.tool_sequence[len(completed_tools)]
                        if len(completed_tools) < len(plan.tool_sequence)
                        else None
                    )
                    if tool_name != next_tool:
                        expected = next_tool or "không gọi thêm tool"
                        observation = (
                            f"ĐÃ CHẶN: Tool '{tool_name}' nằm ngoài phạm vi yêu cầu. "
                            f"Bước được phép: {expected}."
                        )
                        print(f"🔒 {observation}")
                    else:
                        observation = _call_tool(tool_name, arguments)
                        valid_action_executed = True
                        completed_tools.append(tool_name)
                        print(f"👁️ Observation ({tool_name}): {observation}")

                        if _is_terminal_observation(observation):
                            final_answer = _finalize_plan(plan, observation)
                            print(f"🏁 {final_answer}")
                            return final_answer

                        if len(completed_tools) == len(plan.tool_sequence):
                            final_answer = _finalize_plan(plan, observation)
                            print(f"🏁 Dừng đúng phạm vi: {final_answer}")
                            return final_answer

        transcript += (
            f"\n\nPhản hồi trước của Agent:\n{response}"
            f"\nObservation: {observation}"
        )

        if not valid_action_executed:
            policy_violations += 1
            if policy_violations >= MAX_POLICY_RETRIES:
                break

    next_tool = (
        plan.tool_sequence[len(completed_tools)]
        if len(completed_tools) < len(plan.tool_sequence)
        else "không có"
    )
    final_answer = (
        "Đã dừng an toàn vì Agent vi phạm policy hoặc chưa hoàn thành quy trình. "
        f"Đã hoàn tất {len(completed_tools)}/{len(plan.tool_sequence)} tool; "
        f"bước còn thiếu: {next_tool}."
    )
    print(f"🛡️ GUARDRAIL: {final_answer}")
    return final_answer


def _default_test_case(test_cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Chọn ca multi-tool để bản demo mặc định thể hiện đầy đủ ReAct loop."""
    return next((case for case in test_cases if case.get("id") == 4), test_cases[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("baseline", "agent", "both"),
        default="both",
        help="Luồng cần chạy (mặc định: both).",
    )
    parser.add_argument("--query", help="Câu hỏi riêng thay cho test case mặc định.")
    parser.add_argument(
        "--all-tests", action="store_true", help="Chạy toàn bộ test cases."
    )
    args = parser.parse_args()

    provider = get_llm_provider()
    provider_name = provider.__class__.__name__
    model_name = getattr(provider, "model_name", "offline")
    print("=" * 64)
    print("📦 ORDER SUPPORT: CHATBOT VS REACT AGENT")
    print(f"🔌 Provider: {provider_name} ({model_name})")
    print("=" * 64)

    test_cases = load_test_cases()
    if args.query:
        selected_cases = [{"id": "custom", "question": args.query}]
    elif args.all_tests:
        selected_cases = test_cases
    else:
        selected_cases = [_default_test_case(test_cases)]

    for case in selected_cases:
        print(f"\n{'#' * 64}\nTEST {case['id']}: {case['question']}")
        if args.mode in ("baseline", "both"):
            run_baseline_chatbot(case["question"], provider)
        if args.mode in ("agent", "both"):
            run_react_agent(case["question"], provider)


if __name__ == "__main__":
    main()
