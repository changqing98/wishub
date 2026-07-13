import abc
from typing import Any, Dict, List, Optional


class EmbeddingService(abc.ABC):
    @abc.abstractmethod
    def save(
        self,
        collection_name: str,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """
        向量数据库保存接口。

        :param collection_name: 向量集合名称
        :param ids: 向量ID列表
        :param embeddings: 向量列表
        :param metadatas: 元数据列表（可选）
        :param documents: 文本列表（可选）
        """
        raise NotImplementedError
