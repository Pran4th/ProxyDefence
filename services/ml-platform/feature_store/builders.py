import asyncio
from typing import Any

import asyncpg
import numpy as np
import pandas as pd
import requests

from backend.shared.logging_config import get_logger
from config import ENERGY_SERVICE_URL
from db import get_pool

logger = get_logger(__name__)

ENERGY_TABLES = [
    "locations", "organizations", "commodities", "ports",
    "oil_fields", "gas_fields", "pipelines", "refineries",
    "power_plants", "storage_facilities",
    "strategic_petroleum_reserves", "import_corridors",
    "shipping_routes", "suppliers",
]


class FeatureBuilder:
    def __init__(self, feature_registry: Any):
        self._registry = feature_registry

    async def compute_feature(self, feature_def: dict[str, Any], df: pd.DataFrame) -> pd.Series:
        ftype = feature_def["feature_type"]
        config = feature_def.get("transform_config", {}) or {}
        name = feature_def["name"]

        if ftype == "numerical":
            col = config.get("source_column", name)
            return df[col] if col in df.columns else pd.Series(0.0, index=df.index)
        elif ftype == "categorical":
            col = config.get("source_column", name)
            return df[col].astype(str) if col in df.columns else pd.Series("unknown", index=df.index)
        elif ftype == "boolean":
            col = config.get("source_column", name)
            return df[col].astype(bool) if col in df.columns else pd.Series(False, index=df.index)
        elif ftype == "geospatial":
            lat_col = config.get("latitude_column", "latitude")
            lng_col = config.get("longitude_column", "longitude")
            chokepoint = config.get("chokepoint", "hormuz")
            if lat_col in df.columns and lng_col in df.columns:
                from feature_store.transforms import GeospatialTransform
                t = GeospatialTransform(lat_col, lng_col, chokepoint, name)
                return t.transform(df)
            return pd.Series(0.0, index=df.index)
        else:
            logger.warning("feature type %s not yet implemented, returning zeros", ftype)
            return pd.Series(0.0, index=df.index)

    async def compute_all(self, feature_defs: list[dict], df: pd.DataFrame) -> pd.DataFrame:
        series_list = await asyncio.gather(*[
            self.compute_feature(fd, df) for fd in feature_defs
        ])
        result = pd.concat(series_list, axis=1)
        result.columns = [fd["name"] for fd in feature_defs]
        return result


class EnergyServiceDataLoader:
    def __init__(self, base_url: str = ENERGY_SERVICE_URL):
        self._base_url = base_url

    def fetch_table(self, table: str) -> pd.DataFrame:
        url = f"{self._base_url}/api/v1/energy/{table}?limit=10000"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if items:
                return pd.DataFrame(items)
            return pd.DataFrame()
        except requests.RequestException as e:
            logger.warning("failed to fetch %s: %s", table, e)
            return pd.DataFrame()

    def fetch_all(self) -> dict[str, pd.DataFrame]:
        tables = {}
        for table in ENERGY_TABLES:
            df = self.fetch_table(table)
            if not df.empty:
                tables[table] = df
                logger.info("loaded %s: %d records", table, len(df))
        return tables

    def build_feature_matrix(self, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
        if "ports" in tables:
            df = tables["ports"].copy()
        elif "oil_fields" in tables:
            df = tables["oil_fields"].copy()
        elif tables:
            df = next(iter(tables.values())).copy()
        else:
            df = pd.DataFrame()

        if "locations" in tables and "location_id" in df.columns:
            locs = tables["locations"][["uuid", "region", "iso_code", "location_type"]].copy()
            locs.columns = ["location_id", "region", "iso_code", "location_type"]
            df = df.merge(locs, on="location_id", how="left")

        if "organizations" in tables and "organization_id" in df.columns:
            orgs = tables["organizations"][["id", "organization_type"]].copy()
            orgs.columns = ["organization_id", "organization_type"]
            df = df.merge(orgs, on="organization_id", how="left")

        if "ports" in tables and "location_id" in tables["ports"].columns:
            counts = tables["ports"].groupby("location_id").size().reset_index(name="num_ports_in_country")
            df = df.merge(counts, on="location_id", how="left")

        if "refineries" in tables and "location_id" in tables["refineries"].columns:
            counts = tables["refineries"].groupby("location_id").size().reset_index(name="num_refineries_in_country")
            df = df.merge(counts, on="location_id", how="left")

        if "oil_fields" in tables and "location_id" in tables["oil_fields"].columns:
            prod = tables["oil_fields"].groupby("location_id")["production_bpd"].sum().reset_index(name="total_oil_production_bpd")
            df = df.merge(prod, on="location_id", how="left")

        drop_cols = ["uuid", "slug", "id", "created_at", "updated_at", "deleted_at", "geojson",
                     "external_references", "risk_metadata", "graph_metadata", "metadata",
                     "created_by", "updated_by", "deleted_by", "last_verified",
                     "source_type", "source_name", "source_url", "source_version", "ingested_at",
                     "notes", "description"]
        for col in drop_cols:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        return df

    def generate_synthetic(self, n_samples: int = 1000) -> pd.DataFrame:
        rs = np.random.RandomState(42)

        data = {
            "region": rs.choice(["middle_east", "north_america", "europe", "asia", "africa", "south_america"], n_samples),
            "organization_type": rs.choice(["national_oil_company", "international_oil_company", "independent", "government"], n_samples),
            "port_type": rs.choice(["crude_export", "refined_export", "lng_export"], n_samples),
            "operational_status": rs.choice(["active", "maintenance", "offline"], n_samples, p=[0.7, 0.2, 0.1]),
            "throughput_mtpa": rs.exponential(50, n_samples) * rs.uniform(0.5, 2.0, n_samples),
            "storage_capacity_barrels": rs.exponential(5e6, n_samples) * rs.uniform(0.5, 2.0, n_samples),
            "production_bpd": rs.exponential(200000, n_samples) * rs.uniform(0.5, 2.0, n_samples),
            "num_ports_in_country": rs.randint(1, 15, n_samples),
            "num_refineries_in_country": rs.randint(0, 10, n_samples),
            "total_oil_production_bpd": rs.exponential(1e6, n_samples),
        }

        return pd.DataFrame(data)
