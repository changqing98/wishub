import abc
from typing import Dict, List, Union, Generator


class LLMService(abc.ABC):
    @abc.abstractmethod
    def complete(self, messages: List[Dict[str, str]], temperature: float = 0, stream: bool = False,
                 max_tokens: int = 2048) -> Union[str, Generator[str, None, None]]:
        """
        统一对话接口
        :param messages: 对话历史
        :param temperature: 随机度
        :param max_tokens: 最大输出长度
        :param stream: True=流式迭代器  False=一次性完整字符串
        :return: 非流式 → 完整文本str；流式 → 逐块文本生成器
        """
        raise NotImplementedError

    @abc.abstractmethod
    def embedding(self, text: str) -> List[float]:
        """向量化接口（无流式）"""
        raise NotImplementedError
