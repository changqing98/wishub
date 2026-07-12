import abc
from typing import Dict, List


class CompleteCommand:
    def __init__(self, messages: List[Dict[str, str]], temperature: float = 0):
        self.messages = messages
        self.temperature = temperature


class LLMService(abc.ABC):
    @abc.abstractmethod
    def complete(self, cmd: CompleteCommand) -> str:
        raise NotImplemented
