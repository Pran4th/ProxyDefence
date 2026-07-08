"""End-to-end GDELT pipeline test."""
import asyncio
import time
import zipfile
from pathlib import Path

import pytest

from data_acquisition.gdelt_pipeline.master_file_reader import MasterFileReader
from data_acquisition.gdelt_pipeline.filter import GDELTFilter, FilterConfig
from data_acquisition.gdelt_pipeline.downloader import GDELTDownloader
from data_acquisition.gdelt_pipeline.parser import GDELTParser
from data_acquisition.gdelt_pipeline.registration import GDELTRegistration
from data_acquisition.gdelt_pipeline.validation import GDELTValidator
from data_acquisition.gdelt_pipeline.report import ReportGenerator
from data_acquisition.gdelt_pipeline.pipeline import PipelineResult, PipelineStageResult


@pytest.mark.asyncio
@pytest.mark.slow
async def test_gdelt_pipeline_e2e():
    overall_start = time.monotonic()
    start_date = "2024-01-01"
    end_date = "2024-01-01"
    version = "20240101"

    # STAGE 1: DISCOVER
    reader = MasterFileReader()
    result = await reader.fetch()
    assert result.total_discovered > 0, "master file list should have entries"
    assert result.earliest is not None
    assert result.latest is not None
    assert "export.CSV.zip" in result.by_type
    assert "mentions.CSV.zip" in result.by_type
    assert "gkg.csv.zip" in result.by_type

    # STAGE 2: FILTER
    filter_cfg = FilterConfig(start_date=start_date, end_date=end_date)
    filtered = GDELTFilter().filter(result.entries, filter_cfg)
    first_hour = [e for e in filtered if "000000" in e.url]
    assert len(first_hour) >= 3, "should have at least 3 files for first hour (events, mentions, gkg)"
    assert any("export" in e.url for e in first_hour)
    assert any("mentions" in e.url for e in first_hour)
    assert any("gkg" in e.url for e in first_hour)

    # STAGE 3: DOWNLOAD
    downloader = GDELTDownloader()
    dl_results = await downloader.download_batch(first_hour, version=version)
    completed_dl = [r for r in dl_results if r.status == "completed"]
    assert len(completed_dl) >= 3, "should have downloaded at least 3 files"
    for r in completed_dl:
        assert r.files, f"downloaded file should exist for {r.source}"
        assert r.files[0].exists(), f"downloaded file path should exist: {r.files[0]}"
        assert r.total_size_bytes > 0, f"downloaded file should not be empty for {r.source}"

    # STAGE 4: PARSE
    parser = GDELTParser()
    files_by_type = {"events": [], "mentions": [], "gkg": []}
    for r in dl_results:
        if r.status == "completed":
            for fp in r.files:
                ext_part = "events" if "export" in str(fp) else "mentions" if "mentions" in str(fp) else "gkg"
                extract_dir = fp.parent / "extracted"
                extract_dir.mkdir(exist_ok=True)
                with zipfile.ZipFile(fp, "r") as zf:
                    zf.extractall(extract_dir)
                for csv_file in extract_dir.glob("*.csv"):
                    files_by_type[ext_part].append(csv_file)

    parse_results = []
    for ds_type, file_list in files_by_type.items():
        for fp in file_list:
            pr = await parser.parse_file(input_path=fp, dataset_type=ds_type, version=version)
            parse_results.append(pr)
            assert pr.records_parsed > 0, f"should parse records for {ds_type}"
            assert pr.output_path.exists(), f"output should exist for {ds_type}"

    total_parsed = sum(r.records_parsed for r in parse_results)
    assert total_parsed > 0, "should parse at least some records"

    # STAGE 5: REGISTER
    reg = GDELTRegistration()
    for pr in parse_results:
        ds_type_map = {"gdelt-events": "events", "gdelt-mentions": "mentions", "gdelt-gkg": "gkg"}
        ds_type = ds_type_map.get(pr.source, "unknown")
        rr = await reg.register_parsed_dataset(dataset_type=ds_type, version=version, csv_path=pr.output_path)
        assert rr.status == "registered", f"registration should succeed for {ds_type}: {rr.error}"
        assert rr.registration is not None
        assert rr.registration.statistics.get("row_count", 0) > 0

    # STAGE 6: VALIDATE
    validator = GDELTValidator()
    for dl_r in dl_results:
        for fp in dl_r.files:
            matching = [e for e in first_hour if e.md5 in str(fp)]
            expected_md5 = matching[0].md5 if matching else None
            v = validator.full_validation(
                dataset_type=dl_r.source, version=version,
                zip_path=fp, expected_md5=expected_md5,
            )
            assert v.all_passed, f"validation should pass for downloaded file {fp.name}"

    for pr in parse_results:
        v = validator.full_validation(
            dataset_type=pr.source, version=version,
            csv_path=pr.output_path,
        )
        assert v.all_passed, f"validation should pass for parsed file {pr.output_path.name}"

    # GENERATE REPORT
    report_gen = ReportGenerator()
    pl_result = PipelineResult(
        version=version, start_date=start_date, end_date=end_date,
        overall_status="completed", total_duration_seconds=time.monotonic() - overall_start,
        stages=[
            PipelineStageResult(stage="discover", status="completed", duration_seconds=1.0,
                data={"total_discovered": result.total_discovered, "by_type": result.by_type,
                      "earliest": result.earliest, "latest": result.latest}),
            PipelineStageResult(stage="filter", status="completed", duration_seconds=1.0,
                data={"total_filtered": len(first_hour),
                      "by_type": {e.dataset_type: 1 for e in first_hour}}),
            PipelineStageResult(stage="download", status="completed", duration_seconds=1.0,
                data={"completed": len(completed_dl), "failed": len(dl_results) - len(completed_dl),
                      "total_bytes": sum(r.total_size_bytes for r in completed_dl)}),
            PipelineStageResult(stage="parse", status="completed", duration_seconds=1.0,
                data={"records_parsed": total_parsed, "records_failed": sum(r.records_failed for r in parse_results),
                      "canonical_valid": total_parsed, "canonical_invalid": 0}),
            PipelineStageResult(stage="register", status="completed", duration_seconds=1.0,
                data={"registered": 3, "failed": 0, "results": {}}),
        ],
    )
    report = report_gen.generate(pl_result)
    assert report.overall_status == "completed"
    md = report_gen.to_markdown(report)
    assert "GDELT Pipeline Validation Report" in md
    assert str(total_parsed) in md
