import json
from unittest.mock import MagicMock, AsyncMock, patch, mock_open

import pytest

from research.notebooks.runner import DEFAULT_PIPELINE, NotebookPipeline, NotebookRunner


class TestNotebookPipeline:
    def test_dataclass(self):
        pipeline = NotebookPipeline(name="test", notebooks=["01_EDA.ipynb"])
        assert pipeline.name == "test"
        assert pipeline.notebooks == ["01_EDA.ipynb"]
        assert pipeline.config == {}
        assert pipeline.parameters == {}

    def test_default_pipeline(self):
        assert DEFAULT_PIPELINE.name == "research_pipeline"
        assert len(DEFAULT_PIPELINE.notebooks) == 7

    def test_default_pipeline_notebooks(self):
        expected = [
            "01_EDA.ipynb",
            "02_Cleaning.ipynb",
            "03_Feature_Engineering.ipynb",
            "04_Training.ipynb",
            "05_Evaluation.ipynb",
            "06_Explainability.ipynb",
            "07_Export.ipynb",
        ]
        assert DEFAULT_PIPELINE.notebooks == expected


class TestNotebookRunner:
    def test_init(self):
        runner = NotebookRunner()
        assert runner._output_dir is not None
        assert runner._papermill_available is not None

    def test_check_papermill_available(self):
        runner = NotebookRunner()
        runner._papermill_available = True
        assert runner._papermill_available is True

    def test_check_papermill_not_available(self):
        runner = NotebookRunner()
        with patch("builtins.__import__", side_effect=ImportError):
            assert runner._check_papermill() is False

    @pytest.mark.asyncio
    async def test_run_notebook_not_found(self):
        runner = NotebookRunner()
        result = await runner.run_notebook("/nonexistent/path.ipynb")
        assert result["status"] == "failed"
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_run_notebook_no_papermill(self):
        runner = NotebookRunner()
        runner._papermill_available = False
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", ".ipynb"),
            patch("research.notebooks.runner.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "success"
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc
            result = await runner.run_notebook("test.ipynb")
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_run_notebook_no_papermill_failure(self):
        runner = NotebookRunner()
        runner._papermill_available = False
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", ".ipynb"),
            patch("research.notebooks.runner.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stderr = "error"
            mock_run.return_value = mock_proc
            result = await runner.run_notebook("test.ipynb")
            assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_run_notebook_timeout(self):
        runner = NotebookRunner()
        runner._papermill_available = False
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", ".ipynb"),
            patch("research.notebooks.runner.subprocess.run", side_effect=TimeoutError),
        ):
            result = await runner.run_notebook("test.ipynb", timeout=1)
            assert result["status"] != "completed"

    @pytest.mark.asyncio
    async def test_get_notebook_metadata_not_found(self):
        runner = NotebookRunner()
        meta = await runner.get_notebook_metadata("/nonexistent.ipynb")
        assert "error" in meta

    @pytest.mark.asyncio
    async def test_get_notebook_metadata(self):
        runner = NotebookRunner()
        nb_content = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "name": "python3"},
                "language_info": {"name": "python"},
            },
            "cells": [
                {"cell_type": "code", "source": ["print(1)"], "metadata": {}},
                {"cell_type": "markdown", "source": ["# Title"], "metadata": {}},
                {"cell_type": "code", "source": ["x = 1"], "metadata": {"tags": ["parameters"]}},
            ],
        }
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(nb_content))),
        ):
            meta = await runner.get_notebook_metadata("test.ipynb")
            assert meta["total_cells"] == 3
            assert meta["code_cells"] == 2
            assert meta["markdown_cells"] == 1
            assert "parameters" in meta["tags"]

    @pytest.mark.asyncio
    async def test_validate_notebook_not_found(self):
        runner = NotebookRunner()
        errors = await runner.validate_notebook("/nonexistent.ipynb")
        assert "File not found" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_notebook_wrong_extension(self, tmp_path):
        runner = NotebookRunner()
        nb_file = tmp_path / "test.txt"
        nb_file.write_text("{}")
        errors = await runner.validate_notebook(str(nb_file))
        assert "Not a .ipynb file" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_notebook_invalid_json(self):
        runner = NotebookRunner()
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", ".ipynb"),
            patch("builtins.open", mock_open(read_data="invalid json")),
        ):
            errors = await runner.validate_notebook("test.ipynb")
            assert any("Invalid JSON" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_notebook_missing_cells(self):
        runner = NotebookRunner()
        nb = {"nbformat": 4}
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", ".ipynb"),
            patch("builtins.open", mock_open(read_data=json.dumps(nb))),
        ):
            errors = await runner.validate_notebook("test.ipynb")
            assert any("Missing 'cells' key" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_notebook_empty_cells(self, tmp_path):
        runner = NotebookRunner()
        nb_file = tmp_path / "test.ipynb"
        nb_file.write_text(json.dumps({"cells": [], "nbformat": 4}))
        errors = await runner.validate_notebook(str(nb_file))
        assert any("no cells" in e.lower() for e in errors)

    @pytest.mark.asyncio
    async def test_validate_notebook_invalid_cell_type(self):
        runner = NotebookRunner()
        nb = {"cells": [{"cell_type": "invalid", "source": ["x"]}], "nbformat": 4}
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", ".ipynb"),
            patch("builtins.open", mock_open(read_data=json.dumps(nb))),
        ):
            errors = await runner.validate_notebook("test.ipynb")
            assert any("invalid cell_type" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_notebook_missing_source(self):
        runner = NotebookRunner()
        nb = {"cells": [{"cell_type": "code"}], "nbformat": 4}
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", ".ipynb"),
            patch("builtins.open", mock_open(read_data=json.dumps(nb))),
        ):
            errors = await runner.validate_notebook("test.ipynb")
            assert any("missing 'source'" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_notebook_clean(self):
        runner = NotebookRunner()
        nb = {
            "cells": [
                {"cell_type": "code", "source": ["print(1)"]},
                {"cell_type": "markdown", "source": ["# Title"]},
            ],
            "nbformat": 4,
        }
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", ".ipynb"),
            patch("builtins.open", mock_open(read_data=json.dumps(nb))),
        ):
            errors = await runner.validate_notebook("test.ipynb")
            assert errors == []

    @pytest.mark.asyncio
    async def test_list_notebooks_empty_dir(self):
        runner = NotebookRunner()
        notebooks = await runner.list_notebooks("/nonexistent")
        assert notebooks == []

    @pytest.mark.asyncio
    async def test_run_pipeline_stops_on_failure(self):
        runner = NotebookRunner()
        with patch.object(runner, "run_notebook", return_value={"status": "failed", "error": "err"}):
            results = await runner.run_pipeline(DEFAULT_PIPELINE)
            assert len(results) >= 1
            assert results[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_run_pipeline_parallel(self):
        runner = NotebookRunner()
        with patch.object(runner, "run_notebook", return_value={"status": "completed", "duration": 0.1}):
            results = await runner.run_pipeline_parallel(DEFAULT_PIPELINE, max_parallel=2)
            assert len(results) == 7

    @pytest.mark.asyncio
    async def test_run_pipeline_parallel_with_exceptions(self):
        runner = NotebookRunner()
        with patch.object(runner, "run_notebook", side_effect=ValueError("crash")):
            results = await runner.run_pipeline_parallel(DEFAULT_PIPELINE, max_parallel=2)
            assert len(results) == 7
            assert any(r["status"] == "failed" for r in results)

    @pytest.mark.asyncio
    async def test_list_notebooks(self, tmp_path):
        runner = NotebookRunner()
        nb_dir = tmp_path / "notebooks"
        nb_dir.mkdir()
        nb_file = nb_dir / "01_test.ipynb"
        nb_content = {
            "nbformat": 4,
            "metadata": {},
            "cells": [
                {"cell_type": "code", "source": ["x = 1"], "metadata": {}},
            ],
        }
        nb_file.write_text(json.dumps(nb_content))
        notebooks = await runner.list_notebooks(str(nb_dir))
        assert len(notebooks) == 1
        assert notebooks[0]["name"] == "01_test.ipynb"
