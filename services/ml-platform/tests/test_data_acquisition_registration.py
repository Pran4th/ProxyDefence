import hashlib
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from data_acquisition.registration import DatasetRegistrationResult, DatasetRegistrationPipeline
from data_acquisition.registration_flow import RegistrationFlow
from data_acquisition.research_integration import DatasetResolver, ExperimentDatasetResolver
from data_acquisition.source_registry import SourceRegistry, SourceDefinition, DATASET_REGISTRY


class TestDatasetRegistrationResult:
    def test_default_error(self):
        result = DatasetRegistrationResult(
            dataset_name="test", version="1", status="registered",
            catalog_entry={"uuid": "abc-123"}, statistics={"row_count": 100},
            preview_rows=5, manifest_path=Path("/tmp/manifest.yaml"),
            registration_id="abc-123",
        )
        assert result.error is None
        assert result.status == "registered"

    def test_with_error(self):
        result = DatasetRegistrationResult(
            dataset_name="test", version="1", status="failed",
            catalog_entry={}, statistics={}, preview_rows=0,
            manifest_path=Path(), registration_id="",
            error="Processing failed",
        )
        assert result.error == "Processing failed"

    def test_fields(self):
        result = DatasetRegistrationResult(
            dataset_name="ds", version="v1", status="registered",
            catalog_entry={"uuid": "x"}, statistics={"rows": 10},
            preview_rows=3, manifest_path=Path("m.yaml"), registration_id="x",
        )
        assert result.dataset_name == "ds"
        assert result.registration_id == "x"

    def test_default_fields_are_correct_types(self):
        result = DatasetRegistrationResult(
            dataset_name="", version="", status="",
            catalog_entry={}, statistics={}, preview_rows=0,
            manifest_path=Path(), registration_id="",
        )
        assert isinstance(result.preview_rows, int)
        assert isinstance(result.registration_id, str)


@pytest.fixture
def sample_csv(tmp_path):
    f = tmp_path / "sample.csv"
    f.write_text("col1,col2,target\n1,0.5,high\n2,1.5,low\n3,2.5,high\n4,3.5,low\n5,4.5,high\n")
    return f


@pytest.fixture
def sample_csv_advanced(tmp_path):
    f = tmp_path / "advanced.csv"
    f.write_text(
        "id,name,age,score,active,salary,join_date\n"
        "1,Alice,30,95.5,true,75000,2024-01-15\n"
        "2,Bob,25,88.2,false,65000,2023-06-01\n"
        "3,Charlie,35,92.1,true,85000,2025-03-20\n"
    )
    return f


class TestDatasetRegistrationPipeline:
    @pytest.fixture
    def pipeline(self):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pl = DatasetRegistrationPipeline()
            pl._catalog.register = AsyncMock(return_value={"uuid": "mock-uuid", "dataset_type": "test"})
            return pl

    @pytest.mark.asyncio
    async def test_compute_statistics(self, sample_csv):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        stats = await pipeline.compute_statistics(sample_csv)
        assert stats["row_count"] == 5
        assert stats["column_count"] == 3
        assert stats["total_cells"] == 15
        assert stats["missing_cells"] == 0
        assert stats["duplicate_count"] >= 0
        assert "numerical_columns" in stats
        assert "categorical_columns" in stats

    @pytest.mark.asyncio
    async def test_compute_statistics_with_missing(self, tmp_path):
        f = tmp_path / "missing.csv"
        f.write_text("a,b\n1,2\n,4\n5,\n")
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        stats = await pipeline.compute_statistics(f)
        assert stats["missing_cells"] > 0

    @pytest.mark.asyncio
    async def test_compute_statistics_empty_file(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("a,b\n")
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        stats = await pipeline.compute_statistics(f)
        assert stats["row_count"] == 0
        assert stats["total_cells"] == 0

    @pytest.mark.asyncio
    async def test_compute_feature_summary(self, sample_csv_advanced):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        summary = await pipeline.compute_feature_summary(sample_csv_advanced)
        assert "name" in summary
        assert "age" in summary
        assert "score" in summary
        assert summary["name"]["dtype"] == "object"
        assert summary["age"]["cardinality"] == 3

    @pytest.mark.asyncio
    async def test_compute_feature_summary_cardinality_ratio(self, sample_csv_advanced):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        summary = await pipeline.compute_feature_summary(sample_csv_advanced)
        assert 0 < summary["name"]["cardinality_ratio"] <= 1.0

    @pytest.mark.asyncio
    async def test_compute_missing_values(self, sample_csv):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        missing = await pipeline.compute_missing_values(sample_csv)
        for col in ("col1", "col2", "target"):
            assert col in missing
            assert missing[col]["missing_count"] == 0
            assert missing[col]["missing_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_compute_missing_values_with_nulls(self, tmp_path):
        f = tmp_path / "nulls.csv"
        f.write_text("a,b\n1,2\n,4\n5,\n")
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        missing = await pipeline.compute_missing_values(f)
        assert missing["a"]["missing_count"] == 1
        assert missing["b"]["missing_count"] == 1

    @pytest.mark.asyncio
    async def test_generate_preview_default_rows(self, sample_csv):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        preview = await pipeline.generate_preview(sample_csv)
        assert len(preview) == 5

    @pytest.mark.asyncio
    async def test_generate_preview_limited_rows(self, sample_csv):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        preview = await pipeline.generate_preview(sample_csv, n_rows=2)
        assert len(preview) == 2

    @pytest.mark.asyncio
    async def test_generate_preview_with_nulls(self, tmp_path):
        f = tmp_path / "null_preview.csv"
        f.write_text("a,b,c\n1,,3\n4,5,\n")
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        preview = await pipeline.generate_preview(f)
        assert len(preview) == 2

    @pytest.mark.asyncio
    async def test_compute_checksum_file(self, sample_csv):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        cs = await pipeline.compute_checksum(sample_csv)
        assert len(cs) == 64
        assert isinstance(cs, str)

    @pytest.mark.asyncio
    async def test_compute_checksum_directory(self, tmp_path):
        d = tmp_path / "datadir"
        d.mkdir()
        (d / "a.csv").write_text("x\n1\n")
        (d / "b.csv").write_text("y\n2\n")
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        cs = await pipeline.compute_checksum(d)
        assert len(cs) == 64

    @pytest.mark.asyncio
    async def test_verify_integrity_match(self, sample_csv):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        cs = await pipeline.compute_checksum(sample_csv)
        assert await pipeline.verify_integrity(sample_csv, cs) is True

    @pytest.mark.asyncio
    async def test_verify_integrity_mismatch(self, sample_csv):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        assert await pipeline.verify_integrity(sample_csv, "badchecksum") is False

    @pytest.mark.asyncio
    async def test_generate_schema(self, sample_csv_advanced):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        schema = await pipeline.generate_schema(sample_csv_advanced)
        assert "id" in schema
        assert "name" in schema
        assert "age" in schema
        assert "score" in schema
        assert "active" in schema

    @pytest.mark.asyncio
    async def test_build_feature_columns(self, sample_csv_advanced):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        features = await pipeline.build_feature_columns(sample_csv_advanced)
        assert "features" in features
        assert "targets" in features
        assert "categorical" in features
        assert "numerical" in features
        assert "temporal" in features
        assert "entity" in features

    @pytest.mark.asyncio
    async def test_register_dataset_success(self, sample_csv):
        with patch("datasets.statistics.DatasetStatistics.compute", new=AsyncMock(return_value={"row_count": 5, "column_count": 3})), \
             patch("datasets.profiling.DatasetProfiler.profile", new=AsyncMock(return_value=None)):
            import data_acquisition.registration as reg_mod
            orig_catalog = reg_mod.DatasetCatalog
            try:
                mock_catalog = MagicMock()
                mock_catalog.register = AsyncMock(return_value={"uuid": "mock-uuid-123", "dataset_type": "test"})
                reg_mod.DatasetCatalog = MagicMock(return_value=mock_catalog)
                pipeline = DatasetRegistrationPipeline()
                with patch.object(pipeline._manifest_gen, "generate_manifest") as mock_gen, \
                     patch.object(pipeline._manifest_gen, "save_manifest") as mock_save:
                    mock_gen.return_value = MagicMock()
                    mock_save.return_value = sample_csv.parent / "dataset.yaml"
                    result = await pipeline.register_dataset(
                        dataset_name="test_ds", source="test_source",
                        version="1", processed_path=sample_csv,
                    )
                assert result.status == "registered"
                assert result.registration_id == "mock-uuid-123"
            finally:
                reg_mod.DatasetCatalog = orig_catalog

    @pytest.mark.asyncio
    async def test_register_dataset_failure_handled(self, tmp_path):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
            f = tmp_path / "bad.csv"
            f.write_text("not,enough,columns\n")
            result = await pipeline.register_dataset(
                dataset_name="fail", source="src",
                version="1", processed_path=f,
            )
        assert result.status == "failed"
        assert result.error is not None

    def test_load_dataframe_csv(self, sample_csv):
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        df = pipeline._load_dataframe(sample_csv)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5

    def test_load_dataframe_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('[{"a": 1, "b": 2}, {"a": 3, "b": 4}]')
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        df = pipeline._load_dataframe(f)
        assert len(df) == 2

    def test_load_dataframe_unsupported(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("unrecognized")
        with patch.multiple(
            "data_acquisition.registration",
            DatasetCatalog=MagicMock(),
            DatasetProfiler=MagicMock(),
            DatasetStatistics=MagicMock(),
        ):
            pipeline = DatasetRegistrationPipeline()
        with pytest.raises(ValueError, match="Unsupported file format"):
            pipeline._load_dataframe(f)


class TestRegistrationFlow:
    @pytest.fixture
    def flow(self):
        return RegistrationFlow()

    def test_init(self, flow):
        assert flow._pipeline is not None
        assert flow._lake is not None
        assert flow._cfg is not None

    @pytest.mark.asyncio
    async def test_get_registration_status_not_registered(self, flow):
        with patch("datasets.catalog.DatasetCatalog") as mock_catalog_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value=None)
            mock_catalog_cls.return_value = mock_catalog
            status = await flow.get_registration_status("nonexistent")
        assert status["registered"] is False
        assert status["dataset_name"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_get_registration_status_registered(self, flow):
        with patch("datasets.catalog.DatasetCatalog") as mock_catalog_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value={
                "uuid": "abc", "dataset_type": "test", "created_at": "2025-01-01",
            })
            mock_catalog_cls.return_value = mock_catalog
            status = await flow.get_registration_status("test_ds")
        assert status["registered"] is True
        assert status["uuid"] == "abc"

    @pytest.mark.asyncio
    async def test_list_registered_datasets(self, flow):
        with patch("datasets.catalog.DatasetCatalog") as mock_catalog_cls:
            mock_catalog = MagicMock()
            mock_catalog.search = AsyncMock(return_value=([{"name": "ds1"}, {"name": "ds2"}], 2))
            mock_catalog_cls.return_value = mock_catalog
            results = await flow.list_registered_datasets()
        assert len(results) == 2


class TestDatasetResolver:
    @pytest.fixture
    def resolver(self):
        return DatasetResolver()

    def test_init_loads_registry(self, resolver):
        assert len(resolver._registry._sources) == 23

    @pytest.mark.asyncio
    async def test_resolve_dataset_from_registry(self, resolver):
        result = await resolver.resolve_dataset("gdelt-events")
        assert result["source"] == "gdelt-events"
        assert result["display_name"] == "GDELT Events"
        assert "schema" in result
        assert result["version"] == "2.0"

    @pytest.mark.asyncio
    async def test_resolve_dataset_with_custom_version(self, resolver):
        result = await resolver.resolve_dataset("gdelt-events", version="custom-1")
        assert result["version"] == "custom-1"

    @pytest.mark.asyncio
    async def test_resolve_dataset_from_catalog(self, resolver):
        with patch("datasets.catalog.DatasetCatalog") as mock_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value={
                "source": "test_source", "description": "A catalog dataset",
                "tags": ["tag1"],
            })
            mock_cls.return_value = mock_catalog
            result = await resolver.resolve_dataset("custom-dataset")
        assert result["source"] == "test_source"
        assert "path" in result

    @pytest.mark.asyncio
    async def test_resolve_dataset_local_path(self, resolver, tmp_path):
        f = tmp_path / "local_data.csv"
        f.write_text("a,b\n1,2\n")
        with patch("datasets.catalog.DatasetCatalog") as mock_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value=None)
            mock_cls.return_value = mock_catalog
            rel_str = "." + str(f).replace("\\", "/")
            result = await resolver.resolve_dataset(rel_str)
        assert result["category"] == "local"

    @pytest.mark.asyncio
    async def test_resolve_dataset_not_found(self, resolver):
        with patch("datasets.catalog.DatasetCatalog") as mock_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value=None)
            mock_cls.return_value = mock_catalog
            with pytest.raises(ValueError, match="Dataset not found"):
                await resolver.resolve_dataset("completely-bogus-name")

    @pytest.mark.asyncio
    async def test_list_available_datasets(self, resolver):
        datasets = await resolver.list_available_datasets()
        assert len(datasets) == 23
        names = [d["name"] for d in datasets]
        assert "gdelt-events" in names
        assert "eia-petroleum" in names
        assert "opec-production" in names
        assert "ofac-sanctions" in names

    @pytest.mark.asyncio
    async def test_list_available_datasets_has_expected_fields(self, resolver):
        datasets = await resolver.list_available_datasets()
        for d in datasets:
            assert "name" in d
            assert "display_name" in d
            assert "category" in d
            assert "version" in d
            assert "feature_count" in d

    @pytest.mark.asyncio
    async def test_validate_dataset_ref_from_registry(self, resolver):
        errors = await resolver.validate_dataset_ref("gdelt-events")
        assert errors == []

    @pytest.mark.asyncio
    async def test_validate_dataset_ref_not_found(self, resolver):
        with patch("datasets.catalog.DatasetCatalog") as mock_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value=None)
            mock_cls.return_value = mock_catalog
            errors = await resolver.validate_dataset_ref("unknown-dataset")
        assert len(errors) == 1
        assert "not found" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_dataset_ref_local_path(self, resolver):
        with patch("datasets.catalog.DatasetCatalog") as mock_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value=None)
            mock_cls.return_value = mock_catalog
            errors = await resolver.validate_dataset_ref("./local/path.csv")
        assert errors == []

    @pytest.mark.asyncio
    async def test_resolve_for_experiment(self, resolver):
        result = await resolver.resolve_for_experiment(
            "gdelt-events",
            {"experiment": {}, "model": {}, "dataset": {}},
        )
        assert result["dataset"]["name"] == "gdelt-events"
        assert result["dataset"]["version"] == "2.0"
        assert "feature_names" in result["dataset"]


class TestExperimentDatasetResolver:
    @pytest.fixture
    def resolver(self):
        return ExperimentDatasetResolver()

    @pytest.mark.asyncio
    async def test_prepare_experiment_with_dataset_string(self, resolver):
        with patch("datasets.catalog.DatasetCatalog") as mock_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value=None)
            mock_cls.return_value = mock_catalog
            result = await resolver.prepare_experiment(
                "exp-001",
                {"dataset": {"name": "gdelt-events"}, "model": {"type": "rf"}},
            )
        assert result["experiment"]["name"] == "exp-001"
        assert result["dataset"]["name"] == "gdelt-events"

    @pytest.mark.asyncio
    async def test_prepare_experiment_with_dict(self, resolver):
        result = await resolver.prepare_experiment(
            "exp-002",
            {"dataset": {"name": "custom"}, "model": {"type": "lr"}},
        )
        assert result["dataset"]["name"] == "custom"
        assert result["experiment"]["name"] == "exp-002"

    @pytest.mark.asyncio
    async def test_get_dataset_card_not_in_registry(self, resolver):
        with patch("datasets.catalog.DatasetCatalog") as mock_cls:
            mock_catalog = MagicMock()
            mock_catalog.get = AsyncMock(return_value={"description": "Custom ds", "dataset_type": "custom"})
            mock_cls.return_value = mock_catalog
            card = await resolver.get_dataset_card("custom-dataset")
        assert card["name"] == "custom-dataset"
        assert card["feature_count"] == 0

    @pytest.mark.asyncio
    async def test_get_dataset_card_from_registry(self, resolver):
        card = await resolver.get_dataset_card("eia-petroleum")
        assert card["name"] == "eia-petroleum"
        assert card["license"] == "Open Data (US Gov)"
        assert card["update_frequency"] == "weekly"
        assert card["feature_count"] > 0
