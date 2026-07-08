from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from data_acquisition.parser.base import BaseParser, ParseConfig, ParserResult

logger = get_logger(__name__)


UN_COMTRADE_FIELDS = [
    "classification", "year", "period", "trade_flow", "reporter",
    "partner", "commodity_code", "commodity", "qty", "netweight",
    "trade_value_usd",
]


class UNComtradeParser(BaseParser):
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
            dataset = data.get("dataset", data)
            records = dataset if isinstance(dataset, list) else dataset.get("data", dataset.get("records", [dataset]))
            for item in records:
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "classification": item.get("classification", item.get("classif", item.get("cls", ""))),
                        "year": str(item.get("year", item.get("yr", item.get("period", "")))),
                        "period": str(item.get("period", item.get("per", ""))),
                        "trade_flow": item.get("trade_flow", item.get("tradeFlow", item.get("flow", ""))),
                        "reporter": item.get("reporter", item.get("reporterDesc", item.get("rtName", ""))),
                        "reporter_code": item.get("reporter_code", item.get("reporterCode", item.get("rtCode", ""))),
                        "partner": item.get("partner", item.get("partnerDesc", item.get("ptName", ""))),
                        "partner_code": item.get("partner_code", item.get("partnerCode", item.get("ptCode", ""))),
                        "commodity_code": str(item.get("commodity_code", item.get("cmdCode", item.get("hs", "")))),
                        "commodity": item.get("commodity", item.get("commodityDesc", item.get("cmdDesc", ""))),
                        "qty": item.get("qty", item.get("quantity", item.get("qt"))) or item.get("qty_unit", ""),
                        "netweight": item.get("netweight", item.get("netWeight", item.get("netWt"))),
                        "trade_value_usd": item.get("trade_value_usd", item.get("tradeValue", item.get("value", item.get("TradeValue")))),
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
                for row_idx, row in enumerate(reader):
                    if max_records is not None and records_parsed >= max_records:
                        break
                    try:
                        rec = {
                            "classification": row.get("classification", row.get("Classification", row.get("cls", ""))),
                            "year": row.get("year", row.get("Year", row.get("yr", ""))),
                            "period": row.get("period", row.get("Period", row.get("per", ""))),
                            "trade_flow": row.get("trade_flow", row.get("Trade Flow", row.get("tradeFlow", row.get("flow", "")))),
                            "reporter": row.get("reporter", row.get("Reporter", row.get("reporterDesc", row.get("rtName", "")))),
                            "reporter_code": row.get("reporter_code", row.get("Reporter Code", row.get("rtCode", ""))),
                            "partner": row.get("partner", row.get("Partner", row.get("partnerDesc", row.get("ptName", "")))),
                            "partner_code": row.get("partner_code", row.get("Partner Code", row.get("ptCode", ""))),
                            "commodity_code": row.get("commodity_code", row.get("Commodity Code", row.get("cmdCode", row.get("hs", "")))),
                            "commodity": row.get("commodity", row.get("Commodity", row.get("cmdDesc", ""))),
                            "qty": row.get("qty", row.get("Qty", row.get("quantity", row.get("qt", "")))),
                            "netweight": row.get("netweight", row.get("Netweight", row.get("netWt", ""))),
                            "trade_value_usd": row.get("trade_value_usd", row.get("Trade Value (US$)", row.get("TradeValue", row.get("value", "")))),
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
            source="un_comtrade",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=UN_COMTRADE_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "classification": "string",
            "year": "string",
            "period": "string",
            "trade_flow": "string",
            "reporter": "string",
            "reporter_code": "string",
            "partner": "string",
            "partner_code": "string",
            "commodity_code": "string",
            "commodity": "string",
            "qty": "number",
            "netweight": "number",
            "trade_value_usd": "number",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if row_idx > 1000:
                        break
                    if not row.get("reporter", "").strip() and not row.get("Reporter", "").strip():
                        issues.append(f"Row {row_idx}: missing reporter")
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
            "field_count": len(UN_COMTRADE_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            year = rec.get("year", "")
            reporter = rec.get("reporter", "")
            partner = rec.get("partner", "")
            commodity_code = rec.get("commodity_code", "")
            trade_flow = rec.get("trade_flow", "")
            record_id = f"{reporter}_{partner}_{commodity_code}_{year}_{trade_flow}"

            canonical.append({
                "entity_type": "trade_flow",
                "entity_id": record_id,
                "entity_name": f"{trade_flow}: {reporter} -> {partner} ({commodity_code})",
                "timestamp": year,
                "timestamp_precision": "year",
                "latitude": None,
                "longitude": None,
                "location_name": reporter,
                "location_code": rec.get("reporter_code", reporter),
                "attributes": {
                    "classification": rec.get("classification"),
                    "year": year,
                    "period": rec.get("period"),
                    "trade_flow": trade_flow,
                    "reporter": reporter,
                    "reporter_code": rec.get("reporter_code"),
                    "partner": partner,
                    "partner_code": rec.get("partner_code"),
                    "commodity_code": commodity_code,
                    "commodity": rec.get("commodity"),
                    "qty": self._safe_float(rec.get("qty")),
                    "netweight": self._safe_float(rec.get("netweight")),
                    "trade_value_usd": self._safe_float(rec.get("trade_value_usd")),
                },
                "relationships": [
                    {"type": "reported_by", "target_id": reporter},
                    {"type": "traded_with", "target_id": partner},
                    {"type": "commodity", "target_id": commodity_code},
                ],
                "source": "un_comtrade",
                "source_record_id": record_id,
                "confidence": None,
                "metadata": {"parser": "UNComtradeParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
