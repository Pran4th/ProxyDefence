import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class NotebookPipeline:
    name: str
    notebooks: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)


DEFAULT_PIPELINE = NotebookPipeline(
    name="research_pipeline",
    notebooks=[
        "01_EDA.ipynb",
        "02_Cleaning.ipynb",
        "03_Feature_Engineering.ipynb",
        "04_Training.ipynb",
        "05_Evaluation.ipynb",
        "06_Explainability.ipynb",
        "07_Export.ipynb",
    ],
    config={"description": "Standard research pipeline"},
    parameters={},
)


class NotebookRunner:
    def __init__(self, output_dir: str = "./research/notebooks/output"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._papermill_available = self._check_papermill()

    def _check_papermill(self) -> bool:
        try:
            import papermill
            return True
        except ImportError:
            return False

    async def run_notebook(self, notebook_path: str, parameters: dict | None = None,
                           output_path: str | None = None, timeout: int = 3600) -> dict:
        nb_path = Path(notebook_path)
        if not nb_path.exists():
            return {"status": "failed", "error": f"Notebook not found: {notebook_path}", "duration": 0}
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self._output_dir / f"{nb_path.stem}_{timestamp}.ipynb")
        start = time.time()
        result = {"status": "completed", "outputs": [], "errors": [], "duration": 0, "output_path": output_path}
        try:
            if self._papermill_available:
                import papermill as pm
                pm.execute_notebook(
                    str(nb_path),
                    output_path,
                    parameters=parameters or {},
                    kernel_name="python3",
                    progress_bar=False,
                    report_mode=True,
                )
                result["output_path"] = output_path
            else:
                env = os.environ.copy()
                if parameters:
                    env["NOTEBOOK_PARAMETERS"] = json.dumps(parameters)
                proc = subprocess.run(
                    [sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook",
                     "--execute", "--ExecutePreprocessor.timeout", str(timeout),
                     "--output", output_path, str(nb_path)],
                    capture_output=True, text=True, timeout=timeout,
                )
                if proc.returncode != 0:
                    result["status"] = "failed"
                    result["errors"] = [proc.stderr]
                result["outputs"] = [proc.stdout] if proc.stdout else []
            duration = time.time() - start
            result["duration"] = round(duration, 2)
            logger.info("notebook %s completed in %.2fs", notebook_path, duration)
        except subprocess.TimeoutExpired:
            result["status"] = "failed"
            result["error"] = f"Notebook execution timed out after {timeout}s"
            result["duration"] = round(time.time() - start, 2)
        except Exception as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
            result["duration"] = round(time.time() - start, 2)
            logger.error("notebook %s failed: %s", notebook_path, exc)
        return result

    async def run_pipeline(self, pipeline: NotebookPipeline) -> list[dict]:
        results = []
        shared_params = dict(pipeline.parameters)
        for nb_rel in pipeline.notebooks:
            nb_path = nb_rel if os.path.isabs(nb_rel) else str(Path(pipeline.config.get("notebook_dir", "./research/notebooks")) / nb_rel)
            logger.info("pipeline %s: running %s", pipeline.name, nb_path)
            result = await self.run_notebook(nb_path, parameters=shared_params)
            results.append({"notebook": nb_rel, **result})
            if result["status"] == "failed":
                logger.warning("pipeline %s stopped at %s due to failure", pipeline.name, nb_rel)
                break
            if result.get("outputs"):
                shared_params["previous_output"] = result["outputs"]
        return results

    async def run_pipeline_parallel(self, pipeline: NotebookPipeline, max_parallel: int = 2) -> list[dict]:
        import asyncio
        semaphore = asyncio.Semaphore(max_parallel)
        async def _run_with_semaphore(nb_rel: str) -> dict:
            async with semaphore:
                nb_path = nb_rel if os.path.isabs(nb_rel) else str(Path(pipeline.config.get("notebook_dir", "./research/notebooks")) / nb_rel)
                return {"notebook": nb_rel, **await self.run_notebook(nb_path, parameters=pipeline.parameters)}
        tasks = [_run_with_semaphore(nb) for nb in pipeline.notebooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        final = []
        for r in results:
            if isinstance(r, Exception):
                final.append({"notebook": "unknown", "status": "failed", "error": str(r), "duration": 0})
            else:
                final.append(r)
        return final

    async def get_notebook_metadata(self, notebook_path: str) -> dict:
        nb_path = Path(notebook_path)
        if not nb_path.exists():
            return {"error": f"Notebook not found: {notebook_path}"}
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        metadata = nb.get("metadata", {})
        cells = nb.get("cells", [])
        info = {
            "path": str(nb_path),
            "nbformat": nb.get("nbformat"),
            "nbformat_minor": nb.get("nbformat_minor"),
            "kernel": metadata.get("kernelspec", {}),
            "language": metadata.get("language_info", {}).get("name"),
            "total_cells": len(cells),
            "code_cells": sum(1 for c in cells if c.get("cell_type") == "code"),
            "markdown_cells": sum(1 for c in cells if c.get("cell_type") == "markdown"),
            "tags": [],
            "parameters": [],
        }
        for cell in cells:
            cell_tags = cell.get("metadata", {}).get("tags", [])
            info["tags"].extend(cell_tags)
            if "parameters" in cell_tags:
                src = cell.get("source", "")
                if isinstance(src, list):
                    src = "".join(src)
                for line in src.split("\n"):
                    if "=" in line and not line.strip().startswith("#"):
                        info["parameters"].append(line.strip())
        info["tags"] = list(set(info["tags"]))
        return info

    async def validate_notebook(self, notebook_path: str) -> list[str]:
        errors = []
        nb_path = Path(notebook_path)
        if not nb_path.exists():
            return [f"File not found: {notebook_path}"]
        if nb_path.suffix != ".ipynb":
            return [f"Not a .ipynb file: {notebook_path}"]
        try:
            with open(nb_path, "r", encoding="utf-8") as f:
                nb = json.load(f)
        except json.JSONDecodeError as e:
            return [f"Invalid JSON: {e}"]
        if "cells" not in nb:
            errors.append("Missing 'cells' key")
        if "nbformat" not in nb:
            errors.append("Missing 'nbformat' key")
        cells = nb.get("cells", [])
        if not cells:
            errors.append("Notebook has no cells")
        for i, cell in enumerate(cells):
            if "cell_type" not in cell:
                errors.append(f"Cell {i}: missing 'cell_type'")
            elif cell["cell_type"] not in ("code", "markdown", "raw"):
                errors.append(f"Cell {i}: invalid cell_type '{cell.get('cell_type')}'")
            if "source" not in cell:
                errors.append(f"Cell {i}: missing 'source'")
        return errors

    async def list_notebooks(self, directory: str = "./research/notebooks") -> list[dict]:
        nb_dir = Path(directory)
        if not nb_dir.exists():
            return []
        notebooks = []
        for fpath in sorted(nb_dir.glob("*.ipynb")):
            meta = await self.get_notebook_metadata(str(fpath))
            notebooks.append({
                "name": fpath.name,
                "path": str(fpath),
                "size": fpath.stat().st_size,
                "cells": meta.get("total_cells", 0),
                "code_cells": meta.get("code_cells", 0),
                "markdown_cells": meta.get("markdown_cells", 0),
                "tags": meta.get("tags", []),
                "parameters": meta.get("parameters", []),
            })
        return notebooks
