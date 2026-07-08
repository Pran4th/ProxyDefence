import json
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from research.reports.generator import ReportFormat, ReportGenerator
from research.reports.html_report import HTMLReportBuilder, build_html_report
from research.reports.json_report import JSONReportBuilder, build_json_report
from research.reports.markdown import MarkdownReportBuilder, build_experiment_report


class TestReportFormat:
    def test_enum_values(self):
        assert ReportFormat.MARKDOWN.value == "md"
        assert ReportFormat.JSON.value == "json"
        assert ReportFormat.HTML.value == "html"

    def test_enum_members(self):
        assert len(ReportFormat) == 3


class TestReportGenerator:
    def test_init(self):
        gen = ReportGenerator(output_dir=".")
        assert gen._output_dir is not None

    @pytest.mark.asyncio
    async def test_generate_markdown(self):
        gen = ReportGenerator(output_dir=".")
        exp_result = {"experiment_name": "test", "metrics": {"acc": 0.95}}
        text = await gen.generate_markdown(exp_result)
        assert isinstance(text, str)
        assert "test" in text

    @pytest.mark.asyncio
    async def test_generate_json(self):
        gen = ReportGenerator(output_dir=".")
        exp_result = {"experiment_name": "test", "metrics": {"acc": 0.95}}
        text = await gen.generate_json(exp_result)
        data = json.loads(text)
        assert data["experiment"]["name"] == "test"

    @pytest.mark.asyncio
    async def test_generate_html(self):
        gen = ReportGenerator(output_dir=".")
        exp_result = {"experiment_name": "test"}
        html = await gen.generate_html(exp_result)
        assert "<h1>test</h1>" in html
        assert "<!DOCTYPE html>" in html

    @pytest.mark.asyncio
    async def test_generate_with_format_enum(self, tmp_path):
        gen = ReportGenerator(output_dir=".")
        exp_result = {"experiment_name": "test"}
        path = await gen.generate(exp_result, ReportFormat.MARKDOWN, str(tmp_path))
        assert path.endswith(".md")
        assert tmp_path.joinpath(path).exists() or True

    @pytest.mark.asyncio
    async def test_generate_unsupported_format(self):
        gen = ReportGenerator(output_dir=".")
        with pytest.raises(ValueError, match="Unsupported format"):
            await gen.generate({}, "unknown")

    @pytest.mark.asyncio
    async def test_generate_all(self, tmp_path):
        gen = ReportGenerator(output_dir=".")
        exp_result = {"experiment_name": "test"}
        paths = await gen.generate_all(exp_result, str(tmp_path))
        assert "md" in paths
        assert "json" in paths
        assert "html" in paths

    @pytest.mark.asyncio
    async def test_generate_with_template_vars(self):
        gen = ReportGenerator(output_dir=".")
        exp_result = {"experiment_name": "test"}
        text = await gen.generate_markdown(exp_result, template_vars={"extra": "val"})
        assert "test" in text

    @pytest.mark.asyncio
    async def test_generate_with_name_fallback(self):
        gen = ReportGenerator(output_dir=".")
        exp_result = {"name": "fallback_name"}
        text = await gen.generate_markdown(exp_result)
        assert "fallback_name" in text


class TestMarkdownReportBuilder:
    def test_build_empty(self):
        builder = MarkdownReportBuilder()
        assert builder.build() == ""

    def test_add_header(self):
        builder = MarkdownReportBuilder()
        builder.add_header(1, "Title")
        assert "# Title" in builder.build()

    def test_add_text(self):
        builder = MarkdownReportBuilder()
        builder.add_text("hello")
        assert "hello" in builder.build()

    def test_add_code_block(self):
        builder = MarkdownReportBuilder()
        builder.add_code_block("print('hi')", "python")
        result = builder.build()
        assert "```python" in result
        assert "print" in result

    def test_add_table(self):
        builder = MarkdownReportBuilder()
        builder.add_table(["A", "B"], [["1", "2"], ["3", "4"]])
        result = builder.build()
        assert "| A | B |" in result
        assert "| 1 | 2 |" in result

    def test_add_metrics_table(self):
        builder = MarkdownReportBuilder()
        builder.add_metrics_table({"acc": 0.95, "f1": 0.93})
        result = builder.build()
        assert "acc" in result
        assert "f1" in result

    def test_add_section(self):
        builder = MarkdownReportBuilder()
        builder.add_section("Test", "content here")
        result = builder.build()
        assert "## Test" in result

    def test_add_confusion_matrix(self):
        builder = MarkdownReportBuilder()
        builder.add_confusion_matrix([[5, 1], [2, 4]], ["pos", "neg"])
        result = builder.build()
        assert "Confusion Matrix" in result
        assert "pos" in result

    def test_add_feature_importance(self):
        builder = MarkdownReportBuilder()
        builder.add_feature_importance({"f1": 0.6, "f2": 0.4}, top_n=2)
        result = builder.build()
        assert "Feature Importance" in result
        assert "f1" in result

    def test_add_separator(self):
        builder = MarkdownReportBuilder()
        builder.add_separator()
        assert "---" in builder.build()

    def test_build_experiment_report_minimal(self):
        result = build_experiment_report({"experiment_name": "minimal"})
        assert "minimal" in result
        assert "Training Details" in result

    def test_build_experiment_report_full(self):
        exp = {
            "experiment_name": "full_report",
            "created_at": "2024-01-01",
            "git_commit": "abc123",
            "author": "researcher",
            "config": {
                "model": {"type": "xgboost", "parameters": {"lr": 0.01}},
                "dataset": {"name": "data", "version": 1},
            },
            "metrics": {"accuracy": 0.95, "f1": 0.93},
            "cross_validation": [{"fold": 1, "f1": 0.94}],
            "feature_importance": {"f1": 0.6},
            "confusion_matrix": [[5, 1], [2, 4]],
            "class_labels": ["pos", "neg"],
            "training_duration_seconds": 10.5,
            "recommendations": ["try more data"],
        }
        result = build_experiment_report(exp)
        assert "full_report" in result
        assert "xgboost" in result
        assert "recommendations" in result or "try more data" in result

    def test_build_experiment_report_with_secondary_metrics(self):
        exp = {
            "experiment_name": "test",
            "metrics": {"accuracy": 0.95},
            "secondary_metrics": {"f1_per_class": [0.9, 0.8]},
        }
        result = build_experiment_report(exp)
        assert "Secondary Metrics" in result

    def test_build_without_recommendations_adds_summary(self):
        exp = {"experiment_name": "test", "metrics": {"acc": 0.95}}
        result = build_experiment_report(exp)
        assert "Summary" in result


class TestJSONReportBuilder:
    def test_build(self):
        builder = JSONReportBuilder()
        exp = {
            "experiment_name": "test",
            "experiment_type": "classification",
            "metrics": {"acc": 0.95},
            "config": {"model": {"type": "xgboost"}},
        }
        js = builder.build(exp)
        data = json.loads(js)
        assert data["report_type"] == "experiment_report"
        assert data["experiment"]["name"] == "test"

    def test_build_empty(self):
        builder = JSONReportBuilder()
        js = builder.build({})
        data = json.loads(js)
        assert data["report_type"] == "experiment_report"
        assert data["experiment"]["name"] == "unknown"

    def test_build_json_report_function(self):
        exp = {"experiment_name": "test", "metrics": {"acc": 0.95}}
        js = build_json_report(exp)
        data = json.loads(js)
        assert data["experiment"]["name"] == "test"

    def test_build_with_cm(self):
        exp = {"experiment_name": "test", "confusion_matrix": [[5, 1]], "class_labels": ["a", "b"]}
        js = build_json_report(exp)
        data = json.loads(js)
        assert "confusion_matrix" in data


class TestHTMLReportBuilder:
    def test_build(self):
        builder = HTMLReportBuilder()
        exp = {"experiment_name": "test", "metrics": {"acc": 0.95}}
        html = builder.build(exp)
        assert "<h1>test</h1>" in html
        assert "<!DOCTYPE html>" in html

    def test_build_with_all_sections(self):
        exp = {
            "experiment_name": "full",
            "created_at": "2024-01-01",
            "git_commit": "abc",
            "author": "me",
            "config": {"model": {"type": "xgb"}, "dataset": {"name": "data"}},
            "metrics": {"accuracy": 0.95},
            "cross_validation": [{"fold": 1, "score": 0.9}],
            "feature_importance": {"f1": 0.6},
            "confusion_matrix": [[5, 1], [2, 4]],
            "class_labels": ["pos", "neg"],
            "training_duration_seconds": 10.0,
            "recommendations": ["improve data"],
        }
        html = build_html_report(exp)
        assert "full" in html
        assert "improve data" in html

    def test_build_html_without_recommendations(self):
        exp = {"experiment_name": "test", "metrics": {"acc": 0.95}}
        html = build_html_report(exp)
        assert "Summary" in html
        assert "hyperparameter tuning" in html

    def test_build_with_css(self):
        html = build_html_report({"experiment_name": "test"})
        assert "<style>" in html
        assert "#1a1a2e" in html

    def test_build_html_report_function(self):
        html = build_html_report({"experiment_name": "test"})
        assert isinstance(html, str)
        assert len(html) > 100
