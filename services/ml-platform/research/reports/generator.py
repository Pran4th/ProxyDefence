import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from config import REPORT_DIR
from research.reports.markdown import build_experiment_report
from research.reports.json_report import build_json_report
from research.reports.html_report import build_html_report

logger = get_logger(__name__)


class ReportFormat(Enum):
    MARKDOWN = "md"
    JSON = "json"
    HTML = "html"


class ReportGenerator:
    def __init__(self, output_dir: str | None = None):
        self._output_dir = Path(output_dir or REPORT_DIR)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, experiment_result: dict, format: ReportFormat = ReportFormat.MARKDOWN,
                       output_dir: str | None = None, template_vars: dict | None = None) -> str:
        output_path = Path(output_dir) if output_dir else self._output_dir
        output_path.mkdir(parents=True, exist_ok=True)
        name = experiment_result.get("experiment_name", experiment_result.get("name", "experiment"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if format == ReportFormat.MARKDOWN:
            content = await self.generate_markdown(experiment_result, template_vars)
            filename = f"{name}_{timestamp}.md"
        elif format == ReportFormat.JSON:
            content = await self.generate_json(experiment_result)
            filename = f"{name}_{timestamp}.json"
        elif format == ReportFormat.HTML:
            content = await self.generate_html(experiment_result, template_vars)
            filename = f"{name}_{timestamp}.html"
        else:
            raise ValueError(f"Unsupported format: {format}")
        path = output_path / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("report saved to %s", path)
        return str(path)

    async def generate_markdown(self, experiment_result: dict,
                                template_vars: dict | None = None) -> str:
        return build_experiment_report(experiment_result)

    async def generate_json(self, experiment_result: dict) -> str:
        return build_json_report(experiment_result)

    async def generate_html(self, experiment_result: dict,
                            template_vars: dict | None = None) -> str:
        return build_html_report(experiment_result)

    async def generate_all(self, experiment_result: dict, output_dir: str,
                           template_vars: dict | None = None) -> dict[str, str]:
        paths = {}
        for fmt in ReportFormat:
            path = await self.generate(experiment_result, fmt, output_dir, template_vars)
            paths[fmt.value] = path
        return paths
