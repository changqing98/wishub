import json
from unittest import TestCase

from backend.infra.llm import llm_service_openai


class TestHelloAgentsLLM(TestCase):
    def test_complete(self):
        svc = llm_service_openai.GeneralLLMService()
        res = svc.complete(messages=[{"role": "user", "content": "hello"}])
        print(res)


class TestOenAILLMService(TestCase):
    svc = llm_service_openai.GeneralLLMService()
    res = svc.embedding("hello")
    print(res)
    print(len(res))
