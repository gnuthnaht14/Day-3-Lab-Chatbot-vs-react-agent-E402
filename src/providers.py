"""
🔌 MULTI-PROVIDER LLM ADAPTER (OpenAI, Gemini, Anthropic, OpenRouter & Offline Mock)
Hỗ trợ chuyển đổi linh hoạt giữa các nhà cung cấp AI chỉ bằng cách đổi biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
import re

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    # Mock mode vẫn chạy được khi học viên chưa cài requirements.txt.
    def load_dotenv():
        return False

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho tất cả các LLM Provider"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env!"
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (GPT-4o, GPT-3.5-turbo, etc.)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env!"
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider (Claude 3.5 Sonnet, Claude 3 Haiku)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "claude-3-haiku-20240307"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_anthropic_api_key_here":
            return "[Anthropic Error]: Chưa cấu hình ANTHROPIC_API_KEY trong file .env!"
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs = {
                "model": self.model_name,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system_prompt:
                kwargs["system"] = system_prompt
                
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"[Anthropic Exception]: {str(e)}"


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter Provider (Hỗ trợ gọi mọi model qua OpenRouter API)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "google/gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            return "[OpenRouter Error]: Chưa cấu hình OPENROUTER_API_KEY trong file .env!"
        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.model_name,
                "messages": messages
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[OpenRouter API Error {res.status_code}]: {res.text}"
        except Exception as e:
            return f"[OpenRouter Exception]: {str(e)}"


class MockProvider(BaseLLMProvider):
    """Offline Mock Provider (Cho bài test không cần kết nối API)"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        text = prompt.lower()

        # Baseline không có tool: chỉ trả lời chính sách chung và thừa nhận giới hạn.
        if "react agent" not in system_prompt.lower():
            if "chính sách" in text:
                return (
                    "Chính sách đổi trả chính thức của cửa hàng: yêu cầu phải được "
                    "gửi trong vòng 7 ngày kể từ khi đơn được giao; đơn phải ở trạng "
                    "thái đã giao; và sản phẩm phải thuộc nhóm được phép đổi trả. "
                    "Tôi không thể tra cứu hoặc thay đổi một đơn hàng cụ thể."
                )
            return (
                "Tôi không có quyền truy cập dữ liệu đơn hàng thực tế. "
                "Bạn cần sử dụng trợ lý có công cụ tra cứu đơn hàng."
            )

        # Chỉ phân loại intent trên câu hỏi gốc, không lấy nhầm dữ liệu từ Observation.
        user_prompt = prompt.splitlines()[0]
        user_text = user_prompt.lower()
        order_match = re.search(r"\bord\d+\b", user_text, re.IGNORECASE)
        phone_match = re.search(
            r"(?<!\d)(?:\+84|0)(?:[\s.-]?\d){9}(?!\d)", user_prompt
        )
        if not order_match and phone_match:
            phone_number = phone_match.group(0).strip()
            observations = re.findall(r"Observation:\s*(.+)", prompt, re.IGNORECASE)
            action_names = re.findall(r"Action:\s*([A-Za-z_]\w*)", prompt)
            if "look_order_id" not in action_names:
                return (
                    "Thought: Tôi cần tìm mã đơn theo số điện thoại.\n"
                    f'Action: look_order_id["{phone_number}"]'
                )

            last_observation = observations[-1] if observations else ""
            if last_observation.startswith("LỖI"):
                return (
                    "Thought: Không tìm thấy đơn hàng tương ứng.\n"
                    f"Final Answer: {last_observation}"
                )
            return (
                "Thought: Tôi đã tìm thấy các mã đơn của khách hàng.\n"
                f"Final Answer: {last_observation}"
            )

        if not order_match:
            return (
                "Thought: Đây là câu hỏi chính sách chung, không cần gọi tool.\n"
                "Final Answer: Cửa hàng hỗ trợ đổi trả trong 7 ngày đối với "
                "sản phẩm đủ điều kiện."
            )

        order_id = order_match.group(0).upper()
        observations = re.findall(r"Observation:\s*(.+)", prompt, re.IGNORECASE)
        action_names = re.findall(r"Action:\s*([A-Za-z_]\w*)", prompt)
        last_observation = observations[-1] if observations else ""

        if "lookup_order" not in action_names:
            return (
                "Thought: Tôi cần xác minh đơn hàng trước.\n"
                f'Action: lookup_order["{order_id}"]'
            )

        if last_observation.startswith("LỖI"):
            return (
                "Thought: Không tìm thấy đơn nên tôi phải dừng.\n"
                f"Final Answer: Không tìm thấy đơn hàng {order_id}; "
                "tôi chưa tạo bất kỳ yêu cầu đổi trả nào."
            )

        return_intent = any(
            keyword in user_text for keyword in ("đổi trả", "trả đơn", "trả hàng")
        )
        create_intent = any(
            keyword in user_text for keyword in ("hãy tạo", "tạo yêu cầu", "giúp tôi")
        )

        if not return_intent:
            return (
                "Thought: Tôi đã có dữ liệu trạng thái đơn hàng.\n"
                f"Final Answer: Thông tin đơn {order_id}: {last_observation}"
            )

        if "check_return_eligibility" not in action_names:
            return (
                "Thought: Tôi cần kiểm tra điều kiện đổi trả.\n"
                f'Action: check_return_eligibility["{order_id}"]'
            )

        if "create_return_request" in action_names:
            return (
                "Thought: Yêu cầu đổi trả đã được tạo thành công.\n"
                f"Final Answer: {last_observation}"
            )

        if not last_observation.startswith("ĐỦ ĐIỀU KIỆN"):
            return (
                "Thought: Đơn không đáp ứng điều kiện nên tôi phải dừng.\n"
                f"Final Answer: {last_observation}"
            )

        if create_intent and "create_return_request" not in action_names:
            reason = "Sản phẩm bị lỗi" if "bị lỗi" in user_text else "Không còn nhu cầu"
            return (
                "Thought: Người dùng đã yêu cầu tạo và đơn đủ điều kiện.\n"
                f'Action: create_return_request["{order_id}", "{reason}"]'
            )

        return (
            "Thought: Tôi đã kiểm tra xong điều kiện đổi trả.\n"
            f"Final Answer: {last_observation}"
        )


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    """Factory function tự chọn Provider từ biến môi trường LLM_PROVIDER"""
    name = (provider_name or os.getenv("LLM_PROVIDER") or "mock").lower().strip()
    
    if name == "gemini":
        return GeminiProvider()
    elif name == "openai":
        return OpenAIProvider()
    elif name == "anthropic":
        return AnthropicProvider()
    elif name == "openrouter":
        return OpenRouterProvider()
    else:
        return MockProvider()


if __name__ == "__main__":
    print("=== TEST MULTI-PROVIDER LLM ADAPTER ===")
    provider = get_llm_provider()
    print(f"✅ Provider đang dùng: {provider.__class__.__name__}")
    print(f"🤖 User Query: Hello")
    print(f"💬 Response  : {provider.generate('Hello')}")
