import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class DeepSeekClient:
    """
    封装 OpenAI 客户端，用于与 LLM 交互。
    使用预配置的环境变量 OPENAI_API_KEY 和 API_BASE。
    """
    def __init__(self, model: str = "gemini-2.5-flash"):
        # 客户端会自动从环境变量中读取配置
        base_url = os.getenv("OPENAI_API_BASE")
        if base_url:
            print(f"DeepSeekClient: 使用自定义 API Base URL: {base_url}")
            self.client = OpenAI(base_url=base_url)
        else:
            self.client = OpenAI()
        self.model = "deepseek-chat"

    def chat_completion(self, system_prompt: str, user_prompt: str, json_mode: bool = False):
        """
        调用 LLM 进行聊天补全。
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response_format = {"type": "json_object"} if json_mode else {"type": "text"}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                temperature=0.0
            )
            content = response.choices[0].message.content
            if json_mode:
                # 尝试解析 JSON 字符串
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    print(f"LLM 返回内容不是有效的 JSON: {content}")
                    return None
            return content
        except Exception as e:
            print(f"LLM 调用失败: {e}")
            return None