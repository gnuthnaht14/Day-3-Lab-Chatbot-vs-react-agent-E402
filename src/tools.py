"""
🛠️ TOOL REGISTRY & SCHEMAS (Dành cho Role 2: Tool & Spec Engineer)
Nơi khai báo tất cả các "món đồ nghề" mà ReAct Agent có thể gọi.
"""

import json
from datetime import datetime, timedelta

def get_order_details(order_id: str, customer_phone: str = "") -> str:
    """
    Tra cứu chi tiết đơn hàng dựa vào Mã đơn hàng (order_id) và Số điện thoại khách hàng.
    
    Args:
        order_id (str): Mã đơn hàng (Ví dụ: 'ORD12345')
        customer_phone (str): Số điện thoại xác minh của khách hàng
        
    Returns:
        str: Chuỗi JSON chứa danh sách sản phẩm, ngày mua, trạng thái đơn hàng.
    """
    # Mock database lookup
    if order_id == "ORD12345":
        return json.dumps({
            "order_id": "ORD12345",
            "purchase_date": "2026-07-20",
            "delivered_date": "2026-07-22",
            "status": "DELIVERED",
            "total_amount": 850000,
            "items": [
                {"item_id": "SKU_01", "name": "Áo Sơ Mi Nam Oxford White - Size L", "price": 450000, "quantity": 1},
                {"item_id": "SKU_02", "name": "Quần Jean Slimfit Blue - Size 32", "price": 400000, "quantity": 1}
            ]
        }, ensure_ascii=False)
    return f"LỖI: Không tìm thấy đơn hàng với mã '{order_id}'."


def verify_return_eligibility(order_id: str, item_id: str, return_reason: str) -> str:
    """
    Kiểm tra xem sản phẩm trong đơn hàng có đủ điều kiện đổi/trả hay không.
    
    Args:
        order_id (str): Mã đơn hàng
        item_id (str): Mã sản phẩm cần đổi/trả (Ví dụ: 'SKU_01')
        return_reason (str): Lý do đổi trả ('Lỗi nhà sản xuất', 'Không vừa size', 'Đổi ý',...)
        
    Returns:
        str: Kết quả đánh giá đủ điều kiện hay không kèm lý do.
    """
    # Logic kiểm tra thời hạn 7 ngày
    delivered_date = datetime.strptime("2026-07-22", "%Y-%m-%d")
    current_date = datetime.now()
    days_diff = (current_date - delivered_date).days
    
    if days_diff > 7:
        return json.dumps({
            "eligible": False,
            "reason": f"Đơn hàng đã giao từ {days_diff} ngày trước. Đã vượt quá thời hạn cho phép đổi trả (7 ngày)."
        }, ensure_ascii=False)
        
    return json.dumps({
        "eligible": True,
        "policy": "Miễn phí đổi size/mẫu trong 7 ngày đối với sản phẩm nguyên tem mác.",
        "note": "Khách hàng cần cung cấp ảnh chụp sản phẩm còn nguyên tem mác."
    }, ensure_ascii=False)


def create_return_request(order_id: str, item_id: str, action_type: str, reason: str) -> str:
    """
    Tạo yêu cầu đổi hàng hoặc hoàn tiền chính thức trên hệ thống.
    
    Args:
        order_id (str): Mã đơn hàng
        item_id (str): Mã sản phẩm cần đổi/trả
        action_type (str): Loại yêu cầu ('EXCHANGE' - Đổi size/mẫu, hoặc 'REFUND' - Trả hàng hoàn tiền)
        reason (str): Lý do chi tiết
        
    Returns:
        str: Mã ticket đổi trả và hướng dẫn gửi hàng.
    """
    return json.dumps({
        "status": "SUCCESS",
        "ticket_id": "RET_998877",
        "return_shipping_code": "GHN_RET_12345",
        "instruction": "Vui lòng đóng gói sản phẩm và mang tới bưu cục GHN gần nhất, đọc mã GHN_RET_12345."
    }, ensure_ascii=False)


def escalate_to_human_agent(order_id: str, summary: str) -> str:
    """
    Chuyển cuộc trò chuyện cho nhân viên CSKH khi gặp sự cố phức tạp hoặc tranh chấp.
    
    Args:
        order_id (str): Mã đơn hàng liên quan
        summary (str): Tóm tắt vấn đề của khách hàng
        
    Returns:
        str: Thông báo chuyển tiếp thành công.
    """
    return f"Đã chuyển yêu cầu hỗ trợ đơn hàng {order_id} cho nhân viên CSKH. Mã lượt hỗ trợ: #SUP-9912."


AVAILABLE_TOOLS = {
    "get_order_details": get_order_details,
    "verify_return_eligibility": verify_return_eligibility,
    "create_return_request": create_return_request,
    "escalate_to_human_agent": escalate_to_human_agent,
}
