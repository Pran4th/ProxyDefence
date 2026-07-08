import json
import hashlib
from pathlib import Path
from dataclasses import asdict

import pytest
import yaml

from data_acquisition.config import DataAcquisitionConfig, get_config
from data_acquisition.lake import DataLake, DataLakeConfig
from data_acquisition.manifest import DatasetManifest, ManifestGenerator
from data_acquisition.source_registry import SourceRegistry, SourceDefinition, DATASET_REGISTRY


class TestDataAcquisitionConfig:
    def test_default_values(self):
        cfg = DataAcquisitionConfig()
        assert cfg.base_dir == "./datasets"
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 5.0
        assert cfg.chunk_size == 8192
        assert cfg.verify_checksums is True
        assert cfg.preserve_archives is False
        assert cfg.log_level == "INFO"

    def test_computed_paths(self):
        cfg = DataAcquisitionConfig(base_dir="/tmp/test_data")
        assert cfg.raw_dir == "/tmp/test_data/raw"
        assert cfg.processed_dir == "/tmp/test_data/processed"
        assert cfg.normalized_dir == "/tmp/test_data/normalized"
        assert cfg.features_dir == "/tmp/test_data/features"
        assert cfg.training_dir == "/tmp/test_data/training"
        assert cfg.registry_dir == "/tmp/test_data/registry"

    def test_get_config_from_env(self, monkeypatch):
        monkeypatch.setenv("DATASET_DIR", "/env/datasets")
        monkeypatch.setenv("DA_MAX_RETRIES", "5")
        monkeypatch.setenv("DA_RETRY_DELAY", "10.0")
        monkeypatch.setenv("DA_CHUNK_SIZE", "4096")
        monkeypatch.setenv("DA_VERIFY_CHECKSUMS", "0")
        monkeypatch.setenv("DA_PRESERVE_ARCHIVES", "1")
        monkeypatch.setenv("DA_LOG_LEVEL", "DEBUG")
        cfg = get_config()
        assert cfg.base_dir == "/env/datasets"
        assert cfg.max_retries == 5
        assert cfg.retry_delay == 10.0
        assert cfg.chunk_size == 4096
        assert cfg.verify_checksums is False
        assert cfg.preserve_archives is True
        assert cfg.log_level == "DEBUG"

    def test_all_computed_paths_are_strings(self):
        cfg = DataAcquisitionConfig()
        for attr in ("raw_dir", "processed_dir", "normalized_dir", "features_dir", "training_dir", "registry_dir"):
            val = getattr(cfg, attr)
            assert isinstance(val, str), f"{attr} is not a string"


class TestDataLakeConfig:
    def test_default_values(self):
        cfg = DataLakeConfig()
        assert cfg.base_dir == "./datasets"
        assert cfg.max_retries == 3

    def test_custom_values(self):
        cfg = DataLakeConfig(base_dir="/custom/path", max_retries=7)
        assert cfg.base_dir == "/custom/path"
        assert cfg.max_retries == 7


class TestDataLake:
    @pytest.fixture
    def lake(self, tmp_path):
        cfg = DataLakeConfig(base_dir=str(tmp_path / "lake"))
        return DataLake(config=cfg)

    @pytest.mark.asyncio
    async def test_ensure_directories_creates_all(self, lake):
        await lake.ensure_directories()
        for d in [lake.raw_dir, lake.processed_dir, lake.normalized_dir,
                  lake.features_dir, lake.training_dir, lake.registry_dir]:
            assert d.exists()
            assert d.is_dir()

    @pytest.mark.asyncio
    async def test_ensure_directories_idempotent(self, lake):
        await lake.ensure_directories()
        await lake.ensure_directories()
        for d in [lake.raw_dir, lake.processed_dir]:
            assert d.exists()

    @pytest.mark.asyncio
    async def test_get_raw_path_without_version(self, lake):
        p = await lake.get_raw_path("gdelt")
        assert p == lake.raw_dir / "gdelt"

    @pytest.mark.asyncio
    async def test_get_raw_path_with_version(self, lake):
        p = await lake.get_raw_path("gdelt", "v2")
        assert p == lake.raw_dir / "gdelt" / "v2"

    @pytest.mark.asyncio
    async def test_get_processed_path_without_version(self, lake):
        p = await lake.get_processed_path("dataset1")
        assert p == lake.processed_dir / "dataset1"

    @pytest.mark.asyncio
    async def test_get_processed_path_with_version(self, lake):
        p = await lake.get_processed_path("dataset1", "v1")
        assert p == lake.processed_dir / "dataset1" / "v1"

    @pytest.mark.asyncio
    async def test_get_normalized_path(self, lake):
        p = await lake.get_normalized_path("ds")
        assert p == lake.normalized_dir / "ds"

    @pytest.mark.asyncio
    async def test_get_features_path(self, lake):
        p = await lake.get_features_path("ds")
        assert p == lake.features_dir / "ds"

    @pytest.mark.asyncio
    async def test_get_training_path(self, lake):
        p = await lake.get_training_path("ds")
        assert p == lake.training_dir / "ds"

    @pytest.mark.asyncio
    async def test_get_registry_path(self, lake):
        p = await lake.get_registry_path("ds")
        assert p == lake.registry_dir / "ds"

    @pytest.mark.asyncio
    async def test_list_versions_empty(self, lake):
        versions = await lake.list_versions("nonexistent")
        assert versions == []

    @pytest.mark.asyncio
    async def test_list_versions_with_data(self, lake):
        await lake.ensure_directories()
        vdir = lake.raw_dir / "mysource" / "v1"
        vdir.mkdir(parents=True)
        (vdir / "file1.csv").write_text("a,b,c\n1,2,3\n")
        versions = await lake.list_versions("mysource")
        assert len(versions) == 1
        assert versions[0]["version"] == "v1"
        assert versions[0]["source"] == "mysource"
        assert versions[0]["file_count"] == 1
        assert versions[0]["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_list_versions_sorts_entries(self, lake):
        await lake.ensure_directories()
        for v in ("v3", "v1", "v2"):
            d = lake.raw_dir / "src" / v
            d.mkdir(parents=True)
            (d / f"f{v}.txt").write_text("data")
        versions = await lake.list_versions("src")
        assert len(versions) == 3
        assert versions[0]["version"] == "v1"

    @pytest.mark.asyncio
    async def test_list_sources_empty(self, lake):
        sources = await lake.list_sources()
        assert sources == []

    @pytest.mark.asyncio
    async def test_list_sources_returns_sorted(self, lake):
        await lake.ensure_directories()
        for name in ("zzz", "aaa", "mmm"):
            (lake.raw_dir / name).mkdir(parents=True)
        sources = await lake.list_sources()
        assert sources == ["aaa", "mmm", "zzz"]

    @pytest.mark.asyncio
    async def test_get_source_info_not_exists(self, lake):
        info = await lake.get_source_info("ghost")
        assert info == {"source": "ghost", "exists": False}

    @pytest.mark.asyncio
    async def test_get_source_info_with_versions(self, lake):
        await lake.ensure_directories()
        d = lake.raw_dir / "test_src"
        d.mkdir()
        (d / "v1").mkdir()
        (d / "v1" / "data.csv").write_text("x,y\n1,2\n")
        info = await lake.get_source_info("test_src")
        assert info["source"] == "test_src"
        assert info["exists"] is True
        assert info["version_count"] == 1
        assert info["total_files"] == 1
        assert info["total_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_get_lake_stats_empty(self, lake):
        stats = await lake.get_lake_stats()
        assert stats["total_size_bytes"] == 0
        assert stats["file_count"] == 0

    @pytest.mark.asyncio
    async def test_get_lake_stats_with_data(self, lake):
        await lake.ensure_directories()
        (lake.raw_dir / "src1").mkdir()
        (lake.raw_dir / "src1" / "f1.csv").write_text("a\n1\n")
        (lake.processed_dir / "ds1" / "v1").mkdir(parents=True)
        (lake.processed_dir / "ds1" / "v1" / "p1.parquet").write_text("fake")
        stats = await lake.get_lake_stats()
        assert stats["source_count"] == 1
        assert stats["total_size_bytes"] > 0
        assert stats["file_count"] == 2
        assert "raw" in stats["directories"]
        assert "processed" in stats["directories"]

    @pytest.mark.asyncio
    async def test_create_version_dir(self, lake):
        await lake.ensure_directories()
        p = await lake.create_version_dir("src_a", "v99")
        assert p.exists()
        assert str(p).endswith("v99")

    @pytest.mark.asyncio
    async def test_get_disk_usage_empty(self, lake):
        usage = await lake.get_disk_usage()
        assert usage == {}

    @pytest.mark.asyncio
    async def test_get_disk_usage_with_data(self, lake):
        await lake.ensure_directories()
        (lake.raw_dir / "src_x").mkdir()
        (lake.raw_dir / "src_x" / "f.dat").write_text("1234567890")
        (lake.raw_dir / "src_y").mkdir()
        (lake.raw_dir / "src_y" / "g.dat").write_text("abcdef")
        usage = await lake.get_disk_usage()
        assert "src_x" in usage
        assert "src_y" in usage
        assert usage["src_x"] == 10
        assert usage["src_y"] == 6


class TestDatasetManifest:
    def test_minimal_manifest(self):
        m = DatasetManifest(
            dataset_name="test_ds",
            version="1",
            source="test_source",
            download_date="2025-01-01",
            file_count=0,
            total_size_bytes=0,
            checksum="abc",
            schema_hash="def",
        )
        assert m.dataset_name == "test_ds"
        assert m.row_count is None
        assert m.column_count is None
        assert isinstance(m.last_updated, str)
        assert m.license == ""
        assert m.tags == []
        assert m.metadata == {}

    def test_full_manifest(self):
        m = DatasetManifest(
            dataset_name="full",
            version="2.0",
            source="eia",
            download_date="2025-06-01",
            file_count=5,
            total_size_bytes=1024,
            checksum="chk",
            schema_hash="shash",
            row_count=100,
            column_count=20,
            license="CC BY",
            citation="test citation",
            description="A test dataset",
            tags=["energy", "eia"],
            metadata={"key": "value"},
        )
        assert m.row_count == 100
        assert m.column_count == 20
        assert m.license == "CC BY"
        assert m.tags == ["energy", "eia"]
        assert m.metadata == {"key": "value"}

    def test_manifest_asdict_fields(self):
        m = DatasetManifest(
            dataset_name="ds",
            version="1",
            source="src",
            download_date="d",
            file_count=0,
            total_size_bytes=0,
            checksum="c",
            schema_hash="s",
        )
        d = asdict(m)
        assert d["dataset_name"] == "ds"
        assert d["version"] == "1"
        assert d["source"] == "src"


class TestManifestGenerator:
    @pytest.fixture
    def gen(self):
        return ManifestGenerator()

    @pytest.mark.asyncio
    async def test_generate_manifest_basic(self, gen, tmp_path):
        file1 = tmp_path / "data1.csv"
        file1.write_text("col1,col2\n1,2\n3,4\n")
        file2 = tmp_path / "data2.csv"
        file2.write_text("a,b\nx,y\n")
        manifest = await gen.generate_manifest(
            dataset_name="test_ds",
            version="v1",
            source="test_source",
            file_paths=[file1, file2],
            schema={"col1": "int", "col2": "int"},
        )
        assert manifest.dataset_name == "test_ds"
        assert manifest.version == "v1"
        assert manifest.source == "test_source"
        assert manifest.file_count == 2
        assert manifest.total_size_bytes > 0
        assert manifest.checksum != ""
        assert manifest.schema_hash != ""
        assert manifest.download_date != ""

    @pytest.mark.asyncio
    async def test_generate_manifest_empty_files(self, gen):
        manifest = await gen.generate_manifest(
            dataset_name="empty",
            version="1",
            source="src",
            file_paths=[],
        )
        assert manifest.file_count == 0
        assert manifest.total_size_bytes == 0
        assert manifest.checksum == hashlib.sha256().hexdigest()

    @pytest.mark.asyncio
    async def test_generate_manifest_extra_kwargs(self, gen, tmp_path):
        f = tmp_path / "a.csv"
        f.write_text("x\n1\n")
        manifest = await gen.generate_manifest(
            dataset_name="ds",
            version="1",
            source="src",
            file_paths=[f],
            description="My dataset",
            citation="Author et al.",
            license="MIT",
        )
        assert manifest.description == "My dataset"
        assert manifest.citation == "Author et al."
        assert manifest.license == "MIT"

    @pytest.mark.asyncio
    async def test_save_and_load_manifest(self, gen, tmp_path):
        file1 = tmp_path / "data.csv"
        file1.write_text("a,b\n1,2\n")
        manifest = await gen.generate_manifest(
            dataset_name="roundtrip",
            version="v1",
            source="src",
            file_paths=[file1],
        )
        output_dir = tmp_path / "output"
        saved = await gen.save_manifest(manifest, output_dir)
        assert saved.exists()
        assert saved.name == "dataset.yaml"

        loaded = await gen.load_manifest(saved)
        assert loaded.dataset_name == "roundtrip"
        assert loaded.version == "v1"
        assert loaded.checksum == manifest.checksum
        assert loaded.schema_hash == manifest.schema_hash

    @pytest.mark.asyncio
    async def test_save_manifest_yaml_content(self, gen, tmp_path):
        file1 = tmp_path / "x.csv"
        file1.write_text("v\n1\n")
        manifest = await gen.generate_manifest(
            dataset_name="yaml_test",
            version="2",
            source="src",
            file_paths=[file1],
        )
        output_dir = tmp_path / "meta"
        saved = await gen.save_manifest(manifest, output_dir)
        with open(saved, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["dataset_name"] == "yaml_test"
        assert data["version"] == "2"

    @pytest.mark.asyncio
    async def test_verify_manifest_match(self, gen, tmp_path):
        f = tmp_path / "match.csv"
        f.write_text("content")
        manifest = await gen.generate_manifest(
            dataset_name="match", version="1", source="src", file_paths=[f]
        )
        valid = await gen.verify_manifest(manifest, [f])
        assert valid is True

    @pytest.mark.asyncio
    async def test_verify_manifest_mismatch(self, gen, tmp_path):
        f = tmp_path / "original.csv"
        f.write_text("original content")
        manifest = await gen.generate_manifest(
            dataset_name="mismatch", version="1", source="src", file_paths=[f]
        )
        f.write_text("modified content")
        valid = await gen.verify_manifest(manifest, [f])
        assert valid is False

    @pytest.mark.asyncio
    async def test_compute_checksum_consistent(self, gen, tmp_path):
        f = tmp_path / "stable.csv"
        f.write_text("hello world")
        c1 = await gen.compute_checksum([f])
        c2 = await gen.compute_checksum([f])
        assert c1 == c2
        assert len(c1) == 64

    @pytest.mark.asyncio
    async def test_compute_checksum_multiple_files(self, gen, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("aaa")
        f2 = tmp_path / "b.txt"
        f2.write_text("bbb")
        c = await gen.compute_checksum([f1, f2])
        assert len(c) == 64

    @pytest.mark.asyncio
    async def test_compute_checksum_missing_file_skipped(self, gen, tmp_path):
        missing = tmp_path / "missing.csv"
        c = await gen.compute_checksum([missing])
        assert c == hashlib.sha256().hexdigest()

    @pytest.mark.asyncio
    async def test_compute_schema_hash_deterministic(self, gen):
        schema = {"a": "int", "b": "float"}
        h1 = await gen.compute_schema_hash(schema)
        h2 = await gen.compute_schema_hash(schema)
        assert h1 == h2

    @pytest.mark.asyncio
    async def test_compute_schema_hash_different(self, gen):
        h1 = await gen.compute_schema_hash({"x": "int"})
        h2 = await gen.compute_schema_hash({"x": "str"})
        assert h1 != h2

    @pytest.mark.asyncio
    async def test_compute_schema_hash_empty(self, gen):
        h = await gen.compute_schema_hash({})
        assert len(h) == 64

    @pytest.mark.asyncio
    async def test_get_manifest_path(self, gen):
        p = await gen.get_manifest_path("ds", "v1")
        assert str(p).endswith("dataset.yaml")
        assert "processed" in str(p).replace("\\", "/")

    @pytest.mark.asyncio
    async def test_get_manifest_path_with_lake_path(self, gen, tmp_path):
        gen._set_lake_path(tmp_path)
        p = await gen.get_manifest_path("ds", "v1")
        assert p == tmp_path / "dataset.yaml"


class TestSourceRegistry:
    @pytest.fixture
    def registry(self):
        r = SourceRegistry()
        r.register(SourceDefinition(
            name="test-source",
            display_name="Test Source",
            description="A test",
            category="energy",
            update_frequency="daily",
            connector_type="rest_api",
            default_parser="TestParser",
        ))
        r.register(SourceDefinition(
            name="other-source",
            display_name="Other",
            description="Another test",
            category="shipping",
            update_frequency="weekly",
            connector_type="csv",
            default_parser="OtherParser",
        ))
        r.register(SourceDefinition(
            name="inactive-source",
            display_name="Inactive",
            description="Not active",
            category="energy",
            update_frequency="monthly",
            connector_type="rest_api",
            default_parser="InactiveParser",
            is_active=False,
        ))
        return r

    def test_register_and_get(self, registry):
        sd = registry.get("test-source")
        assert sd is not None
        assert sd.name == "test-source"
        assert sd.display_name == "Test Source"
        assert sd.category == "energy"

    def test_get_nonexistent(self, registry):
        assert registry.get("nope") is None

    def test_list_sources_all_active(self, registry):
        sources = registry.list_sources()
        names = [s.name for s in sources]
        assert "test-source" in names
        assert "other-source" in names
        assert "inactive-source" not in names

    def test_list_sources_include_inactive(self, registry):
        sources = registry.list_sources(active_only=False)
        names = [s.name for s in sources]
        assert "inactive-source" in names

    def test_list_sources_filter_by_category(self, registry):
        sources = registry.list_sources(category="shipping")
        assert len(sources) == 1
        assert sources[0].name == "other-source"

    def test_list_sources_no_match_category(self, registry):
        sources = registry.list_sources(category="nonexistent")
        assert sources == []

    def test_get_categories(self, registry):
        cats = registry.get_categories()
        assert "energy" in cats
        assert "shipping" in cats
        assert len(cats) == 2

    def test_get_categories_sorted(self, registry):
        cats = registry.get_categories()
        assert cats == sorted(cats)

    def test_get_by_connector(self, registry):
        srcs = registry.get_by_connector("csv")
        assert len(srcs) == 1
        assert srcs[0].name == "other-source"

    def test_remove_existing(self, registry):
        registry.remove("test-source")
        assert registry.get("test-source") is None

    def test_remove_nonexistent(self, registry):
        registry.remove("does-not-exist")

    def test_register_duplicate_overwrites(self, registry):
        registry.register(SourceDefinition(
            name="test-source",
            display_name="Updated",
            description="Updated",
            category="energy",
            update_frequency="daily",
            connector_type="rest_api",
            default_parser="UpdatedParser",
        ))
        sd = registry.get("test-source")
        assert sd.display_name == "Updated"

    def test_empty_registry_list(self):
        r = SourceRegistry()
        assert r.list_sources() == []
        assert r.get_categories() == []


class TestSourceDefinition:
    def test_default_values(self):
        sd = SourceDefinition(
            name="src",
            display_name="Source",
            description="Desc",
            category="cat",
            update_frequency="daily",
            connector_type="csv",
            default_parser="Parser",
        )
        assert sd.version == "1.0"
        assert sd.license == ""
        assert sd.citation == ""
        assert sd.tags == []
        assert sd.is_active is True
        assert sd.url_template is None
        assert sd.expected_schema == {}

    def test_full_definition(self):
        sd = SourceDefinition(
            name="full-src",
            display_name="Full Source",
            description="Full description",
            category="energy",
            update_frequency="weekly",
            connector_type="rest_api",
            default_parser="FullParser",
            url_template="https://api.example.com/{version}/data",
            expected_schema={"col": "str"},
            version="2.0",
            license="MIT",
            citation="Author (2025)",
            tags=["energy", "test"],
            is_active=False,
        )
        assert sd.url_template == "https://api.example.com/{version}/data"
        assert sd.expected_schema == {"col": "str"}
        assert sd.is_active is False


class TestDATASET_REGISTRY:
    def test_has_23_entries(self):
        assert len(DATASET_REGISTRY) == 23

    def test_all_entries_have_required_fields(self):
        for sd in DATASET_REGISTRY:
            assert sd.name, f"missing name in {sd}"
            assert sd.display_name, f"missing display_name in {sd.name}"
            assert sd.description, f"missing description in {sd.name}"
            assert sd.category, f"missing category in {sd.name}"
            assert sd.update_frequency, f"missing update_frequency in {sd.name}"
            assert sd.connector_type, f"missing connector_type in {sd.name}"
            assert sd.default_parser, f"missing default_parser in {sd.name}"

    def test_categories_covered(self):
        categories = {sd.category for sd in DATASET_REGISTRY}
        assert "geopolitical" in categories
        assert "energy" in categories
        assert "shipping" in categories
        assert "commodity" in categories
        assert "sanctions" in categories
        assert "economics" in categories
        assert "other" in categories

    def test_gdelt_entries_have_cc_by_license(self):
        gdelt_entries = [sd for sd in DATASET_REGISTRY if sd.name.startswith("gdelt")]
        for g in gdelt_entries:
            assert g.license == "CC BY 4.0"

    def test_eia_entries_have_us_gov_license(self):
        eia_entries = [sd for sd in DATASET_REGISTRY if sd.name.startswith("eia")]
        for e in eia_entries:
            assert e.license == "Open Data (US Gov)"

    def test_ofac_sanctions_expected_schema(self):
        ofac = next(sd for sd in DATASET_REGISTRY if sd.name == "ofac-sanctions")
        assert "uid" in ofac.expected_schema
        assert "firstName" in ofac.expected_schema
        assert "sdnType" in ofac.expected_schema

    def test_ais_expected_schema(self):
        ais = next(sd for sd in DATASET_REGISTRY if sd.name == "ais-global")
        assert "mmsi" in ais.expected_schema
        assert "latitude" in ais.expected_schema
        assert "longitude" in ais.expected_schema

    def test_all_parser_names_are_strings(self):
        for sd in DATASET_REGISTRY:
            assert isinstance(sd.default_parser, str)
