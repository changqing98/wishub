from unittest import TestCase

from backend.infra.vectordb import ChromaDBEmbeddingService


class TestChromaDBEmbeddingService(TestCase):
    def test_save(self):
        svc = ChromaDBEmbeddingService()
        svc.save(collection_name="test", embeddings=[[1.1, 2.2], [3.3, 4.4]], documents=["doc1", "doc2"],
                 ids=["v1", "v2"])
