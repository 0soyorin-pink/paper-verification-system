import os
import aiohttp
import json
from typing import List, Dict, Any, Optional
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeepSeekClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
        self.model = "glm-4-flash-250414"  # 使用 GLM 模型
        self.timeout = aiohttp.ClientTimeout(total=60)
    
    async def chat_completion(self, 
                            messages: List[Dict[str, str]] = None,
                            system_prompt: str = None,
                            user_prompt: str = None, 
                            temperature: float = 0.1,
                            max_tokens: int = 2000,
                            json_mode: bool = False) -> Optional[str]:
        """
        增强的聊天补全方法，支持多种参数格式
        
        参数:
            messages: 完整的消息列表 [{"role": "system/user", "content": "..."}]
            system_prompt: 系统提示词（可选）
            user_prompt: 用户提示词（可选）
            temperature: 温度参数
            max_tokens: 最大token数
            json_mode: 是否强制JSON输出
        """
        # 构建 messages 列表（支持多种输入方式）
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if user_prompt:
                messages.append({"role": "user", "content": user_prompt})
        
        if not messages:
            logger.error("No messages provided for chat completion")
            return None
        
        if not self.api_key:
            logger.error("GLM API key not found in environment variables")
            return None
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 构建请求载荷
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        # 处理 JSON 模式
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        logger.info(f"调用 GLM API，模型: {self.model}, JSON模式: {json_mode}")
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]
                        logger.info("GLM API 调用成功")
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"GLM API 请求失败: {response.status} - {error_text}")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"网络错误: {e}")
            return None
        except Exception as e:
            logger.error(f"未知错误: {e}")
            return None
    
    async def process_verification_query(self, query: str, system_prompt: str) -> Optional[str]:
        """
        处理验证查询的便捷方法
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        return await self.chat_completion(messages=messages)
    
    async def generate_json_response(self, 
                                   system_prompt: str, 
                                   user_prompt: str,
                                   temperature: float = 0.1) -> Optional[dict]:
        """
        生成JSON响应的便捷方法
        """
        result = await self.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=True,
            temperature=temperature
        )
        
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}, 原始响应: {result}")
                return None
        return None
    
    def is_available(self) -> bool:
        """
        检查客户端是否可用（API密钥是否存在）
        """
        return bool(self.api_key)
    
    async def test_connection(self) -> bool:
        """
        测试API连接
        """
        test_messages = [
            {"role": "system", "content": "你是一个测试助手。"},
            {"role": "user", "content": "请回复'连接测试成功'"}
        ]
        
        response = await self.chat_completion(messages=test_messages)
        return response is not None and "连接测试成功" in response

# 全局客户端实例
_llm_client = None

def get_llm_client() -> DeepSeekClient:
    """
    获取 LLM 客户端单例
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = DeepSeekClient()
        logger.info("LLM客户端初始化完成")
    return _llm_client

async def test_glm_connection() -> str:
    """
    测试 GLM API 连接
    """
    client = get_llm_client()
    if not client.is_available():
        return "GLM API key not configured"
    
    try:
        success = await client.test_connection()
        return "GLM API 连接成功" if success else "GLM API 连接测试失败"
    except Exception as e:
        return f"GLM API 连接测试异常: {e}"

# 兼容旧版函数名
async def test_connection():
    """兼容旧版本的测试函数"""
    return await test_glm_connection()