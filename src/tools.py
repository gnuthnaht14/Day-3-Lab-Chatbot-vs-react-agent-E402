"""Các công cụ nghiệp vụ dành cho Order Support ReAct Agent."""

import json
from typing import Any


# Dữ liệu giả lập để bài lab chạy hoàn toàn offline và cho kết quả ổn định.
ORDERS: dict[str, dict[str, Any]] = {
    "ORD001": {
        "product": "Tai nghe Bluetooth",
        "phone_number": "0981801663",
        "price_vnd": 800_000,
        "status": "delivered",
        "delivered_days_ago": 3,
        "returnable": True,
    },
    "ORD002": {
        "product": "Bàn phím cơ",
        "phone_number": "0941449752",
        "price_vnd": 1_200_000,
        "status": "shipping",
        "delivered_days_ago": None,
        "returnable": True,
    },
    "ORD003": {
        "product": "Thẻ quà tặng điện tử",
        "phone_number": "0981801663",
        "price_vnd": 500_000,
        "status": "delivered",
        "delivered_days_ago": 2,
        "returnable": False,
    },
    "ORD004": {
        "product": "Chuột không dây",
        "phone_number": "0941440752",
        "price_vnd": 450_000,
        "status": "delivered",
        "delivered_days_ago": 12,
        "returnable": True,
    },
}

RETURN_REQUESTS: dict[str, dict[str, str]] = {}
ORDER_POLICY = {
    "return_window_days": 7,
    "requires_delivered_order": True,
    "requires_returnable_product": True,
}
RETURN_WINDOW_DAYS = ORDER_POLICY["return_window_days"]


def get_return_policy_text() -> str:
    """Trả về chính sách tĩnh dùng chung cho chatbot và tool nghiệp vụ."""
    return (
        "Chính sách đổi trả chính thức của cửa hàng:\n"
        f"- Yêu cầu đổi trả phải được gửi trong vòng {RETURN_WINDOW_DAYS} ngày "
        "kể từ khi đơn được giao.\n"
        "- Đơn hàng phải ở trạng thái đã giao.\n"
        "- Sản phẩm phải thuộc nhóm được phép đổi trả.\n"
        "- Cần tra cứu đơn hàng cụ thể để xác nhận đủ tất cả điều kiện."
    )


def _normalize_order_id(order_id: str) -> str:
    return str(order_id).strip().upper()


def _normalize_phone_number(phone_number: str) -> str:
    """Chuẩn hóa số Việt Nam dạng ``+84...`` hoặc có dấu cách về dạng ``0...``."""
    raw_phone = str(phone_number).strip()
    digits = "".join(character for character in raw_phone if character.isdigit())
    if raw_phone.startswith("+") and digits.startswith("84"):
        digits = f"0{digits[2:]}"
    return digits


def _json(data: dict[str, Any]) -> str:
    """Trả kết quả tool ở dạng một dòng để LLM và trace dễ đọc."""
    return json.dumps(data, ensure_ascii=False)


def lookup_order(order_id: str) -> str:
    """Tra cứu thông tin của một đơn hàng bằng mã đơn.

    Args:
        order_id: Mã đơn hàng, ví dụ ``ORD001``.

    Returns:
        Chuỗi JSON chứa thông tin đơn hàng hoặc thông báo bắt đầu bằng ``LỖI``.
    """
    normalized_id = _normalize_order_id(order_id)
    order = ORDERS.get(normalized_id)
    if order is None:
        return f"LỖI: Không tìm thấy đơn hàng '{normalized_id or order_id}'."

    return _json({"order_id": normalized_id, **order})


def look_order_id(phone_number: str) -> str:
    """Tìm các mã đơn hàng gắn với một số điện thoại khách hàng.

    Args:
        phone_number: Số điện thoại Việt Nam, ví dụ ``0901234567``.

    Returns:
        Chuỗi JSON chứa danh sách mã đơn hoặc thông báo bắt đầu bằng ``LỖI``.
    """
    normalized_phone = _normalize_phone_number(phone_number)
    if len(normalized_phone) != 10 or not normalized_phone.startswith("0"):
        return f"LỖI: Số điện thoại '{phone_number}' không hợp lệ."

    order_ids = [
        order_id
        for order_id, order in ORDERS.items()
        if order["phone_number"] == normalized_phone
    ]
    if not order_ids:
        return f"LỖI: Không tìm thấy đơn hàng cho số điện thoại '{normalized_phone}'."

    return _json({"phone_number": normalized_phone, "order_ids": order_ids})


def check_return_eligibility(order_id: str) -> str:
    """Kiểm tra đơn hàng có đủ điều kiện đổi trả trong 7 ngày hay không.

    Tool chỉ kết luận đủ điều kiện khi đơn đã giao, sản phẩm cho phép đổi trả
    và thời gian kể từ lúc giao không vượt quá ``RETURN_WINDOW_DAYS``.
    """
    normalized_id = _normalize_order_id(order_id)
    order = ORDERS.get(normalized_id)
    if order is None:
        return f"LỖI: Không tìm thấy đơn hàng '{normalized_id or order_id}'."

    if ORDER_POLICY["requires_delivered_order"] and order["status"] != "delivered":
        return (
            f"KHÔNG ĐỦ ĐIỀU KIỆN: Đơn {normalized_id} chưa được giao "
            "nên chưa thể tạo yêu cầu đổi trả."
        )
    if ORDER_POLICY["requires_returnable_product"] and not order["returnable"]:
        return (
            f"KHÔNG ĐỦ ĐIỀU KIỆN: Đơn {normalized_id} chứa sản phẩm "
            f"'{order['product']}' "
            "thuộc nhóm không được đổi trả."
        )
    if order["delivered_days_ago"] > RETURN_WINDOW_DAYS:
        return (
            f"KHÔNG ĐỦ ĐIỀU KIỆN: Đơn {normalized_id} đã được giao "
            f"{order['delivered_days_ago']} ngày, vượt thời hạn {RETURN_WINDOW_DAYS} ngày."
        )

    return (
        f"ĐỦ ĐIỀU KIỆN: Đơn {normalized_id} có thể đổi trả; "
        f"đã giao {order['delivered_days_ago']} ngày trước."
    )


def create_return_request(order_id: str, reason: str) -> str:
    """Tạo yêu cầu đổi trả sau khi tự kiểm tra lại điều kiện an toàn.

    Args:
        order_id: Mã đơn hàng cần đổi trả.
        reason: Lý do người dùng yêu cầu đổi trả.

    Returns:
        Mã yêu cầu đổi trả hoặc thông báo lỗi/không đủ điều kiện.
    """
    normalized_id = _normalize_order_id(order_id)
    normalized_reason = str(reason).strip()
    if not normalized_reason:
        return "LỖI: Lý do đổi trả không được để trống."

    eligibility = check_return_eligibility(normalized_id)
    if not eligibility.startswith("ĐỦ ĐIỀU KIỆN"):
        return eligibility

    existing_request = RETURN_REQUESTS.get(normalized_id)
    if existing_request:
        return (
            f"Yêu cầu đổi trả {existing_request['request_id']} đã tồn tại "
            f"cho đơn {normalized_id}."
        )

    request_id = f"RET-{normalized_id}"
    RETURN_REQUESTS[normalized_id] = {
        "request_id": request_id,
        "reason": normalized_reason,
        "status": "created",
    }
    return (
        f"Đã tạo yêu cầu đổi trả {request_id} cho đơn {normalized_id}. "
        f"Lý do: {normalized_reason}."
    )


AVAILABLE_TOOLS = {
    "look_order_id": look_order_id,
    "lookup_order": lookup_order,
    "check_return_eligibility": check_return_eligibility,
    "create_return_request": create_return_request,
}
