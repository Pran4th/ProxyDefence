from pathlib import Path

from backend.shared.logging_config import get_logger
from data_acquisition.config import get_config, DataAcquisitionConfig
from data_acquisition.lake import DataLake
from data_acquisition.parser.base import BaseParser, ParseConfig
from data_acquisition.registration import DatasetRegistrationPipeline, DatasetRegistrationResult

logger = get_logger(__name__)


class RegistrationFlow:
    def __init__(self) -> None:
        self._pipeline = DatasetRegistrationPipeline()
        self._lake = DataLake()
        self._cfg: DataAcquisitionConfig = get_config()

    async def process_raw_to_registered(
        self,
        source: str,
        version: str,
        raw_path: Path,
        parser: BaseParser,
        pool=None,
    ) -> DatasetRegistrationResult:
        processed_dir = await self._lake.get_processed_path(source, version)
        processed_dir.mkdir(parents=True, exist_ok=True)

        parse_config = ParseConfig(
            source=source,
            version=version,
            input_path=raw_path,
            output_path=processed_dir,
        )
        result = await parser.parse(parse_config)

        dataset_name = f"{source}_v{version}"
        processed_file = result.output_path / "data.parquet"
        if not processed_file.exists():
            parquet_files = list(result.output_path.glob("*.parquet"))
            if parquet_files:
                processed_file = parquet_files[0]

        registration = await self._pipeline.register_dataset(
            dataset_name=dataset_name,
            source=source,
            version=version,
            processed_path=processed_file,
            schema=result.schema_discovered,
            pool=pool,
        )

        return registration

    async def process_registered_to_builder(
        self,
        dataset_name: str,
        version: str,
        builder_name: str | None = None,
        pool=None,
    ) -> dict:
        from datasets.builder import DatasetBuilder

        builder = DatasetBuilder()
        build_result = await builder.build(
            name=dataset_name,
            target_column="criticality_score",
        )

        return {
            "dataset_name": dataset_name,
            "version": version,
            "builder_result": build_result,
        }

    async def get_registration_status(self, dataset_name: str) -> dict:
        from datasets.catalog import DatasetCatalog

        catalog = DatasetCatalog()
        entry = await catalog.get(dataset_name)
        if entry is None:
            return {"dataset_name": dataset_name, "registered": False}
        return {
            "dataset_name": dataset_name,
            "registered": True,
            "uuid": entry.get("uuid"),
            "dataset_type": entry.get("dataset_type"),
            "created_at": str(entry.get("created_at", "")),
        }

    async def list_registered_datasets(
        self, source: str | None = None, pool=None
    ) -> list[dict]:
        from datasets.catalog import DatasetCatalog

        catalog = DatasetCatalog()
        results, _ = await catalog.search(dataset_type=source)
        return results
