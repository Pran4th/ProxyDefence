from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from data_acquisition.config import get_config
from data_acquisition.lake import DataLake, DataLakeConfig
from data_acquisition.source_registry import SourceRegistry, DATASET_REGISTRY
from data_acquisition.download_manager import DownloadManager, DownloadConfig
from data_acquisition.registration import DatasetRegistrationPipeline
from data_acquisition.research_integration import DatasetResolver
from data_acquisition.parser.base import ParseConfig, BaseParser
from data_acquisition.parser.sources import (
    GDELTEventParser,
    GDELTMentionParser,
    GKGParser,
    GCAMParser,
    EIAParser,
    FREDParser,
    OPECParser,
    AISParser,
    PortCongestionParser,
    WorldPortIndexParser,
    CommodityPriceParser,
    CommodityFuturesParser,
    OFACParser,
    UNSanctionsParser,
    WorldBankParser,
    UNComtradeParser,
    KaggleParser,
)
from data_acquisition.gdelt_pipeline import (
    MasterFileReader,
    GDELTFilter,
    FilterConfig,
    GDELTDownloader,
    GDELTParser,
    GDELTRegistration,
    GDELTValidator,
    GDELTPipeline,
    ValidationReport,
    ReportGenerator,
)
from datasets.builder import DatasetBuilder
from datasets.validation import DatasetValidationPipeline, full_validators
from datasets.metadata import DatasetMetadataManager
from dataset_factory.framework import DatasetFactory
from dataset_factory.config import DatasetFactoryConfig
from dataset_factory.builders import build_preset, PRESET_DATASETS
from datasets.builders import (
    NewsArticlesBuilder,
    EnergyInfrastructureBuilder,
    KnowledgeGraphBuilder,
    RiskSignalsBuilder,
    CommodityPricesBuilder,
    DigitalTwinBuilder,
    ProcurementBuilder,
    SPRBuilder,
    EventsBuilder,
    EntityRelationshipsBuilder,
    GraphEmbeddingsBuilder,
    HybridDatasetBuilder,
    BaseDatasetBuilder,
)

PARSER_MAP: dict[str, type[BaseParser]] = {
    "GDELTEventParser": GDELTEventParser,
    "GDELTMentionParser": GDELTMentionParser,
    "GKGParser": GKGParser,
    "GCAMParser": GCAMParser,
    "EIAParser": EIAParser,
    "FREDParser": FREDParser,
    "OPECParser": OPECParser,
    "AISParser": AISParser,
    "PortCongestionParser": PortCongestionParser,
    "WorldPortIndexParser": WorldPortIndexParser,
    "CommodityPriceParser": CommodityPriceParser,
    "CommodityFuturesParser": CommodityFuturesParser,
    "OFACParser": OFACParser,
    "UNSanctionsParser": UNSanctionsParser,
    "WorldBankParser": WorldBankParser,
    "UNComtradeParser": UNComtradeParser,
    "KaggleParser": KaggleParser,
}

BUILDER_MAP: dict[str, type[BaseDatasetBuilder]] = {
    "news_articles": NewsArticlesBuilder,
    "energy_infrastructure": EnergyInfrastructureBuilder,
    "knowledge_graph": KnowledgeGraphBuilder,
    "risk_signals": RiskSignalsBuilder,
    "commodity_prices": CommodityPricesBuilder,
    "digital_twin": DigitalTwinBuilder,
    "procurement": ProcurementBuilder,
    "spr": SPRBuilder,
    "events": EventsBuilder,
    "entity_relationships": EntityRelationshipsBuilder,
    "graph_embeddings": GraphEmbeddingsBuilder,
    "hybrid": HybridDatasetBuilder,
}

_ANSI_RESET = "\033[0m"
_ANSI_RED = "\033[91m"
_ANSI_GREEN = "\033[92m"
_ANSI_YELLOW = "\033[93m"
_ANSI_BLUE = "\033[94m"
_ANSI_MAGENTA = "\033[95m"
_ANSI_CYAN = "\033[96m"
_ANSI_BOLD = "\033[1m"
_ANSI_DIM = "\033[2m"


def print_error(msg: str) -> None:
    print(f"{_ANSI_RED}error: {msg}{_ANSI_RESET}", file=sys.stderr)


def print_success(msg: str) -> None:
    print(f"{_ANSI_GREEN}{msg}{_ANSI_RESET}")


def print_info(msg: str) -> None:
    print(f"{_ANSI_BLUE}{msg}{_ANSI_RESET}")


def print_warning(msg: str) -> None:
    print(f"{_ANSI_YELLOW}warning: {msg}{_ANSI_RESET}")


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print_info("no results")
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))
    sep = "  "
    header_line = sep.join(
        f"{_ANSI_BOLD}{h:<{col_widths[i]}}{_ANSI_RESET}" for i, h in enumerate(headers)
    )
    print(header_line)
    print(sep.join("-" * w for w in col_widths))
    for row in rows:
        line = sep.join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(row))
        print(line)


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs:.0f}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m {secs:.0f}s"


def _build_registry() -> SourceRegistry:
    reg = SourceRegistry()
    for sd in DATASET_REGISTRY:
        reg.register(sd)
    return reg


def _build_lake() -> DataLake:
    cfg = get_config()
    return DataLake(DataLakeConfig(base_dir=cfg.base_dir))


def _resolve_parser(source_name: str, registry: SourceRegistry) -> BaseParser | None:
    sd = registry.get(source_name)
    if not sd:
        return None
    parser_cls = PARSER_MAP.get(sd.default_parser)
    if not parser_cls:
        return None
    return parser_cls()


def _resolve_builder(builder_name: str | None, dataset_name: str) -> BaseDatasetBuilder | None:
    if builder_name and builder_name in BUILDER_MAP:
        return BUILDER_MAP[builder_name]()
    if dataset_name in BUILDER_MAP:
        return BUILDER_MAP[dataset_name]()
    for key, cls in BUILDER_MAP.items():
        if key in dataset_name:
            return cls()
    return None


async def _handle_download(args: argparse.Namespace) -> int:
    registry = _build_registry()
    sd = registry.get(args.source)
    if not sd:
        print_error(f"source '{args.source}' not found in registry")
        print_info("use 'ml list sources' to see available sources")
        return 1
    if not sd.is_active:
        print_warning(f"source '{args.source}' is inactive")

    version = args.version or sd.version
    data_lake = _build_lake()
    await data_lake.ensure_directories()

    if args.dry_run:
        print_info(f"[dry-run] would download '{args.source}' version {version}")
        print_info(f"  url template: {sd.url_template or 'not configured'}")
        print_info(f"  parser: {sd.default_parser}")
        print_info(f"  schema: {len(sd.expected_schema)} fields")
        return 0

    download_config = DownloadConfig(
        source=args.source,
        version=version,
        url=args.force and sd.url_template or sd.url_template,
    )
    async with DownloadManager(data_lake=data_lake) as dm:
        try:
            result = await dm.download(download_config)
        except Exception as e:
            print_error(f"download failed: {e}")
            return 1

    if result.status == "failed":
        print_error(f"download failed: {result.error or 'unknown error'}")
        return 1

    print_success(f"downloaded '{args.source}' version {version}")
    print(f"  status:   {result.status}")
    print(f"  files:    {len(result.files)}")
    print(f"  size:     {format_bytes(result.total_size_bytes)}")
    print(f"  checksum: {result.checksum[:16]}...")
    print(f"  duration: {format_duration(result.download_duration_seconds)}")
    print(f"  retries:  {result.retries}")
    if result.files:
        print(f"  output:   {result.files[0].parent}")
    return 0


async def _handle_list(args: argparse.Namespace) -> int:
    what = args.what or "sources"

    if what == "sources":
        registry = _build_registry()
        sources = registry.list_sources(category=args.category, active_only=True)
        if not sources:
            print_info("no sources registered")
            return 0

        rows = []
        for s in sources:
            if args.category and s.category != args.category:
                continue
            rows.append([
                s.name,
                s.display_name,
                s.category,
                s.update_frequency,
                s.version,
                str(len(s.expected_schema)),
            ])
        headers = ["name", "display_name", "category", "frequency", "version", "fields"]
        print_table(headers, rows)
        print_info(f"\n{len(sources)} source(s)")

    elif what == "datasets":
        resolver = DatasetResolver()
        try:
            datasets = await resolver.list_available_datasets()
        except Exception:
            datasets = []

        registry = _build_registry()
        sources = registry.list_sources(category=args.category)
        for s in sources:
            if not any(d["name"] == s.name for d in datasets):
                datasets.append({
                    "name": s.name,
                    "display_name": s.display_name,
                    "category": s.category,
                    "version": s.version,
                    "tags": s.tags,
                })

        if args.category:
            datasets = [d for d in datasets if d.get("category") == args.category]
        if not datasets:
            print_info("no datasets found")
            return 0

        rows = []
        for d in datasets:
            rows.append([
                d.get("name", ""),
                d.get("display_name", ""),
                d.get("category", ""),
                d.get("version", ""),
                str(d.get("feature_count", d.get("fields", ""))),
            ])
        headers = ["name", "display_name", "category", "version", "features"]
        print_table(headers, rows)
        print_info(f"\n{len(datasets)} dataset(s)")

    elif what == "versions":
        if not args.source:
            print_error("--source is required for 'list versions'")
            return 1
        lake = _build_lake()
        versions = await lake.list_versions(args.source)
        if not versions:
            print_info(f"no versions found for source '{args.source}'")
            return 0
        rows = []
        for v in versions:
            rows.append([
                v["version"],
                v.get("created", ""),
                format_bytes(v.get("size_bytes", 0)),
                str(v.get("file_count", 0)),
            ])
        print_table(["version", "created", "size", "files"], rows)
        print_info(f"\n{len(versions)} version(s)")

    return 0


async def _handle_describe(args: argparse.Namespace) -> int:
    registry = _build_registry()
    sd = registry.get(args.source_or_dataset)
    if sd:
        print(f"{_ANSI_BOLD}{sd.name}{_ANSI_RESET}")
        print(f"  display_name:    {sd.display_name}")
        print(f"  description:     {sd.description}")
        print(f"  category:        {sd.category}")
        print(f"  update_frequency: {sd.update_frequency}")
        print(f"  connector_type:  {sd.connector_type}")
        print(f"  default_parser:  {sd.default_parser}")
        print(f"  version:         {sd.version}")
        print(f"  url_template:    {sd.url_template or 'N/A'}")
        print(f"  license:         {sd.license or 'N/A'}")
        print(f"  active:          {sd.is_active}")
        print(f"  tags:            {', '.join(sd.tags) if sd.tags else 'none'}")
        if sd.expected_schema:
            print(f"\n  schema ({len(sd.expected_schema)} fields):")
            for col, typ in sd.expected_schema.items():
                print(f"    {col}: {typ}")
        return 0

    resolver = DatasetResolver()
    try:
        resolved = await resolver.resolve_dataset(args.source_or_dataset)
    except ValueError:
        resolved = None
    except Exception as e:
        print_warning(f"catalog lookup failed: {e}")
        resolved = None

    if resolved:
        print(f"{_ANSI_BOLD}{resolved.get('display_name', resolved['source'])}{_ANSI_RESET}")
        for k, v in resolved.items():
            if k in ("path", "display_name", "features"):
                continue
            if isinstance(v, dict) and v:
                print(f"  {k}: {json.dumps(v, default=str)[:200]}")
            else:
                print(f"  {k}: {v}")
        features = resolved.get("features", [])
        if features:
            print(f"  features ({len(features)}): {', '.join(features[:20])}")
        print(f"  path: {resolved.get('path', 'N/A')}")
        return 0

    lake = _build_lake()
    source_info = await lake.get_source_info(args.source_or_dataset)
    if source_info.get("exists"):
        print(f"{_ANSI_BOLD}{args.source_or_dataset}{_ANSI_RESET} (local)")
        print(f"  versions:      {source_info['version_count']}")
        print(f"  total_size:    {format_bytes(source_info['total_size_bytes'])}")
        print(f"  total_files:   {source_info['total_files']}")
        return 0

    print_error(f"'{args.source_or_dataset}' not found in registry, catalog, or lake")
    return 1


async def _handle_parse(args: argparse.Namespace) -> int:
    registry = _build_registry()
    sd = registry.get(args.source)
    if not sd:
        print_error(f"source '{args.source}' not found in registry")
        return 1

    parser = _resolve_parser(args.source, registry)
    if not parser:
        print_error(f"no parser found for source '{args.source}' (parser: {sd.default_parser})")
        return 1

    input_path = Path(args.input_path)
    if not input_path.exists():
        print_error(f"input path not found: {input_path}")
        return 1

    version = args.version or sd.version
    lake = _build_lake()
    await lake.ensure_directories()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = await lake.get_processed_path(args.source, version)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{args.source}.csv"

    parse_config = ParseConfig(
        source=args.source,
        version=version,
        input_path=input_path,
        output_path=output_file,
        schema=sd.expected_schema,
    )

    try:
        result = await parser.parse(parse_config)
    except Exception as e:
        print_error(f"parse failed: {e}")
        return 1

    print_success(f"parsed '{args.source}' version {version}")
    print(f"  records_parsed:   {result.records_parsed}")
    print(f"  records_failed:   {result.records_failed}")
    print(f"  columns:          {len(result.columns)}")
    print(f"  duration:         {format_duration(result.duration_seconds)}")
    print(f"  output:           {result.output_path}")
    if result.errors:
        print(f"  errors ({len(result.errors)}):")
        for err in result.errors[:5]:
            print(f"    - {err}")
    return 0


async def _handle_register(args: argparse.Namespace) -> int:
    source = args.source or args.dataset_name
    version = args.version or "1"

    if args.path:
        input_path = Path(args.path)
    else:
        lake = _build_lake()
        input_path = await lake.get_processed_path(source, version)
        parquet_files = list(input_path.glob("*.parquet"))
        if parquet_files:
            input_path = parquet_files[0]
        else:
            csv_files = list(input_path.glob("*.csv"))
            if csv_files:
                input_path = csv_files[0]
            elif not input_path.exists():
                print_error(f"no data found at {input_path}, specify --path")
                return 1

    pipeline = DatasetRegistrationPipeline()
    try:
        result = await pipeline.register_dataset(
            dataset_name=args.dataset_name,
            source=source,
            version=version,
            processed_path=input_path,
        )
    except Exception as e:
        print_error(f"registration failed: {e}")
        return 1

    if result.status == "failed":
        print_error(f"registration failed: {result.error or 'unknown error'}")
        return 1

    print_success(f"registered dataset '{args.dataset_name}' v{version}")
    print(f"  status:         {result.status}")
    print(f"  registration_id: {result.registration_id}")
    print(f"  preview_rows:   {result.preview_rows}")
    print(f"  manifest_path:  {result.manifest_path}")
    stats = result.statistics
    if stats:
        print(f"  row_count:      {stats.get('row_count', 'N/A')}")
        print(f"  column_count:   {stats.get('column_count', 'N/A')}")
        print(f"  memory:         {format_bytes(stats.get('memory_bytes', 0))}")
        print(f"  duplicates:     {stats.get('duplicate_count', 'N/A')}")
        print(f"  missing_cells:  {stats.get('missing_cells', 'N/A')}")
    return 0


async def _handle_build(args: argparse.Namespace) -> int:
    builder = DatasetBuilder()
    target_column = "criticality_score"

    try:
        if args.builder:
            specific = _resolve_builder(args.builder, args.dataset_name)
            if specific:
                print_info(f"using builder: {specific.__class__.__name__}")
                deps = specific.get_dependencies()
                if deps:
                    print_info(f"  dependencies: {len(deps)}")

        result = await builder.build(
            name=args.dataset_name,
            target_column=target_column,
        )
    except Exception as e:
        print_error(f"build failed: {e}")
        return 1

    print_success(f"built dataset '{args.dataset_name}' v{result.get('version', '?')}")
    print(f"  uuid:           {result.get('uuid', 'N/A')}")
    print(f"  total_records:  {result.get('total_records', 'N/A')}")
    print(f"  feature_count:  {result.get('feature_count', 'N/A')}")
    print(f"  target_column:  {result.get('target_column', 'N/A')}")
    splits = result.get("splits", {})
    if splits:
        print(f"  splits:         train={splits.get('train', '?')} "
              f"val={splits.get('validation', '?')} "
              f"test={splits.get('test', '?')}")
    return 0


async def _handle_build_dataset(args: argparse.Namespace) -> int:
    try:
        if args.preset:
            print_info(f"building preset: {args.preset}")
            result = await build_preset(
                args.preset,
                force_synthetic=args.force_synthetic,
                skip_normalize=args.skip_normalize,
                skip_clean=args.skip_clean,
                skip_validate=args.skip_validate,
                skip_quality=args.skip_quality,
                skip_eda=args.skip_eda,
                skip_features=args.skip_features,
                skip_export=args.skip_export,
            )
        else:
            factory = DatasetFactory(DatasetFactoryConfig())
            result = await factory.build(
                name=args.dataset,
                target_column=args.target_column or "criticality_score",
                force_synthetic=args.force_synthetic,
                skip_normalize=args.skip_normalize,
                skip_clean=args.skip_clean,
                skip_validate=args.skip_validate,
                skip_quality=args.skip_quality,
                skip_eda=args.skip_eda,
                skip_features=args.skip_features,
                skip_export=args.skip_export,
                description=args.description,
            )

        d = result.to_dict()
        print(f"\n{_ANSI_BOLD}{'=' * 50}{_ANSI_RESET}")
        print(f"{_ANSI_GREEN}{_ANSI_BOLD}DATASET BUILD COMPLETE{_ANSI_RESET}")
        print(f"{_ANSI_BOLD}{'=' * 50}{_ANSI_RESET}")
        print(f"  dataset:        {d['dataset_name']}")
        print(f"  version:        {d['version']}")
        print(f"  records:        {d['total_records']}")
        print(f"  features:       {d['feature_count']}")
        print(f"  target:         {d['target_column']}")
        print(f"  duration:       {d['duration_seconds']:.1f}s")
        print(f"  uuid:           {d.get('db_uuid', 'N/A')}")
        print(f"  export:         {d.get('export_path', 'N/A')}")

        steps = d.get("steps_completed", [])
        check_results = []
        if "normalize" in steps:
            check_results.append(f"{_ANSI_GREEN}normalized dataset{_ANSI_RESET}")
        if "clean" in steps:
            check_results.append(f"{_ANSI_GREEN}cleaned dataset{_ANSI_RESET}")
        if "validate" in steps:
            v = f"{_ANSI_GREEN}validated dataset{_ANSI_RESET}" if d.get("validated") else f"{_ANSI_RED}validation FAILED{_ANSI_RESET}"
            check_results.append(v)
        if "quality_report" in steps:
            check_results.append(f"{_ANSI_GREEN}quality report{_ANSI_RESET}")
        if "eda_report" in steps:
            check_results.append(f"{_ANSI_GREEN}EDA report{_ANSI_RESET}")
        if "feature_engineering" in steps:
            check_results.append(f"{_ANSI_GREEN}feature engineered{_ANSI_RESET}")
        if "feature_validation" in steps:
            fv = f"{_ANSI_GREEN}feature validation{_ANSI_RESET}" if d.get("feature_validated") else f"{_ANSI_RED}feature validation flagged{_ANSI_RESET}"
            check_results.append(fv)
        if "export" in steps:
            check_results.append(f"{_ANSI_GREEN}export files{_ANSI_RESET}")
        if "db_registration" in steps:
            check_results.append(f"{_ANSI_GREEN}registered{_ANSI_RESET}")
        if "dataset_card" in steps:
            check_results.append(f"{_ANSI_GREEN}dataset card{_ANSI_RESET}")

        print(f"\n  {_ANSI_BOLD}steps:{_ANSI_RESET}")
        for cr in check_results:
            print(f"    {_ANSI_GREEN}\u2713{_ANSI_RESET} {cr}")

        splits = d.get("splits", {})
        if splits:
            print(f"\n  {_ANSI_BOLD}splits:{_ANSI_RESET}")
            for split_name, count in splits.items():
                print(f"    {split_name}: {count} records")

        errors = d.get("errors", [])
        if errors:
            print(f"\n  {_ANSI_RED}{len(errors)} error(s):{_ANSI_RESET}")
            for e in errors:
                print(f"    {_ANSI_RED}- {e}{_ANSI_RESET}")

        warnings = d.get("warnings", [])
        if warnings:
            print(f"\n  {_ANSI_YELLOW}{len(warnings)} warning(s):{_ANSI_RESET}")
            for w in warnings:
                print(f"    {_ANSI_YELLOW}- {w}{_ANSI_RESET}")

        print(f"\n{_ANSI_BOLD}{'=' * 50}{_ANSI_RESET}")

    except Exception as e:
        print_error(f"build_dataset failed: {e}")
        return 1
    return 0


async def _handle_validate(args: argparse.Namespace) -> int:
    version = args.version
    if not version:
        try:
            version = await DatasetMetadataManager.get_current_version(args.dataset_name)
        except Exception:
            pass
        version = version or 1

    lake = _build_lake()
    processed = await lake.get_processed_path(args.dataset_name, str(version))

    data_path = None
    for pattern in ("*.parquet", "*.csv"):
        files = list(processed.glob(pattern))
        if files:
            data_path = files[0]
            break

    if not data_path or not data_path.exists():
        registry = _build_registry()
        sd = registry.get(args.dataset_name)
        if sd:
            raw = await lake.get_raw_path(args.dataset_name, str(version))
            for pattern in ("*.parquet", "*.csv"):
                files = list(raw.glob(pattern))
                if files:
                    data_path = files[0]
                    break

    if not data_path or not data_path.exists():
        print_error(f"no data found for dataset '{args.dataset_name}' v{version}")
        return 1

    import pandas as pd
    try:
        if data_path.suffix == ".parquet":
            df = pd.read_parquet(data_path)
        else:
            df = pd.read_csv(data_path)
    except Exception as e:
        print_error(f"failed to load data: {e}")
        return 1

    pipeline = DatasetValidationPipeline()
    for name, fn in full_validators():
        pipeline.add_validator(name, fn)
    try:
        result = await pipeline.validate(df, args.dataset_name, int(version))
    except Exception as e:
        print_error(f"validation failed: {e}")
        return 1

    print_success(f"validation results for '{args.dataset_name}' v{version}")
    print(f"  total_checks:  {result.get('total_checks', 0)}")
    print(f"  passed:        {result.get('passed', 0)}")
    print(f"  failed:        {result.get('failed', 0)}")
    for r in result.get("results", []):
        status_icon = f"{_ANSI_GREEN}PASS{_ANSI_RESET}" if r.get("passed") else f"{_ANSI_RED}FAIL{_ANSI_RESET}"
        details = r.get("details", {})
        detail_str = ""
        if details:
            snippet = json.dumps(details, default=str)[:120]
            detail_str = f"  {snippet}"
        print(f"  [{status_icon}] {r.get('validation_type', '?')}{detail_str}")
    return 0


async def _handle_info(args: argparse.Namespace) -> int:
    lake = _build_lake()
    await lake.ensure_directories()

    registry = _build_registry()
    sources = registry.list_sources(active_only=True)
    categories = registry.get_categories()

    stats = await lake.get_lake_stats()

    print(f"{_ANSI_BOLD}Data Lake Statistics{_ANSI_RESET}")
    print(f"  total_size:    {format_bytes(stats.get('total_size_bytes', 0))}")
    print(f"  file_count:    {stats.get('file_count', 0)}")
    print(f"  source_count:  {stats.get('source_count', 0)}")
    print()
    for dir_name, info in stats.get("directories", {}).items():
        print(f"  {dir_name}/: {format_bytes(info['size_bytes'])} ({info['file_count']} files)")

    print(f"\n{_ANSI_BOLD}Source Registry{_ANSI_RESET}")
    print(f"  total_sources: {len(sources)}")
    print(f"  categories:    {len(categories)}")
    for cat in categories:
        count = len(registry.list_sources(category=cat))
        print(f"    {cat}: {count} source(s)")

    disk = await lake.get_disk_usage()
    if disk:
        print(f"\n{_ANSI_BOLD}Disk Usage by Source{_ANSI_RESET}")
        for name, size in sorted(disk.items(), key=lambda x: -x[1]):
            print(f"  {name}: {format_bytes(size)}")

    cfg = get_config()
    print(f"\n{_ANSI_BOLD}Configuration{_ANSI_RESET}")
    print(f"  base_dir:          {cfg.base_dir}")
    print(f"  max_retries:       {cfg.max_retries}")
    print(f"  verify_checksums:  {cfg.verify_checksums}")
    print(f"  preserve_archives: {cfg.preserve_archives}")
    print(f"  log_level:         {cfg.log_level}")

    return 0


async def _handle_gdelt(args: argparse.Namespace) -> int:
    gdelt_action = args.gdelt_action
    pipeline = GDELTPipeline()

    version = args.version
    start_date = args.start_date
    end_date = args.end_date

    if gdelt_action == "discover":
        s = time.monotonic()
        reader = MasterFileReader()
        result = await reader.fetch()
        elapsed = time.monotonic() - s
        if result.error:
            print_error(result.error)
            return 1
        print_success(f"GDELT master file list: {result.total_discovered} entries ({format_duration(elapsed)})")
        print(f"  by type:")
        for ds_type, count in sorted(result.by_type.items()):
            print(f"    {ds_type}: {count}")
        if result.earliest:
            print(f"  date range:  {MasterFileReader.format_date(result.earliest) if result.earliest else 'N/A'}")
            print(f"               {MasterFileReader.format_date(result.latest) if result.latest else 'N/A'}")
        return 0

    elif gdelt_action == "download":
        reader = MasterFileReader()
        master_result = await reader.fetch()
        if master_result.error:
            print_error(f"discovery failed: {master_result.error}")
            return 1

        filter_cfg = FilterConfig(
            start_date=start_date,
            end_date=end_date,
        )
        filtered = GDELTFilter().filter(master_result.entries, filter_cfg)
        if not filtered:
            print_error(f"no files found for date range {start_date} → {end_date}")
            return 1

        version = version or (start_date.replace("-", "") if start_date else "latest")
        print_info(f"downloading {len(filtered)} file(s) for version {version}...")

        downloader = GDELTDownloader()
        results = await downloader.download_batch(filtered, version=version)

        completed = [r for r in results if r.status == "completed"]
        failed = [r for r in results if r.status == "failed"]

        if failed:
            print_warning(f"{len(completed)} completed, {len(failed)} failed")
            for f in failed:
                print_error(f"  {f.url}: {f.error}")
        else:
            print_success(f"all {len(completed)} downloads completed")

        for r in completed:
            print(f"  {r.source} v{r.version}: {format_bytes(r.total_size_bytes)} ({format_duration(r.download_duration_seconds)})")
            if r.files:
                print(f"    -> {r.files[0]}")
        return 0 if not failed else 1

    elif gdelt_action == "parse":
        import zipfile

        version = version or "latest"
        parser = GDELTParser()

        csv_dir = Path(f"datasets/raw/gdelt/events/{version}")
        if not csv_dir.exists() and start_date:
            csv_dir = Path(f"datasets/raw/gdelt/events/{start_date.replace('-', '')}")

        files_by_type: dict[str, list[Path]] = {"events": [], "mentions": [], "gkg": []}
        for ds_type in ("events", "mentions", "gkg"):
            base = Path(f"datasets/raw/gdelt/{ds_type}/{version}")
            if not base.exists():
                base = Path(f"datasets/raw/gdelt/{ds_type}/{start_date.replace('-', '')}") if start_date else base
            if base.exists():
                for zf in base.glob("*.zip"):
                    extract_dir = base / "extracted"
                    extract_dir.mkdir(exist_ok=True)
                    with zipfile.ZipFile(zf, "r") as z:
                        z.extractall(extract_dir)
                    for csv_file in extract_dir.glob("*.csv"):
                        files_by_type[ds_type].append(csv_file)

        parse_results = []
        for ds_type, file_list in files_by_type.items():
            for fp in file_list:
                print_info(f"parsing {ds_type}: {fp.name}...")
                pr = await parser.parse_file(
                    input_path=fp,
                    dataset_type=ds_type,
                    version=version,
                )
                parse_results.append(pr)
                print_success(f"  {pr.records_parsed} records parsed, {pr.records_failed} failed -> {pr.output_path}")

        total_parsed = sum(r.records_parsed for r in parse_results)
        total_failed = sum(r.records_failed for r in parse_results)
        print_info(f"total: {total_parsed} parsed, {total_failed} failed")
        return 0

    elif gdelt_action == "register":
        from data_acquisition.gdelt_pipeline.registration import GDELTRegistration

        version = version or "latest"
        reg = GDELTRegistration()

        for ds_type in ("events", "mentions", "gkg"):
            csv_dir = Path(f"datasets/processed/gdelt/{ds_type}/{version}")
            if not csv_dir.exists() and start_date:
                csv_dir = Path(f"datasets/processed/gdelt/{ds_type}/{start_date.replace('-', '')}")
            if csv_dir.exists():
                csv_files = list(csv_dir.glob("*.csv"))
                for csv_path in csv_files:
                    print_info(f"registering {ds_type}: {csv_path.name}...")
                    result = await reg.register_parsed_dataset(
                        dataset_type=ds_type,
                        version=version,
                        csv_path=csv_path,
                    )
                    if result.status == "registered":
                        print_success(f"  registered: {result.dataset_name} (id={getattr(result.registration, 'registration_id', 'N/A')})")
                    else:
                        print_error(f"  failed: {result.error}")
        return 0

    elif gdelt_action == "validate":
        from data_acquisition.gdelt_pipeline.validation import GDELTValidator

        version = version or "latest"
        validator = GDELTValidator()

        all_ok = True
        for ds_type in ("events", "mentions", "gkg"):
            zip_dir = Path(f"datasets/raw/gdelt/{ds_type}/{version}")
            csv_dir = Path(f"datasets/processed/gdelt/{ds_type}/{version}")
            if not zip_dir.exists() and not csv_dir.exists():
                print_info(f"  {ds_type}: no data found for version {version}")
                continue

            print(f"\n{_ANSI_BOLD}{ds_type}{_ANSI_RESET}")
            for zf in zip_dir.glob("*.zip") if zip_dir.exists() else []:
                vresult = validator.full_validation(
                    dataset_type=ds_type,
                    version=version,
                    zip_path=zf,
                )
                for c in vresult.checks:
                    icon = f"{_ANSI_GREEN}PASS{_ANSI_RESET}" if c.passed else f"{_ANSI_RED}FAIL{_ANSI_RESET}"
                    print(f"  [{icon}] {c.name}: {c.detail[:120]}")
                if not vresult.all_passed:
                    all_ok = False

            for csv_path in csv_dir.glob("*.csv") if csv_dir.exists() else []:
                vresult_csv = validator.full_validation(
                    dataset_type=ds_type,
                    version=version,
                    csv_path=csv_path,
                )
                for c in vresult_csv.checks:
                    icon = f"{_ANSI_GREEN}PASS{_ANSI_RESET}" if c.passed else f"{_ANSI_RED}FAIL{_ANSI_RESET}"
                    print(f"  [{icon}] {c.name}: {c.detail[:120]}")
                if not vresult_csv.all_passed:
                    all_ok = False

        return 0 if all_ok else 1

    else:
        print_error(f"unknown gdelt action: {gdelt_action}")
        return 1


async def _handle_config(args: argparse.Namespace) -> int:
    cfg = get_config()

    if args.show:
        print(f"{_ANSI_BOLD}Current Configuration{_ANSI_RESET}")
        for field in ("base_dir", "max_retries", "retry_delay", "chunk_size",
                       "verify_checksums", "preserve_archives", "log_level"):
            print(f"  {field}: {getattr(cfg, field)}")
        print(f"\n{_ANSI_DIM}Configuration is read from environment variables.{_ANSI_RESET}")
        print(f"{_ANSI_DIM}  DATASET_DIR       -> base_dir{_ANSI_RESET}")
        print(f"{_ANSI_DIM}  DA_MAX_RETRIES    -> max_retries{_ANSI_RESET}")
        print(f"{_ANSI_DIM}  DA_RETRY_DELAY    -> retry_delay{_ANSI_RESET}")
        print(f"{_ANSI_DIM}  DA_CHUNK_SIZE     -> chunk_size{_ANSI_RESET}")
        print(f"{_ANSI_DIM}  DA_LOG_LEVEL      -> log_level{_ANSI_RESET}")
        return 0

    if args.key and args.value:
        env_map = {
            "base_dir": "DATASET_DIR",
            "max_retries": "DA_MAX_RETRIES",
            "retry_delay": "DA_RETRY_DELAY",
            "chunk_size": "DA_CHUNK_SIZE",
            "verify_checksums": "DA_VERIFY_CHECKSUMS",
            "preserve_archives": "DA_PRESERVE_ARCHIVES",
            "log_level": "DA_LOG_LEVEL",
        }
        env_key = env_map.get(args.key)
        if not env_key:
            print_error(f"unknown config key '{args.key}'. valid keys: {', '.join(env_map.keys())}")
            return 1
        os.environ[env_key] = args.value
        print_success(f"set {args.key} = {args.value} (via {env_key})")
        print_info("note: this change is ephemeral; set the env var in your shell for persistence")
        return 0

    if args.key:
        env_map = {
            "base_dir": "DATASET_DIR",
            "max_retries": "DA_MAX_RETRIES",
            "retry_delay": "DA_RETRY_DELAY",
            "chunk_size": "DA_CHUNK_SIZE",
            "verify_checksums": "DA_VERIFY_CHECKSUMS",
            "preserve_archives": "DA_PRESERVE_ARCHIVES",
            "log_level": "DA_LOG_LEVEL",
        }
        env_key = env_map.get(args.key)
        if not env_key:
            print_error(f"unknown config key '{args.key}'")
            return 1
        val = os.getenv(env_key, str(getattr(cfg, args.key, "")))
        print(f"{args.key} = {val}  ({env_key})")
        return 0

    print_info("use --show to display full config, or --key KEY --value VALUE to set")
    return 0


async def _handle_presets(args: argparse.Namespace) -> int:
    print(f"{_ANSI_BOLD}Available Dataset Presets:{_ANSI_RESET}")
    print()
    for name, cfg in PRESET_DATASETS.items():
        n_features = len(cfg.get("feature_configs", []))
        print(f"  {_ANSI_CYAN}{name}{_ANSI_RESET}")
        print(f"    target:     {cfg.get('target_column')}")
        print(f"    features:   {n_features}")
        print(f"    type:       {cfg.get('dataset_type')}")
        print(f"    desc:       {cfg.get('description', 'N/A')}")
        print()
        for fc in cfg.get("feature_configs", [])[:3]:
            print(f"      - {fc['name']} ({fc.get('transform', 'identity')})")
        if n_features > 3:
            print(f"      ... and {n_features - 3} more")
        print()
    print(f"{_ANSI_DIM}Usage: ml build_dataset --preset <name>{_ANSI_RESET}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ml",
        description="ML Platform Data Acquisition CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_download = sub.add_parser("download", help="Download dataset from registered source")
    p_download.add_argument("source", help="Source name from registry")
    p_download.add_argument("--version", help="Dataset version (default: source default)")
    p_download.add_argument("--dry-run", action="store_true", help="Show what would be downloaded")
    p_download.add_argument("--force", action="store_true", help="Force download even if exists")

    p_list = sub.add_parser("list", help="List sources, datasets, or versions")
    p_list.add_argument("what", nargs="?", choices=["sources", "datasets", "versions"],
                        default="sources", help="What to list")
    p_list.add_argument("--category", help="Filter by category")
    p_list.add_argument("--source", help="Source name (required for 'versions')")

    p_describe = sub.add_parser("describe", help="Show source or dataset metadata")
    p_describe.add_argument("source_or_dataset", help="Source or dataset name")

    p_parse = sub.add_parser("parse", help="Parse raw data using source's default parser")
    p_parse.add_argument("source", help="Source name from registry")
    p_parse.add_argument("input_path", help="Path to raw input data")
    p_parse.add_argument("--version", help="Version tag for output")
    p_parse.add_argument("--output-dir", help="Output directory (default: lake processed/)")

    p_register = sub.add_parser("register", help="Register a processed dataset")
    p_register.add_argument("dataset_name", help="Name for the dataset")
    p_register.add_argument("--source", help="Source name")
    p_register.add_argument("--version", help="Version string")
    p_register.add_argument("--path", help="Path to processed data file/dir")

    p_build = sub.add_parser("build", help="Build dataset using DatasetBuilder")
    p_build.add_argument("dataset_name", help="Dataset name to build")
    p_build.add_argument("--builder", help="Specific builder class name")

    p_validate = sub.add_parser("validate", help="Run validation checks on a dataset")
    p_validate.add_argument("dataset_name", help="Dataset name")
    p_validate.add_argument("--version", help="Version number")

    p_info = sub.add_parser("info", help="Show data lake statistics and system info")

    p_gdelt = sub.add_parser("gdelt", help="GDELT data pipeline operations")
    p_gdelt.add_argument("gdelt_action", choices=["discover", "download", "parse", "register", "validate"],
                         help="GDELT pipeline stage")
    p_gdelt.add_argument("--start-date", default="2024-01-01", help="Start date (YYYY-MM-DD)")
    p_gdelt.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    p_gdelt.add_argument("--version", help="Version string (default: derived from start-date)")

    p_build_dataset = sub.add_parser("build_dataset", help="Build dataset using Dataset Factory (full pipeline)")
    p_build_dataset.add_argument("dataset", nargs="?", help="Dataset name (optional if --preset is used)")
    p_build_dataset.add_argument("--preset", choices=list(PRESET_DATASETS.keys()),
                                  help="Preset dataset configuration")
    p_build_dataset.add_argument("--target-column", default="criticality_score",
                                  help="Target column name")
    p_build_dataset.add_argument("--description", help="Dataset description")
    p_build_dataset.add_argument("--force-synthetic", action="store_true",
                                  help="Force use of synthetic data")
    p_build_dataset.add_argument("--skip-normalize", action="store_true",
                                  help="Skip normalization step")
    p_build_dataset.add_argument("--skip-clean", action="store_true",
                                  help="Skip cleaning step")
    p_build_dataset.add_argument("--skip-validate", action="store_true",
                                  help="Skip validation step")
    p_build_dataset.add_argument("--skip-quality", action="store_true",
                                  help="Skip quality report")
    p_build_dataset.add_argument("--skip-eda", action="store_true",
                                  help="Skip EDA report")
    p_build_dataset.add_argument("--skip-features", action="store_true",
                                  help="Skip feature engineering")
    p_build_dataset.add_argument("--skip-export", action="store_true",
                                  help="Skip file export")

    p_presets = sub.add_parser("presets", help="List available dataset presets")

    p_config = sub.add_parser("config", help="Show or set configuration")
    p_config.add_argument("--show", action="store_true", help="Show full configuration")
    p_config.add_argument("--key", help="Configuration key")
    p_config.add_argument("--value", help="Value to set")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command_handlers = {
        "download": _handle_download,
        "list": _handle_list,
        "describe": _handle_describe,
        "parse": _handle_parse,
        "register": _handle_register,
        "build": _handle_build,
        "build_dataset": _handle_build_dataset,
        "validate": _handle_validate,
        "info": _handle_info,
        "config": _handle_config,
        "gdelt": _handle_gdelt,
        "presets": _handle_presets,
    }

    handler = command_handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    try:
        return asyncio.run(handler(args))
    except KeyboardInterrupt:
        print_error("interrupted")
        return 130
    except Exception as e:
        print_error(f"unexpected error: {e}")
        return 1


def ml_cli() -> None:
    sys.exit(main())


if __name__ == "__main__":
    ml_cli()
