import csv
import io

from parsers.base import ImportParser


class CsvParser(ImportParser):
    def parse(self, content: str) -> list[dict]:
        reader = csv.DictReader(io.StringIO(content))
        records = list(reader)
        if not records:
            raise ValueError("CSV is empty or has no data rows")
        cleaned = []
        for row in records:
            cleaned.append({k.strip(): v.strip() if v else None for k, v in row.items() if k.strip()})
        return cleaned
