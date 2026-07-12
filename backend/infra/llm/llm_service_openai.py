import os
from typing import Dict, List, Union, Generator
from dotenv import load_dotenv
from openai import OpenAI

from backend.domain.domainsvc import llm_service

# 加载 .env 文件中的环境变量
load_dotenv()


class OenAILLMService(llm_service.LLMService):
    """
    为本书 "Hello Agents" 定制的LLM客户端。
    它用于调用任何兼容OpenAI接口的服务，并默认使用流式响应。
    """

    def __init__(self, model: str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None):
        """
        初始化客户端。优先使用传入参数，如果未提供，则从环境变量加载。
        """
        self.model = model or os.getenv("LLM_MODEL_ID")
        apiKey = apiKey or os.getenv("LLM_API_KEY")
        baseUrl = baseUrl or os.getenv("LLM_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, apiKey, baseUrl]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.client = OpenAI(api_key=apiKey, base_url=baseUrl, timeout=timeout)

    def complete(self, messages: List[Dict[str, str]], temperature: float = 0, stream: bool = False,
                 max_tokens: int = 2048) -> Union[str, Generator[str, None, None]]:
        res = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream
        )

        # 非流式：返回完整文本
        if not stream:
            return res.choices[0].message.content.strip()

        # 流式：包装成逐块文本生成器
        def stream_generator():
            for chunk in res:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        return stream_generator()

    def embedding(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(input=text, model=self.model)
        return resp.data[0].embedding
