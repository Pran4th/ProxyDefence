import json
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from research.model_cards.generator import ModelCard, ModelCardGenerator


class TestModelCard:
    def test_dataclass_fields(self):
        card = ModelCard(
            model_name="test_model",
            model_version=1,
            model_type="xgboost",
            task="classification",
            dataset_name="energy_data",
            dataset_version=1,
        )
        assert card.model_name == "test_model"
        assert card.model_version == 1
        assert card.intended_use == ""
        assert card.owner == "system"
        assert card.license == "MIT"
        assert card.dependencies == []
        assert card.references == []

    def test_all_fields(self):
        card = ModelCard(
            model_name="m1", model_version=2, model_type="rf",
            task="regression", dataset_name="d1", dataset_version=1,
            intended_use="predict energy", limitations="limited data",
            ethical_considerations="none", evaluation_metrics={"acc": 0.9},
            training_params={"lr": 0.01}, training_date="2024-01-01",
            owner="admin", model_architecture="ensemble",
            feature_count=10, training_duration_seconds=60.0,
            inference_latency_ms=5.0, model_size_kb=100.0,
            bias_assessment="none", out_of_scope_usage="not for medical",
            dependencies=["sklearn"], license="Apache-2.0",
            references=["paper1"],
        )
        assert card.model_version == 2
        assert card.feature_count == 10
        assert card.license == "Apache-2.0"


class TestModelCardGenerator:
    def test_generate_minimal(self):
        gen = ModelCardGenerator()
        card = gen.generate({"model_name": "test", "model_type": "xgboost", "task": "classification"})
        assert isinstance(card, ModelCard)
        assert card.model_name == "test"
        assert card.model_architecture != ""

    def test_generate_with_experiment_result(self):
        gen = ModelCardGenerator()
        metadata = {"model_name": "m1", "model_type": "rf", "task": "regression"}
        exp_result = {"evaluation_metrics": {"r2": 0.9}, "owner": "researcher"}
        card = gen.generate(metadata, exp_result)
        assert card.evaluation_metrics["r2"] == 0.9
        assert card.owner == "researcher"

    def test_generate_merges_experiment_into_existing(self):
        gen = ModelCardGenerator()
        card = gen.generate(
            {"model_name": "m1", "model_type": "rf", "task": "cls", "owner": "existing"},
            {"owner": "override"},
        )
        assert card.owner == "existing"

    def test_generate_with_dataset_from_config(self):
        gen = ModelCardGenerator()
        card = gen.generate({
            "model_name": "m1", "model_type": "xgb", "task": "cls",
            "dataset": {"name": "energy", "version": 3},
        })
        assert card.dataset_name == "energy"
        assert card.dataset_version == 3

    def test_generate_fills_defaults_for_empty_fields(self):
        gen = ModelCardGenerator()
        card = gen.generate({"model_name": "m1", "model_type": "unknown", "task": "cls"})
        assert card.intended_use != ""
        assert card.limitations != ""
        assert card.ethical_considerations != ""
        assert card.bias_assessment != ""
        assert card.out_of_scope_usage != ""
        assert len(card.dependencies) > 0

    def test_fill_defaults_architecture(self):
        gen = ModelCardGenerator()
        card = ModelCard("m1", 1, "xgboost", "cls", "d1", 1)
        gen.fill_defaults(card)
        assert card.model_architecture != ""

    def test_fill_defaults_intended_use(self):
        gen = ModelCardGenerator()
        card = ModelCard("m1", 1, "rf", "cls", "d1", 1)
        gen.fill_defaults(card)
        assert "rf" in card.intended_use

    @pytest.mark.asyncio
    async def test_to_markdown(self):
        gen = ModelCardGenerator()
        card = ModelCard("m1", 1, "xgboost", "cls", "d1", 1,
                          intended_use="testing", evaluation_metrics={"acc": 0.95})
        md = await gen.to_markdown(card)
        assert "# Model Card: m1" in md
        assert "**Version:**" in md
        assert "testing" in md
        assert "acc" in md

    @pytest.mark.asyncio
    async def test_to_markdown_no_metrics(self):
        gen = ModelCardGenerator()
        card = ModelCard("m1", 1, "rf", "cls", "d1", 1)
        md = await gen.to_markdown(card)
        assert "No evaluation metrics recorded" in md

    @pytest.mark.asyncio
    async def test_to_markdown_no_training_params(self):
        gen = ModelCardGenerator()
        card = ModelCard("m1", 1, "rf", "cls", "d1", 1)
        md = await gen.to_markdown(card)
        assert "No training parameters recorded" in md

    @pytest.mark.asyncio
    async def test_to_json(self):
        gen = ModelCardGenerator()
        card = ModelCard("m1", 2, "rf", "regression", "d1", 1)
        js = await gen.to_json(card)
        data = json.loads(js)
        assert data["model_name"] == "m1"
        assert data["model_version"] == 2

    @pytest.mark.asyncio
    async def test_save_md(self, tmp_path):
        gen = ModelCardGenerator()
        card = ModelCard("Test Model", 1, "rf", "cls", "d1", 1)
        paths = await gen.save(card, str(tmp_path), formats=["md"])
        assert "md" in paths
        assert "test_model_v1_card.md" in paths["md"]

    @pytest.mark.asyncio
    async def test_save_json(self, tmp_path):
        gen = ModelCardGenerator()
        card = ModelCard("Test", 1, "rf", "cls", "d1", 1)
        paths = await gen.save(card, str(tmp_path), formats=["json"])
        assert "json" in paths

    @pytest.mark.asyncio
    async def test_save_both_formats(self, tmp_path):
        gen = ModelCardGenerator()
        card = ModelCard("Test", 1, "rf", "cls", "d1", 1)
        paths = await gen.save(card, str(tmp_path))
        assert "md" in paths
        assert "json" in paths

    def test_known_architectures(self):
        gen = ModelCardGenerator()
        card = gen.generate({"model_name": "m1", "model_type": "random_forest", "task": "cls"})
        assert "bootstrap aggregation" in card.model_architecture

    def test_unknown_architecture_default(self):
        gen = ModelCardGenerator()
        card = gen.generate({"model_name": "m1", "model_type": "custom", "task": "cls"})
        assert card.model_architecture == "No description available."

    def test_default_license(self):
        gen = ModelCardGenerator()
        card = gen.generate({"model_name": "m1", "model_type": "rf", "task": "cls"})
        assert card.license == "MIT"

    def test_generate_from_scratch_without_model_type(self):
        gen = ModelCardGenerator()
        card = gen.generate({"model_name": "m1", "task": "cls"})
        assert card.model_type == "unknown"
