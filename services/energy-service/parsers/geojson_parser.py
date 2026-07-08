import json

from parsers.base import ImportParser


class GeoJsonParser(ImportParser):
    def parse(self, content: str) -> list[dict]:
        data = json.loads(content)

        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            raise ValueError("GeoJSON must be a FeatureCollection")

        features = data.get("features", [])
        records = []
        for feature in features:
            props = feature.get("properties", {})
            geometry = feature.get("geometry")

            props["_table"] = props.get("_table", "locations")

            if geometry and geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
                if len(coords) >= 2:
                    props["longitude"] = coords[0]
                    props["latitude"] = coords[1]

            props["geojson"] = json.dumps(geometry) if geometry else None
            records.append(props)

        return records
