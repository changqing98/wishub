import abc


class DataSpliter(abc.ABC):
    @abc.abstractmethod
    def split(self, file):
        raise NotImplementedError
