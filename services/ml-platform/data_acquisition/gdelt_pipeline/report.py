from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_acquisition.gdelt_pipeline.pipeline import PipelineResult, PipelineStageResult


@dataclass
class ValidationReport:
    version: str
    start_date: str | None
    end_date: str | None
    overall_status: str
    total_duration_seconds: float
    stages: list[dict]
    summary: dict
    sample_records: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ReportGenerator:
    def generate(self, pipeline_result: PipelineResult) -> ValidationReport:
        stages_summary: list[dict] = []
        all_errors: list[str] = []
        total_records_parsed = 0
        total_records_failed = 0
        total_files_downloaded = 0
        total_bytes = 0

        for stage in pipeline_result.stages:
            stage_info = {
                "stage": stage.stage,
                "status": stage.status,
                "duration_seconds": round(stage.duration_seconds, 2),
            }

            if stage.error:
                stage_info["error"] = stage.error
                all_errors.append(f"[{stage.stage}] {stage.error}")

            data = stage.data

            if stage.stage == "discover":
                stage_info["total_discovered"] = data.get("total_discovered", 0)
                stage_info["by_type"] = data.get("by_type", {})

            elif stage.stage == "filter":
                stage_info["total_filtered"] = data.get("total_filtered", 0)
                stage_info["by_type"] = data.get("by_type", {})

            elif stage.stage == "download":
                stage_info["completed"] = data.get("completed", 0)
                stage_info["failed"] = data.get("failed", 0)
                stage_info["total_bytes"] = data.get("total_bytes", 0)
                total_files_downloaded = data.get("completed", 0)
                total_bytes = data.get("total_bytes", 0)

            elif stage.stage == "parse":
                stage_info["records_parsed"] = data.get("records_parsed", 0)
                stage_info["records_failed"] = data.get("records_failed", 0)
                stage_info["canonical_valid"] = data.get("canonical_valid", 0)
                stage_info["canonical_invalid"] = data.get("canonical_invalid", 0)
                total_records_parsed = data.get("records_parsed", 0)
                total_records_failed = data.get("records_failed", 0)

            elif stage.stage == "register":
                stage_info["registered"] = data.get("registered", 0)
                stage_info["failed"] = data.get("failed", 0)
                results = data.get("results", {})
                for ds_type, r in results.items():
                    stage_info[f"{ds_type}_dataset_name"] = r.get("dataset_name", "")

            stages_summary.append(stage_info)

        throughput = 0.0
        if pipeline_result.total_duration_seconds > 0:
            throughput = (
                total_records_parsed / pipeline_result.total_duration_seconds
            )

        summary = {
            "version": pipeline_result.version,
            "start_date": pipeline_result.start_date,
            "end_date": pipeline_result.end_date,
            "overall_status": pipeline_result.overall_status,
            "total_duration_seconds": round(pipeline_result.total_duration_seconds, 2),
            "total_duration_formatted": self._format_duration(
                pipeline_result.total_duration_seconds
            ),
            "total_files_discovered": next(
                (
                    s.get("total_discovered", 0)
                    for s in stages_summary
                    if s["stage"] == "discover"
                ),
                0,
            ),
            "total_files_filtered": next(
                (
                    s.get("total_filtered", 0)
                    for s in stages_summary
                    if s["stage"] == "filter"
                ),
                0,
            ),
            "total_files_downloaded": total_files_downloaded,
            "total_bytes_downloaded": total_bytes,
            "total_records_parsed": total_records_parsed,
            "total_records_failed": total_records_failed,
            "throughput_records_per_sec": round(throughput, 2),
            "stages_completed": sum(
                1 for s in stages_summary if s["status"] == "completed"
            ),
            "stages_partial": sum(
                1 for s in stages_summary if s["status"] == "partial"
            ),
            "stages_failed": sum(
                1 for s in stages_summary if s["status"] == "failed"
            ),
        }

        return ValidationReport(
            version=pipeline_result.version,
            start_date=pipeline_result.start_date,
            end_date=pipeline_result.end_date,
            overall_status=pipeline_result.overall_status,
            total_duration_seconds=pipeline_result.total_duration_seconds,
            stages=stages_summary,
            summary=summary,
            errors=all_errors,
        )

    def to_markdown(self, report: ValidationReport) -> str:
        lines: list[str] = []
        lines.append("# GDELT Pipeline Validation Report")
        lines.append("")
        lines.append(f"**Generated:** {report.generated_at}")
        lines.append(f"**Version:** {report.version}")
        lines.append(f"**Date Range:** {report.start_date or 'all'} → {report.end_date or 'all'}")
        lines.append(f"**Overall Status:** {report.overall_status}")
        lines.append(f"**Total Duration:** {report.summary['total_duration_formatted']}")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Files Discovered | {report.summary['total_files_discovered']} |")
        lines.append(f"| Files Filtered | {report.summary['total_files_filtered']} |")
        lines.append(f"| Files Downloaded | {report.summary['total_files_downloaded']} |")
        lines.append(f"| Total Bytes | {self._format_bytes(report.summary['total_bytes_downloaded'])} |")
        lines.append(f"| Records Parsed | {report.summary['total_records_parsed']} |")
        lines.append(f"| Records Failed | {report.summary['total_records_failed']} |")
        lines.append(f"| Throughput | {report.summary['throughput_records_per_sec']} rec/s |")
        lines.append(f"| Stages | {report.summary['stages_completed']} ok / {report.summary['stages_failed']} failed / {report.summary['stages_partial']} partial |")
        lines.append("")

        lines.append("## Stage Results")
        lines.append("")
        for s in report.stages:
            status_icon = "✅" if s["status"] == "completed" else "⚠️" if s["status"] == "partial" else "❌"
            lines.append(f"### {status_icon} {s['stage'].title()}")
            lines.append("")
            lines.append(f"- **Status:** {s['status']}")
            lines.append(f"- **Duration:** {self._format_duration(s.get('duration_seconds', 0))}")
            for k, v in s.items():
                if k in ("stage", "status", "duration_seconds", "error"):
                    continue
                lines.append(f"- **{k}:** `{v}`")
            if s.get("error"):
                lines.append(f"- **Error:** {s['error']}")
            lines.append("")

        if report.errors:
            lines.append("## Errors")
            lines.append("")
            for err in report.errors:
                lines.append(f"- {err}")
            lines.append("")

        lines.append("## Verification Steps")
        lines.append("")
        lines.append("To independently verify the downloaded data:")
        lines.append("")
        lines.append("1. **Check GDELT master file list:**")
        lines.append("   ```bash")
        lines.append("   curl -s http://data.gdeltproject.org/gdeltv2/masterfilelist.txt | head -20")
        lines.append("   ```")
        lines.append("2. **Verify a specific file checksum:**")
        lines.append("   ```bash")
        lines.append("   md5sum datasets/raw/gdelt/events/<version>/*.zip")
        lines.append("   ```")
        lines.append("3. **Compare with GDELT master list entry for the same file**")
        lines.append("4. **Inspect parsed CSV output:**")
        lines.append("   ```bash")
        lines.append("   head -5 datasets/processed/gdelt/events/<version>/*.csv")
        lines.append("   ```")
        lines.append("5. **Count records:**")
        lines.append("   ```bash")
        lines.append("   wc -l datasets/processed/gdelt/events/<version>/*.csv")
        lines.append("   ```")
        lines.append("")

        return "\n".join(lines)

    def to_json(self, report: ValidationReport) -> dict:
        return {
            "generated_at": report.generated_at,
            "version": report.version,
            "start_date": report.start_date,
            "end_date": report.end_date,
            "overall_status": report.overall_status,
            "total_duration_seconds": report.total_duration_seconds,
            "stages": report.stages,
            "summary": report.summary,
            "errors": report.errors,
        }

    def _format_duration(self, seconds: float) -> str:
        if seconds < 1:
            return f"{seconds * 1000:.0f}ms"
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"

    def _format_bytes(self, n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"
