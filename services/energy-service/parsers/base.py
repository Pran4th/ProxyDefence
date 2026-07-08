from abc import ABC, abstractmethod


class ImportParser(ABC):
    @abstractmethod
    def parse(self, content: str) -> list[dict]:
        ...
