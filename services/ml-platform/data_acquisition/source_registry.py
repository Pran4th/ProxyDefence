from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceDefinition:
    name: str
    display_name: str
    description: str
    category: str
    update_frequency: str
    connector_type: str
    default_parser: str
    url_template: str | None = None
    expected_schema: dict[str, str] = field(default_factory=dict)
    version: str = "1.0"
    license: str = ""
    citation: str = ""
    tags: list[str] = field(default_factory=list)
    is_active: bool = True


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, SourceDefinition] = {}

    def register(self, definition: SourceDefinition) -> None:
        self._sources[definition.name] = definition

    def get(self, name: str) -> SourceDefinition | None:
        return self._sources.get(name)

    def list_sources(
        self, category: str | None = None, active_only: bool = True
    ) -> list[SourceDefinition]:
        results: list[SourceDefinition] = []
        for s in self._sources.values():
            if active_only and not s.is_active:
                continue
            if category and s.category != category:
                continue
            results.append(s)
        return results

    def get_categories(self) -> list[str]:
        return sorted({s.category for s in self._sources.values()})

    def get_by_connector(self, connector_type: str) -> list[SourceDefinition]:
        return [s for s in self._sources.values() if s.connector_type == connector_type]

    def remove(self, name: str) -> None:
        self._sources.pop(name, None)


_gdelt_schema: dict[str, str] = {
    "GLOBALEVENTID": "int",
    "SQLDATE": "date",
    "MonthYear": "int",
    "Year": "int",
    "FractionDate": "float",
    "Actor1Code": "str",
    "Actor1Name": "str",
    "Actor1CountryCode": "str",
    "Actor1KnownGroupCode": "str",
    "Actor1EthnicCode": "str",
    "Actor1Religion1Code": "str",
    "Actor1Religion2Code": "str",
    "Actor1Type1Code": "str",
    "Actor1Type2Code": "str",
    "Actor1Type3Code": "str",
    "Actor2Code": "str",
    "Actor2Name": "str",
    "Actor2CountryCode": "str",
    "Actor2KnownGroupCode": "str",
    "Actor2EthnicCode": "str",
    "Actor2Religion1Code": "str",
    "Actor2Religion2Code": "str",
    "Actor2Type1Code": "str",
    "Actor2Type2Code": "str",
    "Actor2Type3Code": "str",
    "IsRootEvent": "int",
    "EventCode": "str",
    "EventBaseCode": "str",
    "EventRootCode": "str",
    "QuadClass": "int",
    "GoldsteinScale": "float",
    "NumMentions": "int",
    "NumSources": "int",
    "NumArticles": "int",
    "AvgTone": "float",
    "Actor1Geo_Type": "int",
    "Actor1Geo_FullName": "str",
    "Actor1Geo_CountryCode": "str",
    "Actor1Geo_ADM1Code": "str",
    "Actor1Geo_Lat": "float",
    "Actor1Geo_Long": "float",
    "Actor1Geo_FeatureID": "str",
    "Actor2Geo_Type": "int",
    "Actor2Geo_FullName": "str",
    "Actor2Geo_CountryCode": "str",
    "Actor2Geo_ADM1Code": "str",
    "Actor2Geo_Lat": "float",
    "Actor2Geo_Long": "float",
    "Actor2Geo_FeatureID": "str",
    "ActionGeo_Type": "int",
    "ActionGeo_FullName": "str",
    "ActionGeo_CountryCode": "str",
    "ActionGeo_ADM1Code": "str",
    "ActionGeo_Lat": "float",
    "ActionGeo_Long": "float",
    "ActionGeo_FeatureID": "str",
    "DATEADDED": "int",
    "SOURCEURL": "str",
}

_eia_schema: dict[str, str] = {
    "period": "date",
    "duoarea": "str",
    "area-name": "str",
    "product": "str",
    "product-name": "str",
    "series": "str",
    "series-description": "str",
    "value": "float",
    "units": "str",
}

_fred_schema: dict[str, str] = {
    "date": "date",
    "value": "float",
    "realtime_start": "date",
    "realtime_end": "date",
}

_opec_schema: dict[str, str] = {
    "year": "int",
    "month": "int",
    "country": "str",
    "production_bpd": "float",
    "change_from_previous": "float",
}

_ais_schema: dict[str, str] = {
    "mmsi": "int",
    "timestamp": "datetime",
    "latitude": "float",
    "longitude": "float",
    "speed": "float",
    "course": "float",
    "heading": "float",
    "destination": "str",
    "vessel_name": "str",
    "vessel_type": "str",
}

_port_congestion_schema: dict[str, str] = {
    "port_name": "str",
    "port_code": "str",
    "country": "str",
    "date": "date",
    "waiting_vessels": "int",
    "avg_wait_hours": "float",
    "congestion_index": "float",
    "total_berthed": "int",
}

_commodity_schema: dict[str, str] = {
    "date": "date",
    "commodity": "str",
    "price": "float",
    "currency": "str",
    "unit": "str",
    "change_pct": "float",
}

_ofac_schema: dict[str, str] = {
    "uid": "int",
    "firstName": "str",
    "lastName": "str",
    "sdnType": "str",
    "program": "str",
    "title": "str",
    "callSign": "str",
    "vesselType": "str",
    "tonnage": "str",
    "grt": "str",
    "nationality": "str",
    "city": "str",
    "country": "str",
    "address": "str",
    "remarks": "str",
}

_world_bank_schema: dict[str, str] = {
    "indicator": "str",
    "country": "str",
    "country_code": "str",
    "year": "int",
    "value": "float",
}

_un_comtrade_schema: dict[str, str] = {
    "year": "int",
    "period": "str",
    "trade_flow": "str",
    "reporter": "str",
    "reporter_code": "int",
    "partner": "str",
    "partner_code": "int",
    "commodity_code": "str",
    "commodity": "str",
    "trade_value_usd": "float",
    "net_weight_kg": "float",
    "quantity": "float",
}

_kaggle_schema: dict[str, str] = {
    "id": "str",
    "title": "str",
    "description": "str",
    "url": "str",
    "dataset_size": "int",
    "file_count": "int",
    "downloads": "int",
    "last_updated": "date",
}

_world_port_index_schema: dict[str, str] = {
    "port_name": "str",
    "country": "str",
    "unlocode": "str",
    "latitude": "float",
    "longitude": "float",
    "harbor_size": "str",
    "harbor_type": "str",
    "max_draft": "float",
    "max_vessel_length": "float",
    "cargo_types": "str",
}

DATASET_REGISTRY: list[SourceDefinition] = [
    # Geopolitical
    SourceDefinition(
        name="gdelt-events",
        display_name="GDELT Events",
        description="Global Database of Events, Language, and Tone — event records covering worldwide political and social developments",
        category="geopolitical",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="GDELTEventParser",
        url_template="http://gdeltproject.org/data/{version}/export.CSV.zip",
        expected_schema=_gdelt_schema,
        version="2.0",
        license="CC BY 4.0",
        citation="Leetaru, K., & Schrodt, P. A. (2013). GDELT: Global Data on Events, Location and Tone.",
        tags=["gdelt", "events", "political", "conflict", "global"],
    ),
    SourceDefinition(
        name="gdelt-mentions",
        display_name="GDELT Mentions",
        description="GDELT Mentions — individual mentions of events across global news sources",
        category="geopolitical",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="GDELTMentionParser",
        url_template="http://gdeltproject.org/data/{version}/mentions.CSV.zip",
        expected_schema={"GLOBALEVENTID": "int", "EventTimeDate": "date", "MentionTimeDate": "date", "MentionType": "int", "MentionSourceName": "str", "MentionIdentifier": "str", "MentionDocTone": "float", "Confidence": "int"},
        version="2.0",
        license="CC BY 4.0",
        citation="Leetaru, K., & Schrodt, P. A. (2013). GDELT: Global Data on Events, Location and Tone.",
        tags=["gdelt", "mentions", "media", "coverage"],
    ),
    SourceDefinition(
        name="gdelt-gkg",
        display_name="GDELT Global Knowledge Graph",
        description="GDELT Global Knowledge Graph — extracted entities, themes, and emotions from global news",
        category="geopolitical",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="GKGParser",
        url_template="http://gdeltproject.org/data/{version}/GKG.CSV.zip",
        expected_schema={"GKGRECORDID": "str", "DATE": "date", "SourceCollectionIdentifier": "int", "SourceCommonName": "str", "DocumentIdentifier": "str", "Counts": "str", "V2.1Themes": "str", "V2.1Locations": "str", "V2.1Persons": "str", "V2.1Organizations": "str", "V2.1Tone": "str"},
        version="2.0",
        license="CC BY 4.0",
        citation="Leetaru, K., & Schrodt, P. A. (2013). GDELT: Global Data on Events, Location and Tone.",
        tags=["gdelt", "knowledge-graph", "entities", "themes"],
    ),
    SourceDefinition(
        name="gdelt-gcam",
        display_name="GDELT Geographic CAMEO",
        description="GDELT Geographic CAMEO — geographic coding of CAMEO event data for geospatial analysis",
        category="geopolitical",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="GCAMParser",
        url_template="http://gdeltproject.org/data/{version}/GCAM.CSV.zip",
        expected_schema={"GLOBALEVENTID": "int", "CAMEO_CODE": "str", "GEO_LAT": "float", "GEO_LONG": "float", "GEO_FULLNAME": "str", "GEO_COUNTRY": "str", "GEO_ADM1": "str", "GEO_FEATUREID": "str"},
        version="2.0",
        license="CC BY 4.0",
        citation="Leetaru, K., & Schrodt, P. A. (2013). GDELT: Global Data on Events, Location and Tone.",
        tags=["gdelt", "cameo", "geographic", "geospatial"],
    ),
    # Energy
    SourceDefinition(
        name="eia-petroleum",
        display_name="EIA Weekly Petroleum",
        description="US Energy Information Administration — Weekly Petroleum Status Report",
        category="energy",
        update_frequency="weekly",
        connector_type="rest_api",
        default_parser="EIAParser",
        url_template="https://api.eia.gov/v2/petroleum/{endpoint}/data/",
        expected_schema=_eia_schema,
        license="Open Data (US Gov)",
        citation="U.S. Energy Information Administration. Weekly Petroleum Status Report.",
        tags=["eia", "petroleum", "oil", "supply", "us"],
    ),
    SourceDefinition(
        name="eia-natural-gas",
        display_name="EIA Natural Gas",
        description="US Energy Information Administration — Natural Gas Storage, Production, and Consumption",
        category="energy",
        update_frequency="weekly",
        connector_type="rest_api",
        default_parser="EIAParser",
        url_template="https://api.eia.gov/v2/natural-gas/{endpoint}/data/",
        expected_schema=_eia_schema,
        license="Open Data (US Gov)",
        citation="U.S. Energy Information Administration. Natural Gas Data.",
        tags=["eia", "natural-gas", "storage", "production"],
    ),
    SourceDefinition(
        name="eia-coal",
        display_name="EIA Coal",
        description="US Energy Information Administration — Coal production, consumption, exports, and inventories",
        category="energy",
        update_frequency="monthly",
        connector_type="rest_api",
        default_parser="EIAParser",
        url_template="https://api.eia.gov/v2/coal/{endpoint}/data/",
        expected_schema=_eia_schema,
        license="Open Data (US Gov)",
        citation="U.S. Energy Information Administration. Coal Data.",
        tags=["eia", "coal", "production", "inventory"],
    ),
    SourceDefinition(
        name="eia-electricity",
        display_name="EIA Electricity",
        description="US Energy Information Administration — Electricity generation, consumption, and capacity",
        category="energy",
        update_frequency="monthly",
        connector_type="rest_api",
        default_parser="EIAParser",
        url_template="https://api.eia.gov/v2/electricity/{endpoint}/data/",
        expected_schema=_eia_schema,
        license="Open Data (US Gov)",
        citation="U.S. Energy Information Administration. Electricity Data.",
        tags=["eia", "electricity", "generation", "capacity"],
    ),
    SourceDefinition(
        name="fred-oil-prices",
        display_name="FRED Crude Oil Prices",
        description="Federal Reserve Economic Data — Crude Oil Prices: West Texas Intermediate (WTI)",
        category="energy",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="FREDParser",
        url_template="https://api.stlouisfed.org/fred/series/observations?series_id={series_id}",
        expected_schema=_fred_schema,
        license="Open Data (FRED)",
        citation="Federal Reserve Bank of St. Louis. FRED Economic Data. Retrieved from FRED.",
        tags=["fred", "oil", "wti", "crude", "prices"],
    ),
    SourceDefinition(
        name="fred-gas-prices",
        display_name="FRED Natural Gas Prices",
        description="Federal Reserve Economic Data — Natural Gas Prices (Henry Hub)",
        category="energy",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="FREDParser",
        url_template="https://api.stlouisfed.org/fred/series/observations?series_id={series_id}",
        expected_schema=_fred_schema,
        license="Open Data (FRED)",
        citation="Federal Reserve Bank of St. Louis. FRED Economic Data. Retrieved from FRED.",
        tags=["fred", "natural-gas", "henry-hub", "prices"],
    ),
    SourceDefinition(
        name="opec-production",
        display_name="OPEC Monthly Production",
        description="Organization of the Petroleum Exporting Countries — Monthly Oil Production by Member Country",
        category="energy",
        update_frequency="monthly",
        connector_type="csv",
        default_parser="OPECParser",
        url_template="https://www.opec.org/opec_web/en/data_graphs/{dataset}.csv",
        expected_schema=_opec_schema,
        license="OPEC Data (Attribution Required)",
        citation="Organization of the Petroleum Exporting Countries. Monthly Oil Market Report.",
        tags=["opec", "production", "oil", "monthly"],
    ),
    SourceDefinition(
        name="opec-exports",
        display_name="OPEC Exports",
        description="Organization of the Petroleum Exporting Countries — Monthly Crude Oil Exports by Destination",
        category="energy",
        update_frequency="monthly",
        connector_type="csv",
        default_parser="OPECParser",
        url_template="https://www.opec.org/opec_web/en/data_graphs/{dataset}.csv",
        expected_schema=_opec_schema,
        license="OPEC Data (Attribution Required)",
        citation="Organization of the Petroleum Exporting Countries. Monthly Oil Market Report.",
        tags=["opec", "exports", "oil", "trade-flows"],
    ),
    # Shipping
    SourceDefinition(
        name="ais-global",
        display_name="AIS Global Shipping",
        description="Automatic Identification System — global vessel tracking and maritime traffic data",
        category="shipping",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="AISParser",
        url_template="https://ais.{}",
        expected_schema=_ais_schema,
        license="Varies by Provider",
        citation="Various AIS data providers.",
        tags=["ais", "shipping", "maritime", "vessel-tracking"],
    ),
    SourceDefinition(
        name="port-congestion",
        display_name="Port Congestion Index",
        description="Global port congestion metrics — waiting times, vessel queue counts, congestion indices",
        category="shipping",
        update_frequency="weekly",
        connector_type="csv",
        default_parser="PortCongestionParser",
        expected_schema=_port_congestion_schema,
        license="Varies by Provider",
        citation="Various port authority and maritime analytics providers.",
        tags=["port", "congestion", "shipping", "logistics"],
    ),
    SourceDefinition(
        name="world-port-index",
        display_name="World Port Index",
        description="NGIA World Port Index — comprehensive global port database with location, facilities, and characteristics",
        category="shipping",
        update_frequency="yearly",
        connector_type="csv",
        default_parser="WorldPortIndexParser",
        url_template="https://msi.nga.mil/api/publications/download?key={key}",
        expected_schema=_world_port_index_schema,
        license="Open Data (US Gov)",
        citation="National Geospatial-Intelligence Agency. World Port Index.",
        tags=["port", "index", "maritime", "infrastructure"],
    ),
    # Commodity
    SourceDefinition(
        name="commodity-prices",
        display_name="Commodity Price Index",
        description="Global commodity price indices — energy, metals, agriculture, and soft commodities",
        category="commodity",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="CommodityPriceParser",
        url_template="https://api.{provider}/commodity/prices",
        expected_schema=_commodity_schema,
        license="Varies by Provider",
        citation="Various commodity price data providers.",
        tags=["commodity", "prices", "indices", "markets"],
    ),
    SourceDefinition(
        name="commodity-futures",
        display_name="Commodity Futures",
        description="Global commodity futures and derivatives market data — open interest, volume, settlement prices",
        category="commodity",
        update_frequency="daily",
        connector_type="rest_api",
        default_parser="CommodityFuturesParser",
        url_template="https://api.{provider}/futures/{symbol}",
        expected_schema={"date": "date", "symbol": "str", "contract": "str", "expiry": "date", "open": "float", "high": "float", "low": "float", "close": "float", "volume": "int", "open_interest": "int"},
        license="Varies by Exchange",
        citation="Various futures exchange data providers.",
        tags=["futures", "commodity", "derivatives", "markets"],
    ),
    # Sanctions
    SourceDefinition(
        name="ofac-sanctions",
        display_name="OFAC Sanctions List",
        description="US Office of Foreign Assets Control — Specially Designated Nationals and Blocked Persons List (SDN)",
        category="sanctions",
        update_frequency="daily",
        connector_type="csv",
        default_parser="OFACParser",
        url_template="https://www.treasury.gov/ofac/downloads/sdn.csv",
        expected_schema=_ofac_schema,
        license="Open Data (US Gov)",
        citation="U.S. Department of the Treasury. OFAC SDN List.",
        tags=["ofac", "sanctions", "sdn", "compliance"],
    ),
    SourceDefinition(
        name="un-sanctions",
        display_name="UN Sanctions",
        description="United Nations Security Council — consolidated sanctions list covering all active UN sanctions regimes",
        category="sanctions",
        update_frequency="on_demand",
        connector_type="csv",
        default_parser="UNSanctionsParser",
        url_template="https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        expected_schema={"id": "int", "name": "str", "type": "str", "sanctions_regime": "str", "listed_date": "date", "nationality": "str", "remarks": "str"},
        license="Open Data (UN)",
        citation="United Nations Security Council. Consolidated United Nations Sanctions List.",
        tags=["un", "sanctions", "compliance", "international"],
    ),
    # Economics
    SourceDefinition(
        name="world-bank-indicators",
        display_name="World Bank Indicators",
        description="World Bank Open Data — global development indicators covering economics, health, education, and infrastructure",
        category="economics",
        update_frequency="yearly",
        connector_type="rest_api",
        default_parser="WorldBankParser",
        url_template="https://api.worldbank.org/v2/country/{country}/indicator/{indicator}",
        expected_schema=_world_bank_schema,
        license="CC BY 4.0",
        citation="The World Bank. World Development Indicators.",
        tags=["world-bank", "development", "indicators", "economics"],
    ),
    SourceDefinition(
        name="un-comtrade",
        display_name="UN Comtrade",
        description="United Nations International Trade Statistics — global import and export data by commodity and country",
        category="economics",
        update_frequency="monthly",
        connector_type="rest_api",
        default_parser="UNComtradeParser",
        url_template="https://comtrade.un.org/api/get?{params}",
        expected_schema=_un_comtrade_schema,
        license="Open Data (UN)",
        citation="United Nations. UN Comtrade Database.",
        tags=["comtrade", "trade", "imports", "exports", "commodities"],
    ),
    # Other
    SourceDefinition(
        name="kaggle-competition",
        display_name="Kaggle Competition",
        description="Kaggle competition datasets — structured datasets from active and past Kaggle competitions",
        category="other",
        update_frequency="on_demand",
        connector_type="csv",
        default_parser="KaggleParser",
        url_template="https://www.kaggle.com/api/v1/competitions/{name}/download/{file}",
        expected_schema=_kaggle_schema,
        license="Varies per Competition",
        citation="Kaggle. https://www.kaggle.com",
        tags=["kaggle", "competition", "ml"],
    ),
    SourceDefinition(
        name="kaggle-dataset",
        display_name="Kaggle Dataset",
        description="Kaggle community datasets — user-contributed datasets across all domains and sizes",
        category="other",
        update_frequency="on_demand",
        connector_type="csv",
        default_parser="KaggleParser",
        url_template="https://www.kaggle.com/api/v1/datasets/{owner}/{name}/download",
        expected_schema=_kaggle_schema,
        license="Varies per Dataset",
        citation="Kaggle. https://www.kaggle.com",
        tags=["kaggle", "dataset", "community"],
    ),
]
