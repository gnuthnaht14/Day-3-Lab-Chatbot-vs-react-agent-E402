# 📊 RUBRIC ĐÁNH GIÁ — TRỢ LÝ TRA CỨU ĐƠN HÀNG & XỬ LÝ ĐỔI TRẢ



## AGENTIC FIT SCORING MATRIX 

| 🧠 **Multi-step Reasoning**  | Có cần suy luận nối tiếp không?                 |  **5/5**   | Tra cứu đơn → kiểm tra trạng thái giao → đối chiếu điều kiện đổi trả (trong 7/30 ngày, còn nguyên tem) → sinh hướng dẫn.  |
| 🛠️ **Tool Interaction**     | Có cần data thời gian thực từ hệ thống không?    |  **5/5**   | Bắt buộc: `lookup_order`, `check_return_policy`, `get_return_status`. Chatbot thuần **phải bịa** mã đơn, ngày giao.      |
| 🔀 **Dynamic Decision**      | Kết quả bước trước có đổi nhánh bước sau không?  |  **4/5**   | Đơn "chưa giao" → `cancel_order`; "đã giao, trong 7 ngày" → `check_return_policy`; "quá 30 ngày" → từ chối.              |
| ⏳ **Long Horizon**          | Nhiều bước dài hạn không?                       |  **3/5**   | Tối đa 3–4 bước (khác agent lập kế hoạch 10+ bước). Điểm trung bình.                                                      |
| 🟢 **TỔNG ĐIỂM FIT**        |                                                 | **17/20**  | **KẾT LUẬN: BÀI TOÁN RẤT NÊN DÙNG REACT AGENT!**                                                                          |
---

## 📐 THANG ĐIỂM ÁP DỤNG

**0 – 2 điểm per case**

**Mục đích:** Kiểm thử chất lượng hội thoại, tính chính xác nghiệp vụ (SOP) và độ an toàn hệ thống trước/trong khi vận hành thực tế.

---

## 🔢 TỔNG QUAN THANG ĐO (SaCALING GUIDE)

| Điểm | Mức đánh giá | Mô tả |
|:----:|:-------------|:------|
| **0** | Thất bại / Fatal Fail | Sai nghiệp vụ, ảo giác dữ liệu (Hallucination), vi phạm bảo mật hoặc gây ức chế nghiêm trọng cho khách hàng. |
| **1** | Đạt cơ bản / Còn sạn UX | Hoàn thành đúng luồng nghiệp vụ nhưng xử lý máy móc, thụ động, rập khuôn hoặc yêu cầu thao tác thừa từ khách hàng. |
| **2** | Tối ưu / Xuất sắc | Trả lời chính xác tuyệt đối, thấu cảm, chủ động giải quyết vấn đề (Proactive) và tối thiểu hóa nỗ lực của khách hàng (Low CES). |

---


**Thang điểm:** 0 – 2 điểm / tiêu chí · Thang tổng: 0 – 10 điểm / case

Nghiệp Vụ Tra Cứu Đơn Hàng


| Tiêu chí | 0 điểm | 1 điểm | 2 điểm |
|:---|:---|:---|:---|
| **Factual correctness** *(Chính xác thông tin)* | Sai trạng thái / Bịa đặt thời gian giao hàng (ETA). | Đúng trạng thái nhưng thiếu ETA hoặc vị trí hiện tại. | Đúng hoàn toàn Trạng thái, Vị trí & ETA chi tiết. |
| **Grounding** *(Căn cứ dữ liệu)* | Không dựa vào DB/API (tự bịa câu trả lời để xoa dịu khách). | Dựa vào DB nhưng trả về nguyên mã code kỹ thuật (STATUS_802). | Trích xuất từ DB và dịch chính xác thành ngôn ngữ tự nhiên. |
| **Tool selection & Calling** *(Gọi công cụ)* | Gọi sai API / Không gọi tool / Truyền sai tham số (Mã đơn). | Gọi đúng tool nhưng hỏi lắt nhắt từng tham số qua nhiều lượt chat. | Tự động gom tham số trong 1 câu nói (Zero-shot) & gọi đúng tool ngay. |
| **Proactivity & Tone** *(Chủ động & Giọng văn)* | Cộc lốc / Đổ lỗi cho bên vận chuyển khi đơn trễ. | Thụ động trả lời đúng thông tin, không giải thích khi đơn bị delay. | Chủ động nhận diện đơn delay → Xin lỗi → Nêu lý do → Gợi ý bước tiếp theo. |
| **Termination & Fallback** *(Điểm dừng & Xử lý lỗi)* | Lặp vô hạn câu xin lỗi / Crash khi API phản hồi chậm. | Dừng đúng nhưng chuyển nhân viên không kèm tóm tắt lịch sử chat. | Có mẫu câu chờ khi API chậm 

Nghiệp vụ đổi trả 

 Tiêu chí | 0 điểm | 1 điểm | 2 điểm |
|:---|:---|:---|:---|
| **Policy compliance** *(Tuân thủ chính sách)* | Bỏ qua SLA / Chấp nhận đơn quá hạn hoặc hàng cấm đổi trả. | Từ chối đơn sai quy định nhưng không giải thích lý do (gây ức chế). | Kiểm tra đúng SLA, từ chối khéo léo + đề xuất giải pháp thay thế (Voucher/Bảo hành). |
| **Evidence collection** *(Thu thập bằng chứng)* | Tạo lệnh hoàn khi chưa có ảnh/video / Nhận ảnh mờ, sai sản phẩm. | Hỏi rườm rà từng bước (Hỏi lý do → Xin ảnh → Xin địa chỉ). | Hướng dẫn gom 1 lần đủ 3 ảnh minh chứng & tự phân tích tính hợp lệ của ảnh. |
| **Tool selection & Path** *(Thực thi Tool)* | Gọi sai Tool / Bịa đặt "Đã hoàn tiền thành công" / Không tạo ticket. | Gọi đúng tool tạo ticket nhưng không trả về Mã vận đơn hoàn cho khách. | Gọi đúng thứ tự tool path: Tạo ticket → Trả mã vận đơn hoàn → Báo lịch shipper. |
| **Empathy & Alignment** *(Thấu cảm & Điều hướng)* | Tranh cãi, hoài nghi khách ("Do anh dùng sai cách...") / Vô cảm. | Lịch sự nhưng rập khuôn kiểu văn mẫu copy-paste, thiếu đồng cảm. | Xin lỗi chân thành vì trải nghiệm tệ trước khi đi vào luồng thu thập thông tin. |
| **Termination & Handover** *(Điểm dừng & Chuyển tiếp)* | Tranh luận vô bổ / Bế tắc, tự ngắt kết nối khi gặp ca khiếu nại khó. | Dừng thụ động (chỉ chuyển khi khách gõ "Gặp nhân viên"), bắt khách kể lại từ đầu. | Nhận diện thái độ gay gắt/ca vượt thẩm quyền → Chuyển tiếp ngay kèm toàn bộ hồ sơ (Ảnh, Lý do). |


## 📐 CÔNG THỨC TÍNH ĐIỂM

$$\text{Điểm Kịch Bản} = \sum_{i=1}^{5} \text{Điểm Tiêu Chí}_i \quad \text{(Tối đa: 10 điểm / case)}$$

| Tổng điểm | Xếp loại |
|:---------:|:---------|
| 9 – 10 | Xuất sắc |
| 7 – 8 | Khá |
| 5 – 6 | Trung bình |
| 3 – 4 | Yếu |
| 0 – 2 | Không đạt |