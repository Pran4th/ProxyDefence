from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from data_acquisition.parser.base import BaseParser, ParseConfig, ParserResult

logger = get_logger(__name__)


COMMODITY_PRICE_FIELDS = [
    "commodity", "date", "price", "unit", "currency", "market", "source",
]

COMMODITY_FUTURES_FIELDS = [
    "commodity", "contract_month", "contract_year", "price",
    "volume", "open_interest", "exchange", "settlement_date",
]


class CommodityPriceParser(BaseParser):
    @property
    def canonical_schema(self) -> dict:
        return {
            "entity_type": "string",
            "entity_id": "string",
            "entity_name": "string",
            "timestamp": "string",
            "timestamp_precision": "string",
            "latitude": "float",
            "longitude": "float",
            "location_name": "string",
            "location_code": "string",
            "attributes": "dict",
            "relationships": "list",
            "source": "string",
            "source_record_id": "string",
            "confidence": "float",
            "metadata": "dict",
        }

    async def parse(self, config: ParseConfig) -> ParserResult:
        return await self.parse_file(
            config.input_path, config.output_path,
            encoding=config.encoding, max_records=config.max_records,
            batch_size=config.batch_size,
        )

    async def parse_file(
        self, input_path: Path, output_path: Path, **kwargs: Any
    ) -> ParserResult:
        start = time.monotonic()
        errors: list[dict] = []
        records_parsed = 0
        records_failed = 0
        max_records = kwargs.get("max_records")
        encoding = kwargs.get("encoding", "utf-8")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        schema = await self.discover_schema(input_path)
        suffix = input_path.suffix.lower()

        canonical_records: list[dict] = []

        if suffix == ".json":
            with open(input_path, "r", encoding=encoding) as f:
                data = json.load(f)

            dataset = data.get("data", data.get("dataset", data))
            if isinstance(dataset, dict):
                series = dataset.get("series", dataset.get("data", []))
            else:
                series = dataset

            for item in series:
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "commodity": item.get("commodity", item.get("name", item.get("series_id", ""))),
                        "date": item.get("date", item.get("period", item.get("timestamp", ""))),
                        "price": item.get("price", item.get("value", item.get("close"))),
                        "unit": item.get("unit", item.get("units", "")),
                        "currency": item.get("currency", item.get("Currency", "USD")),
                        "market": item.get("market", item.get("exchange", item.get("Market", ""))),
                        "source": item.get("source", item.get("Source", "")),
                    }
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"record": records_parsed, "error": str(e)})
        else:
            with open(input_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                fuel_cols = [
                    c for c in fieldnames
                    if c.startswith("fuel_") and not c.startswith(("o_fuel_", "h_fuel_", "l_fuel_", "c_fuel_"))
                ]
                is_wide_fuel_panel = "mkt_name" in fieldnames and bool(fuel_cols)

                for row_idx, row in enumerate(reader):
                    if max_records is not None and records_parsed >= max_records:
                        break
                    if is_wide_fuel_panel:
                        try:
                            recs = self._melt_fuel_panel_row(row, fuel_cols)
                            canonical = await self.to_canonical(recs)
                            canonical_records.extend(canonical)
                            records_parsed += len(recs)
                        except Exception as e:
                            records_failed += 1
                            errors.append({"row": row_idx, "error": str(e)})
                        continue
                    try:
                        rec = {
                            "commodity": row.get("commodity", row.get("Commodity", row.get("name", ""))),
                            "date": row.get("date", row.get("Date", row.get("period", ""))),
                            "price": row.get("price", row.get("Price", row.get("value", row.get("close")))),
                            "unit": row.get("unit", row.get("Unit", row.get("units", ""))),
                            "currency": row.get("currency", row.get("Currency", "USD")),
                            "market": row.get("market", row.get("Market", row.get("exchange", ""))),
                            "source": row.get("source", row.get("Source", "")),
                        }
                        canonical = await self.to_canonical([rec])
                        canonical_records.extend(canonical)
                        records_parsed += 1
                    except Exception as e:
                        records_failed += 1
                        errors.append({"row": row_idx, "error": str(e)})

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            if canonical_records:
                writer = csv.DictWriter(out_f, fieldnames=list(canonical_records[0].keys()))
                writer.writeheader()
                writer.writerows(canonical_records)

        return ParserResult(
            source="commodity_price",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=COMMODITY_PRICE_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "commodity": "string",
            "date": "string",
            "price": "number",
            "unit": "string",
            "currency": "string",
            "market": "string",
            "source": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if row_idx > 1000:
                        break
                    if not row.get("commodity", "").strip() and not row.get("Commodity", "").strip():
                        issues.append(f"Row {row_idx}: missing commodity identifier")
        except Exception as e:
            issues.append(f"Validation error: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        line_count = 0
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in f:
                line_count += 1
        return {
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "line_count": line_count,
            "field_count": len(COMMODITY_PRICE_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            date = rec.get("date", "")
            if re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                precision = "day"
            elif re.match(r"^\d{4}-\d{2}$", date):
                precision = "month"
            elif re.match(r"^\d{4}$", date):
                precision = "year"
            else:
                precision = "day"

            commodity = rec.get("commodity", "").strip().lower().replace(" ", "_")
            entity_id = f"{commodity}_{rec.get('market', '')}_{rec.get('date', '')}"
            canonical.append({
                "entity_type": "commodity_price",
                "entity_id": entity_id,
                "entity_name": rec.get("commodity", ""),
                "timestamp": rec.get("date", ""),
                "timestamp_precision": precision,
                "latitude": self._safe_float(rec.get("latitude")),
                "longitude": self._safe_float(rec.get("longitude")),
                "location_name": rec.get("market"),
                "location_code": rec.get("country_code") or rec.get("market"),
                "attributes": {
                    "commodity": rec.get("commodity"),
                    "price": self._safe_float(rec.get("price")),
                    "unit": rec.get("unit"),
                    "currency": rec.get("currency"),
                    "market": rec.get("market"),
                    "country": rec.get("country"),
                    "country_code": rec.get("country_code"),
                    "inflation_pct": self._safe_float(rec.get("inflation_pct")),
                    "data_trust_score": self._safe_float(rec.get("data_trust_score")),
                    "source_name": rec.get("source"),
                },
                "relationships": [
                    {"type": "traded_on", "target_id": rec.get("market")},
                ],
                "source": rec.get("source", "commodity"),
                "source_record_id": entity_id,
                "confidence": self._safe_float(rec.get("data_trust_score")),
                "metadata": {"parser": "CommodityPriceParser", "version": "1.0"},
            })
        return canonical

    def _melt_fuel_panel_row(self, row: dict, fuel_cols: list[str]) -> list[dict]:
        """Melts one wide fuel-price-panel row (WFP-style: fuel_<type>, o_/h_/l_/c_/inflation_/trust_ prefixes)
        into one canonical price record per fuel type present in that row."""
        records: list[dict] = []
        for col in fuel_cols:
            fuel_type = col[len("fuel_"):]
            price = row.get(f"c_{col}") or row.get(col)
            if price is None or str(price).strip() == "":
                continue
            records.append({
                "commodity": f"fuel_{fuel_type}",
                "date": row.get("DATES", ""),
                "price": price,
                "unit": "per_liter_local_currency",
                "currency": row.get("currency", ""),
                "market": row.get("mkt_name", ""),
                "source": "wfp_global_fuel_prices",
                "latitude": row.get("lat"),
                "longitude": row.get("lon"),
                "country": row.get("country"),
                "country_code": row.get("ISO3"),
                "inflation_pct": row.get(f"inflation_{col}"),
                "data_trust_score": row.get(f"trust_{col}"),
            })
        return records

    def _safe_float(self, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class CommodityFuturesParser(BaseParser):
    @property
    def canonical_schema(self) -> dict:
        return {
            "entity_type": "string",
            "entity_id": "string",
            "entity_name": "string",
            "timestamp": "string",
            "timestamp_precision": "string",
            "latitude": "float",
            "longitude": "float",
            "location_name": "string",
            "location_code": "string",
            "attributes": "dict",
            "relationships": "list",
            "source": "string",
            "source_record_id": "string",
            "confidence": "float",
            "metadata": "dict",
        }

    async def parse(self, config: ParseConfig) -> ParserResult:
        return await self.parse_file(
            config.input_path, config.output_path,
            encoding=config.encoding, max_records=config.max_records,
            batch_size=config.batch_size,
        )

    async def parse_file(
        self, input_path: Path, output_path: Path, **kwargs: Any
    ) -> ParserResult:
        start = time.monotonic()
        errors: list[dict] = []
        records_parsed = 0
        records_failed = 0
        max_records = kwargs.get("max_records")
        encoding = kwargs.get("encoding", "utf-8")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        schema = await self.discover_schema(input_path)

        canonical_records: list[dict] = []
        with open(input_path, "r", encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader):
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "commodity": row.get("commodity", row.get("Commodity", row.get("product", ""))),
                        "contract_month": row.get("contract_month", row.get("month", row.get("ContractMonth", ""))),
                        "contract_year": row.get("contract_year", row.get("year", row.get("ContractYear", ""))),
                        "price": row.get("price", row.get("Price", row.get("settlement", row.get("close")))),
                        "volume": row.get("volume", row.get("Volume", row.get("vol"))),
                        "open_interest": row.get("open_interest", row.get("OpenInterest", row.get("oi"))),
                        "exchange": row.get("exchange", row.get("Exchange", row.get("market", ""))),
                        "settlement_date": row.get("settlement_date", row.get("date", row.get("Date", ""))),
                    }
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"row": row_idx, "error": str(e)})

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            if canonical_records:
                writer = csv.DictWriter(out_f, fieldnames=list(canonical_records[0].keys()))
                writer.writeheader()
                writer.writerows(canonical_records)

        return ParserResult(
            source="commodity_futures",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=COMMODITY_FUTURES_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "commodity": "string",
            "contract_month": "string",
            "contract_year": "integer",
            "price": "number",
            "volume": "integer",
            "open_interest": "integer",
            "exchange": "string",
            "settlement_date": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if row_idx > 1000:
                        break
                    if not row.get("commodity", "").strip():
                        issues.append(f"Row {row_idx}: missing commodity")
                    if not row.get("contract_year", "").strip() and not row.get("contract_month", "").strip():
                        issues.append(f"Row {row_idx}: missing contract reference")
        except Exception as e:
            issues.append(f"Validation error: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        line_count = 0
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in f:
                line_count += 1
        return {
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "line_count": line_count,
            "field_count": len(COMMODITY_FUTURES_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            contract_id = f"{rec['commodity']}_{rec.get('contract_month', '')}_{rec.get('contract_year', '')}"
            settlement_date = rec.get("settlement_date", "")
            canonical.append({
                "entity_type": "commodity_futures",
                "entity_id": contract_id,
                "entity_name": f"{rec['commodity']} Futures {rec.get('contract_month', '')} {rec.get('contract_year', '')}",
                "timestamp": settlement_date,
                "timestamp_precision": "day" if settlement_date else None,
                "latitude": None,
                "longitude": None,
                "location_name": rec.get("exchange"),
                "location_code": rec.get("exchange"),
                "attributes": {
                    "commodity": rec.get("commodity"),
                    "contract_month": rec.get("contract_month"),
                    "contract_year": self._safe_int(rec.get("contract_year")),
                    "price": self._safe_float(rec.get("price")),
                    "volume": self._safe_int(rec.get("volume")),
                    "open_interest": self._safe_int(rec.get("open_interest")),
                    "exchange": rec.get("exchange"),
                    "settlement_date": settlement_date,
                },
                "relationships": [
                    {"type": "traded_on", "target_id": rec.get("exchange")},
                    {"type": "underlying", "target_id": rec.get("commodity")},
                ],
                "source": "commodity_futures",
                "source_record_id": contract_id,
                "confidence": None,
                "metadata": {"parser": "CommodityFuturesParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: Any) -> int | None:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
