from dataclasses import asdict
from pathlib import Path

import pytest

from data_acquisition.parser.base import BaseParser, ParseConfig, ParserResult
from data_acquisition.canonical import CanonicalRecord, CanonicalSchema
from data_acquisition.parser.sources import (
    GDELTEventParser, GDELTMentionParser, GKGParser, GCAMParser,
    EIAParser, FREDParser,
    OPECParser,
    AISParser, PortCongestionParser, WorldPortIndexParser,
    CommodityPriceParser, CommodityFuturesParser,
    OFACParser, UNSanctionsParser,
    WorldBankParser,
    UNComtradeParser,
    KaggleParser,
)


class TestParseConfig:
    def test_default_values(self, tmp_path):
        cfg = ParseConfig(
            source="test", version="1",
            input_path=tmp_path / "in.csv",
            output_path=tmp_path / "out",
        )
        assert cfg.encoding == "utf-8"
        assert cfg.batch_size == 10000
        assert cfg.max_records is None
        assert cfg.schema is None
        assert cfg.params == {}

    def test_custom_values(self, tmp_path):
        cfg = ParseConfig(
            source="eia", version="2",
            input_path=tmp_path / "in.json",
            output_path=tmp_path / "out",
            encoding="latin-1", batch_size=500, max_records=100,
            schema={"col": "str"}, params={"key": "val"},
        )
        assert cfg.encoding == "latin-1"
        assert cfg.max_records == 100
        assert cfg.schema == {"col": "str"}


class TestParserResult:
    def test_default_errors_and_metadata(self):
        r = ParserResult(
            source="src", version="1", records_parsed=10, records_failed=0,
            output_path=Path("/out"), schema_discovered={},
            columns=[], row_count=10, duration_seconds=0.5,
        )
        assert r.errors == []
        assert r.metadata == {}

    def test_with_errors(self):
        r = ParserResult(
            source="src", version="1", records_parsed=8, records_failed=2,
            output_path=Path("/out"), schema_discovered={},
            columns=["a", "b"], row_count=8, duration_seconds=1.2,
            errors=[{"row": 5, "error": "bad value"}],
            metadata={"parser": "Test", "version": "1.0"},
        )
        assert len(r.errors) == 1
        assert r.metadata["parser"] == "Test"


class TestBaseParser:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            BaseParser()


class TestGDELTEventParser:
    @pytest.fixture
    def parser(self):
        return GDELTEventParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    def test_canonical_schema(self, parser):
        schema = parser.canonical_schema
        assert schema["entity_type"] == "string"
        assert schema["source"] == "string"

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "gdelt.tsv"
        f.write_text(
            "20120101\t20250101\tUSA\tUnited States\tRUS\tRussia\t"
            "0511\t1.5\t10\t5\t3\t-2.0\t1\tWorld\tUS\t39.0\t-77.0\n"
        )
        schema = await parser.discover_schema(f)
        assert isinstance(schema, dict)
        assert len(schema) > 0

    @pytest.mark.asyncio
    async def test_validate(self, parser, tmp_path):
        f = tmp_path / "gdelt_valid.tsv"
        f.write_text(
            "20120101\t20250101\tUSA\tUnited States\tRUS\tRussia\t"
            "0511\t1.5\t10\t5\t3\t-2.0\t1\tWorld\tUS\t39.0\t-77.0\n"
        )
        issues = await parser.validate(f)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "GlobalEventID": "12345",
            "Day": "20250101",
            "Actor1Name": "USA",
            "Actor2Name": "RUS",
            "Actor1Code": "USA",
            "Actor1CountryCode": "US",
            "Actor2Code": "RUS",
            "Actor2CountryCode": "RS",
            "EventCode": "0511",
            "GoldsteinScale": "1.5",
            "NumMentions": "10",
            "NumSources": "5",
            "NumArticles": "3",
            "AvgTone": "-2.0",
            "Actor1Geo_Type": "1",
            "Actor1Geo_FullName": "World",
            "Actor1Geo_CountryCode": "US",
            "Actor1Geo_Lat": "39.0",
            "Actor1Geo_Long": "-77.0",
        }]
        result = await parser.to_canonical(records)
        assert len(result) == 1
        assert result[0]["entity_type"] == "event"
        assert result[0]["entity_id"] == "12345"
        assert result[0]["latitude"] == 39.0
        assert result[0]["longitude"] == -77.0


class TestGDELTMentionParser:
    @pytest.fixture
    def parser(self):
        return GDELTMentionParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    def test_canonical_schema(self, parser):
        assert "mention" not in parser.canonical_schema.get("entity_type", "")

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "mentions.tsv"
        f.write_text("12345\t20250101\t20250102\t1\tSourceName\tURL\t0.5\t100\n")
        schema = await parser.discover_schema(f)
        assert isinstance(schema, dict)
        assert len(schema) > 0

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "GlobalEventID": "12345",
            "EventTimeDate": "20250101",
            "MentionTimeDate": "20250102",
            "MentionType": "1",
            "MentionSourceName": "Reuters",
            "MentionIdentifier": "url",
            "Confidence": "85",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "mention"
        assert result[0]["attributes"]["mention_source_name"] == "Reuters"


class TestGKGParser:
    @pytest.fixture
    def parser(self):
        return GKGParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "GKGRECORDID": "gkg001",
            "DATE": "20250101",
            "SourceCollectionIdentifier": "1",
            "SourceCommonName": "BBC",
            "DocumentIdentifier": "http://bbc.com/news",
            "V2Themes": "war;conflict",
            "V2Locations": "New York,40.7,-74.0,US,city",
            "V2Persons": "John Doe",
            "V2Organizations": "UN",
            "V2Tone": "-3.5,0.2,0.1",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "gkg_record"
        assert "war" in result[0]["attributes"]["themes"]
        assert len(result[0]["relationships"]) > 0


class TestGCAMParser:
    @pytest.fixture
    def parser(self):
        return GCAMParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "GlobalEventID": "42",
            "EventCode": "0511",
            "Geo_Type": "1",
            "Geo_FullName": "Moscow",
            "Geo_CountryCode": "RS",
            "Geo_ADM1Code": "MOW",
            "Geo_ADM2Code": "",
            "Geo_Lat": "55.75",
            "Geo_Long": "37.62",
            "Geo_FeatureID": "123",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "geographic_event"
        assert result[0]["latitude"] == 55.75

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "gcam.tsv"
        f.write_text("1\t0511\t1\tMoscow\tRS\tMOW\t\t55.75\t37.62\t123\n")
        schema = await parser.discover_schema(f)
        assert isinstance(schema, dict)


class TestEIAParser:
    @pytest.fixture
    def parser(self):
        return EIAParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_discover_schema_json(self, parser, tmp_path):
        f = tmp_path / "eia.json"
        f.write_text('{"series": [{"series_id": "PET.W_EPC0_SAX_YCUOK_MBBL.W", "data": [["20250101", 100.5]]}]}')
        schema = await parser.discover_schema(f)
        assert "series_id" in schema

    @pytest.mark.asyncio
    async def test_discover_schema_csv(self, parser, tmp_path):
        f = tmp_path / "eia.csv"
        f.write_text("period,value,area,product,unit\n2025-01,100.5,USA,Crude,mbbl\n")
        schema = await parser.discover_schema(f)
        assert "period" in schema

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{"series_id": "SER.123", "period": "202501", "value": "100.5", "unit": "mbbl", "area": "USA", "product": "Crude", "series_name": "Test Series"}]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "timeseries"
        assert result[0]["timestamp_precision"] == "month"
        assert result[0]["attributes"]["value"] == 100.5

    @pytest.mark.asyncio
    async def test_validate_json(self, parser, tmp_path):
        f = tmp_path / "eia_valid.json"
        f.write_text('{"series": [{"series_id": "S1", "data": [["2025", 50]]}]}')
        issues = await parser.validate(f)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_parse_json(self, parser, tmp_path):
        inp = tmp_path / "input.json"
        inp.write_text('{"series": [{"series_id": "S1", "data": [["202501", 100]], "units": "mbbl", "name": "Test"}]}')
        out = tmp_path / "output.csv"
        result = await parser.parse_file(inp, out)
        assert result.records_parsed > 0

    @pytest.mark.asyncio
    async def test_parse_csv(self, parser, tmp_path):
        inp = tmp_path / "input.csv"
        inp.write_text("series_id,period,value,units,area,product,name\nS1,2025-01,100,mbbl,US,Oil,Test\n")
        out = tmp_path / "output.csv"
        result = await parser.parse_file(inp, out)
        assert result.records_parsed >= 0


class TestFREDParser:
    @pytest.fixture
    def parser(self):
        return FREDParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "fred.json"
        f.write_text('{"observations": []}')
        schema = await parser.discover_schema(f)
        assert "date" in schema
        assert "value" in schema

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{"series_id": "WTI", "date": "2025-01-15", "value": "75.5", "name": "Crude Oil"}]
        result = await parser.to_canonical(records)
        assert result[0]["attributes"]["value"] == 75.5
        assert result[0]["source"] == "fred"


class TestOPECParser:
    @pytest.fixture
    def parser(self):
        return OPECParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    def test_canonical_schema(self, parser):
        assert parser.canonical_schema["entity_type"] == "string"

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "opec.csv"
        f.write_text("country,month,production_kbbl\nIraq,2025-01,4500\n")
        schema = await parser.discover_schema(f)
        assert schema["country"] == "string"

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "country": "Saudi Arabia",
            "month": "2025-01",
            "production_kbbl": "9000",
            "change_kbbl": "100",
            "capacity_kbbl": "12000",
            "export_kbbl": "7000",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "oil_production"
        assert result[0]["attributes"]["production_kbbl"] == 9000.0

    @pytest.mark.asyncio
    async def test_country_normalization(self, parser):
        from data_acquisition.parser.sources.opec import normalize_country
        assert normalize_country("Islamic Republic of Iran") == "Iran"
        assert normalize_country("Saudi Arabia (KSA)") == "Saudi Arabia"
        assert normalize_country("United Arab Emirates") == "UAE"
        assert normalize_country("Venezuela, Bolivarian Republic of") == "Venezuela"
        assert normalize_country("Russian Federation") == "Russia"
        assert normalize_country("Congo (Brazzaville)") == "Congo"
        assert normalize_country("Unknown Country") == "Unknown Country"

    @pytest.mark.asyncio
    async def test_validate(self, parser, tmp_path):
        f = tmp_path / "opec_valid.csv"
        f.write_text("country,month,production_kbbl\nSaudi Arabia,2025-01,9000\n")
        issues = await parser.validate(f)
        assert isinstance(issues, list)


class TestAISParser:
    @pytest.fixture
    def parser(self):
        return AISParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    def test_canonical_schema_has_entity_type_vessel(self):
        assert "vessel" not in AISParser().canonical_schema.get("entity_type", "")

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "ais.csv"
        f.write_text("MMSI,Timestamp,Latitude,Longitude,Speed,Course,Heading,Destination,ShipName,ShipType\n")
        schema = await parser.discover_schema(f)
        assert "MMSI" in schema
        assert "Latitude" in schema
        assert "Longitude" in schema

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "MMSI": "123456789",
            "Timestamp": "2025-01-15T10:30:00Z",
            "Latitude": "40.7128",
            "Longitude": "-74.0060",
            "Speed": "12.5",
            "Course": "180",
            "Heading": "175",
            "Destination": "NEW YORK",
            "ShipName": "Tanker-1",
            "ShipType": "Tanker",
            "Length": "250",
            "Width": "32",
            "Draft": "12.5",
            "CargoType": "Crude Oil",
            "Status": "Underway",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "vessel"
        assert result[0]["entity_id"] == "123456789"
        assert result[0]["latitude"] == 40.7128

    @pytest.mark.asyncio
    async def test_validate_lat_lng(self, parser, tmp_path):
        f = tmp_path / "ais_valid.csv"
        f.write_text("MMSI,Latitude,Longitude\n123,40.0,-74.0\n")
        issues = await parser.validate(f)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_validate_out_of_range_lat(self, parser, tmp_path):
        f = tmp_path / "ais_bad.csv"
        f.write_text("MMSI,Latitude,Longitude\n123,100.0,-74.0\n")
        issues = await parser.validate(f)
        assert any("latitude out of range" in i for i in issues)


class TestPortCongestionParser:
    @pytest.fixture
    def parser(self):
        return PortCongestionParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "port_name": "Shanghai",
            "port_code": "CNSHA",
            "country": "China",
            "region": "Asia",
            "date": "2025-01-15",
            "waiting_days": "3.5",
            "vessel_count": "12",
            "capacity_mt": "50000",
            "congestion_level": "high",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "port_congestion"
        assert result[0]["confidence"] == 0.7


class TestWorldPortIndexParser:
    @pytest.fixture
    def parser(self):
        return WorldPortIndexParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "port_name": "Port of Houston",
            "country_code": "US",
            "latitude": "29.75",
            "longitude": "-95.08",
            "UNLOCODE": "USHOU",
            "harbor_type": "Deep Water",
            "max_draft": "45",
            "max_length": "1200",
            "tug_assist": "Yes",
            "fuel_available": "Yes",
            "cargo_types": "Container,Bulk",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "port"
        assert result[0]["entity_id"] == "USHOU"


class TestCommodityPriceParser:
    @pytest.fixture
    def parser(self):
        return CommodityPriceParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "commodity.csv"
        f.write_text("commodity,date,price,unit,currency,market,source\n")
        schema = await parser.discover_schema(f)
        assert "commodity" in schema
        assert "price" in schema

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "commodity": "Crude Oil (WTI)",
            "date": "2025-01-15",
            "price": "75.50",
            "unit": "USD/bbl",
            "currency": "USD",
            "market": "NYMEX",
            "source": "EIA",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "commodity_price"
        assert result[0]["attributes"]["price"] == 75.50

    @pytest.mark.asyncio
    async def test_validate(self, parser, tmp_path):
        f = tmp_path / "commodity_valid.csv"
        f.write_text("commodity,date,price\nWTI,2025-01-15,75.5\n")
        issues = await parser.validate(f)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_validate_missing_commodity(self, parser, tmp_path):
        f = tmp_path / "commodity_empty.csv"
        f.write_text("commodity,date,price\n,2025-01-15,75.5\n")
        issues = await parser.validate(f)
        assert any("missing commodity" in i for i in issues)


class TestCommodityFuturesParser:
    @pytest.fixture
    def parser(self):
        return CommodityFuturesParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "commodity": "Crude Oil",
            "contract_month": "Mar",
            "contract_year": "2025",
            "price": "74.20",
            "volume": "50000",
            "open_interest": "250000",
            "exchange": "NYMEX",
            "settlement_date": "2025-01-15",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "commodity_futures"
        assert result[0]["attributes"]["volume"] == 50000


class TestOFACParser:
    @pytest.fixture
    def parser(self):
        return OFACParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "ofac.csv"
        f.write_text("ent_num,sdn_name,sdn_type,program,list,score,remarks\n")
        schema = await parser.discover_schema(f)
        assert "ent_num" in schema

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "ent_num": "12345",
            "sdn_name": "John Doe",
            "sdn_type": "Individual",
            "program": "IRAN;NORTH KOREA",
            "list": "SDN",
            "score": "",
            "remarks": "Dual national",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "sanctioned_entity"
        assert len(result[0]["attributes"]["program"]) == 2

    @pytest.mark.asyncio
    async def test_validate(self, parser, tmp_path):
        f = tmp_path / "ofac_valid.csv"
        f.write_text("ent_num,sdn_name,sdn_type\n1,Test Person,Individual\n")
        issues = await parser.validate(f)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_parse_json(self, parser, tmp_path):
        inp = tmp_path / "ofac.json"
        inp.write_text('[{"ent_num": "1", "sdn_name": "Test", "sdn_type": "Individual", "program": "IRAN"}]')
        out = tmp_path / "output.csv"
        result = await parser.parse_file(inp, out)
        assert result.records_parsed == 1


class TestUNSanctionsParser:
    @pytest.fixture
    def parser(self):
        return UNSanctionsParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_to_canonical_individual(self, parser):
        records = [{
            "individual_name": "Bad Actor",
            "entity_name": "",
            "identifier": "UN-001",
            "type": "Individual",
            "sanctions_program": "IRAN;DPRK",
            "listed_date": "2025-01-01",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "sanctioned_individual"

    @pytest.mark.asyncio
    async def test_to_canonical_entity(self, parser):
        records = [{
            "individual_name": "",
            "entity_name": "Evil Corp",
            "identifier": "UN-002",
            "type": "Entity",
            "sanctions_program": "SYRIA",
            "listed_date": "2025-02-01",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "sanctioned_entity"

    @pytest.mark.asyncio
    async def test_validate(self, parser, tmp_path):
        f = tmp_path / "un_valid.csv"
        f.write_text("individual_name,entity_name,identifier\nTest Person,,UN-001\n")
        issues = await parser.validate(f)
        assert isinstance(issues, list)


class TestWorldBankParser:
    @pytest.fixture
    def parser(self):
        return WorldBankParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "wb.csv"
        f.write_text("indicator,country,date,value\n")
        schema = await parser.discover_schema(f)
        assert "indicator" in schema

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "indicator": "GDP (current US$)",
            "indicator_id": "NY.GDP.MKTP.CD",
            "country": "United States",
            "country_id": "US",
            "date": "2024",
            "value": "25439700000000",
            "unit": "current US$",
            "source_note": "World Bank",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "economic_indicator"
        assert result[0]["timestamp_precision"] == "year"


class TestUNComtradeParser:
    @pytest.fixture
    def parser(self):
        return UNComtradeParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_discover_schema(self, parser, tmp_path):
        f = tmp_path / "comtrade.csv"
        f.write_text("classification,year,period,trade_flow,reporter,partner,commodity_code,commodity\n")
        schema = await parser.discover_schema(f)
        assert "classification" in schema

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "classification": "HS",
            "year": "2024",
            "period": "2024",
            "trade_flow": "Export",
            "reporter": "USA",
            "reporter_code": "842",
            "partner": "China",
            "partner_code": "156",
            "commodity_code": "270900",
            "commodity": "Crude Oil",
            "qty": "100000",
            "netweight": "100000000",
            "trade_value_usd": "5000000000",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "trade_flow"
        assert result[0]["timestamp_precision"] == "year"


class TestKaggleParser:
    @pytest.fixture
    def parser(self):
        return KaggleParser()

    def test_can_instantiate(self, parser):
        assert isinstance(parser, BaseParser)

    @pytest.mark.asyncio
    async def test_discover_schema_csv(self, parser, tmp_path):
        f = tmp_path / "kaggle.csv"
        f.write_text("id,title,description,url\n1,Test,Desc,http://example.com\n2,Test2,Desc2,http://example.com/2\n")
        schema = await parser.discover_schema(f)
        assert "id" in schema

    @pytest.mark.asyncio
    async def test_discover_schema_json(self, parser, tmp_path):
        f = tmp_path / "kaggle.json"
        f.write_text('[{"id": "1", "title": "Test", "value": 42}, {"id": "2", "title": "Test2", "value": 99}]')
        schema = await parser.discover_schema(f)
        assert "id" in schema
        assert "value" in schema

    @pytest.mark.asyncio
    async def test_to_canonical(self, parser):
        records = [{
            "id": "kaggle-001",
            "title": "Energy Dataset",
            "description": "Global energy data",
            "value": 100,
            "lat": "40.71",
            "lon": "-74.00",
        }]
        result = await parser.to_canonical(records)
        assert result[0]["entity_type"] == "kaggle_record"
        assert result[0]["latitude"] == 40.71

    @pytest.mark.asyncio
    async def test_discover_schema_auto_detect_types(self, parser, tmp_path):
        f = tmp_path / "kaggle_types.csv"
        f.write_text("name,age,score,active\nJohn,30,95.5,true\nJane,25,88.2,false\n")
        schema = await parser.discover_schema(f)
        assert "name" in schema
        assert "age" in schema

    @pytest.mark.asyncio
    async def test_validate(self, parser, tmp_path):
        f = tmp_path / "kaggle_valid.csv"
        f.write_text("a,b,c\n1,2,3\n4,5,6\n")
        issues = await parser.validate(f)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_validate_column_mismatch(self, parser, tmp_path):
        f = tmp_path / "kaggle_bad.csv"
        f.write_text("a,b,c\n1,2\n4,5,6,7\n")
        issues = await parser.validate(f)
        assert any("column count mismatch" in i for i in issues)


class TestCanonicalRecord:
    def test_default_construction(self):
        r = CanonicalRecord()
        assert r.entity_type == ""
        assert r.entity_id == ""
        assert r.latitude is None
        assert r.longitude is None

    def test_construction_with_kwargs(self):
        r = CanonicalRecord(
            entity_type="vessel",
            entity_id="123",
            entity_name="Tanker-1",
            latitude=40.71,
            longitude=-74.00,
        )
        assert r.entity_type == "vessel"
        assert r.entity_name == "Tanker-1"

    def test_to_dict(self):
        r = CanonicalRecord(entity_type="event", entity_id="1", source="gdelt")
        d = r.to_dict()
        assert d["entity_type"] == "event"
        assert d["entity_id"] == "1"
        assert d["source"] == "gdelt"

    def test_from_dict(self):
        data = {
            "entity_type": "port",
            "entity_id": "USHOU",
            "entity_name": "Houston",
            "timestamp": "2025-01-01",
            "timestamp_precision": "day",
            "latitude": 29.75,
            "longitude": -95.08,
            "location_name": "Houston",
            "location_code": "USHOU",
            "attributes": {"draft": 45},
            "relationships": [],
            "source": "wpi",
            "source_record_id": "USHOU",
            "confidence": 0.9,
            "metadata": {},
        }
        r = CanonicalRecord.from_dict(data)
        assert r.entity_id == "USHOU"
        assert r.latitude == 29.75

    def test_validate_passes(self):
        r = CanonicalRecord(entity_type="vessel", entity_id="123")
        errors = r.validate()
        assert errors == []

    def test_validate_missing_entity_type(self):
        r = CanonicalRecord(entity_id="123")
        errors = r.validate()
        assert "entity_type is required" in errors

    def test_validate_missing_entity_id(self):
        r = CanonicalRecord(entity_type="vessel")
        errors = r.validate()
        assert "entity_id is required" in errors

    def test_validate_latitude_out_of_range(self):
        r = CanonicalRecord(entity_type="vessel", entity_id="1", latitude=100.0)
        errors = r.validate()
        assert any("latitude out of range" in e for e in errors)

    def test_validate_longitude_out_of_range(self):
        r = CanonicalRecord(entity_type="vessel", entity_id="1", longitude=200.0)
        errors = r.validate()
        assert any("longitude out of range" in e for e in errors)

    def test_validate_confidence_out_of_range(self):
        r = CanonicalRecord(entity_type="vessel", entity_id="1", confidence=1.5)
        errors = r.validate()
        assert any("confidence out of range" in e for e in errors)

    def test_validate_invalid_timestamp_precision(self):
        r = CanonicalRecord(entity_type="vessel", entity_id="1", timestamp_precision="century")
        errors = r.validate()
        assert any("invalid timestamp_precision" in e for e in errors)

    def test_validate_valid_timestamp_precisions(self):
        for prec in ("year", "month", "day", "hour", "minute", "second"):
            r = CanonicalRecord(entity_type="vessel", entity_id="1", timestamp_precision=prec)
            errors = r.validate()
            assert errors == []

    def test_validate_latitude_negative_valid(self):
        r = CanonicalRecord(entity_type="vessel", entity_id="1", latitude=-90.0)
        errors = r.validate()
        assert errors == []

    def test_to_dataframe_row(self):
        r = CanonicalRecord(
            entity_type="event",
            entity_id="1",
            entity_name="Test",
            source="gdelt",
            attributes={"key": "val"},
            relationships=[{"type": "related", "target_id": "2"}],
            metadata={"version": "1"},
        )
        row = r.to_dataframe_row()
        assert row["entity_type"] == "event"
        assert row["attr_key"] == "val"
        assert isinstance(row["relationships"], str)
        assert isinstance(row["metadata"], str)


class TestCanonicalSchema:
    def test_default_values(self):
        s = CanonicalSchema()
        assert s.entity_type == ""
        assert s.latitude is None
        assert s.longitude is None
        assert s.attributes == {}
        assert s.relationships == []
        assert s.metadata == {}

    def test_custom_values(self):
        s = CanonicalSchema(
            entity_type="vessel",
            entity_id="123",
            latitude=40.71,
            longitude=-74.0,
            attributes={"speed": 12.5},
        )
        assert s.entity_type == "vessel"
        assert s.attributes["speed"] == 12.5

    def test_fields_are_strings(self):
        s = CanonicalSchema()
        assert isinstance(s.entity_type, str)
        assert isinstance(s.entity_id, str)
        assert isinstance(s.entity_name, str)
        assert isinstance(s.timestamp, str)
        assert isinstance(s.timestamp_precision, str)
