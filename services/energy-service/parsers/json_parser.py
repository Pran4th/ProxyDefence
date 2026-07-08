import json

from parsers.base import ImportParser


class JsonParser(ImportParser):
    def parse(self, content: str) -> list[dict]:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            entities = data.get("entities", data.get("data", None))
            if isinstance(entities, list):
                return entities
            return [data]
        raise ValueError("JSON must be an object or array of objects")
