import sys
from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest

from research.explainability.engine import ExplainabilityEngine, ExplainabilityResult
from research.explainability.partial import PartialDependenceExplainer
from research.explainability.permutation import PermutationExplainer
from research.explainability.shap_explainer import ShapExplainer


class TestExplainabilityResult:
    def test_dataclass(self):
        result = ExplainabilityResult(
            method="permutation",
            feature_names=["f1", "f2"],
            importance_values={"f1": 0.8, "f2": 0.2},
            importance_ranked=[("f1", 0.8), ("f2", 0.2)],
        )
        assert result.method == "permutation"
        assert result.shap_values is None
        assert result.partial_dependence is None
        assert result.summary_text is None
        assert result.plot_paths == []
        assert result.duration_seconds == 0.0

    def test_with_all_fields(self):
        result = ExplainabilityResult(
            method="shap", feature_names=["a"], importance_values={"a": 1.0},
            importance_ranked=[("a", 1.0)], shap_values=[0.5],
            partial_dependence={"grid": [1]}, summary_text="summary",
            plot_paths=["plot.png"], duration_seconds=0.5,
        )
        assert result.shap_values == [0.5]
        assert result.summary_text == "summary"
        assert result.duration_seconds == 0.5


class TestExplainabilityEngine:
    def test_init(self):
        engine = ExplainabilityEngine()
        assert engine._shap_explainer is None
        assert engine._permutation_explainer is not None
        assert engine._partial_explainer is not None

    @pytest.mark.asyncio
    async def test_explain_permutation(self):
        engine = ExplainabilityEngine()
        model = MagicMock()
        model.predict = MagicMock(return_value=np.array([0, 1, 0]))
        X = np.random.randn(10, 3)
        y = np.random.randint(0, 2, 10)
        result = await engine.explain(model, X, y, method="permutation")
        assert isinstance(result, ExplainabilityResult)
        assert result.method == "permutation"
        assert len(result.feature_names) == 3

    @pytest.mark.asyncio
    async def test_explain_permutation_no_y_raises(self):
        engine = ExplainabilityEngine()
        with pytest.raises(ValueError, match="y is required"):
            await engine.explain(MagicMock(), np.array([[1]]), method="permutation")

    @pytest.mark.asyncio
    async def test_explain_feature_importance(self):
        engine = ExplainabilityEngine()
        model = MagicMock()
        model.feature_importances_ = np.array([0.6, 0.3, 0.1])
        X = np.random.randn(10, 3)
        result = await engine.explain(model, X, method="feature_importance")
        assert result.method == "feature_importance"
        assert len(result.importance_values) == 3

    @pytest.mark.asyncio
    async def test_explain_feature_importance_with_coef(self):
        engine = ExplainabilityEngine()
        model = MagicMock()
        model.coef_ = np.array([[0.5, -0.3, 0.2]])
        X = np.random.randn(10, 3)
        result = await engine.explain(model, X, method="feature_importance")
        assert len(result.importance_values) == 3

    @pytest.mark.asyncio
    async def test_explain_feature_importance_no_attrs(self):
        engine = ExplainabilityEngine()
        model = MagicMock(spec=[])
        X = np.random.randn(10, 3)
        result = await engine.explain(model, X, method="feature_importance")
        for v in result.importance_values.values():
            assert v == 0.0

    @pytest.mark.asyncio
    async def test_explain_unknown_method(self):
        engine = ExplainabilityEngine()
        with pytest.raises(ValueError, match="Unknown explanation method"):
            await engine.explain(MagicMock(), np.array([[1]]), method="unknown")

    @pytest.mark.asyncio
    async def test_explain_shap(self):
        engine = ExplainabilityEngine()
        model = MagicMock()
        model.feature_importances_ = np.array([0.6, 0.4])
        X = np.random.randn(10, 2)
        result = await engine.explain(model, X, method="shap")
        assert isinstance(result, ExplainabilityResult)
        assert result.method == "shap"

    @pytest.mark.asyncio
    async def test_explain_with_custom_feature_names(self):
        engine = ExplainabilityEngine()
        model = MagicMock()
        model.feature_importances_ = np.array([0.6, 0.4])
        X = np.random.randn(10, 2)
        result = await engine.explain(model, X, method="feature_importance", feature_names=["a", "b"])
        assert "a" in result.importance_values
        assert "b" in result.importance_values

    @pytest.mark.asyncio
    async def test_explain_partial_dependence(self):
        engine = ExplainabilityEngine()
        model = MagicMock()
        X = np.random.randn(20, 3)
        result = await engine.explain_partial_dependence(model, X, [0, 1], n_grid=10)
        assert "feature_labels" in result
        assert "grids" in result

    @pytest.mark.asyncio
    async def test_generate_summary_markdown(self):
        engine = ExplainabilityEngine()
        result = ExplainabilityResult(
            method="permutation", feature_names=["a", "b"],
            importance_values={"a": 0.8, "b": 0.2},
            importance_ranked=[("a", 0.8), ("b", 0.2)],
        )
        text = await engine.generate_summary(result, format="markdown")
        assert "Explainability Summary" in text
        assert "permutation" in text
        assert "a" in text

    @pytest.mark.asyncio
    async def test_generate_summary_plain(self):
        engine = ExplainabilityEngine()
        result = ExplainabilityResult(
            method="shap", feature_names=["a"], importance_values={"a": 1.0},
            importance_ranked=[("a", 1.0)],
        )
        text = await engine.generate_summary(result, format="text")
        assert "shap" in text

    @pytest.mark.asyncio
    async def test_generate_summary_from_dict(self):
        engine = ExplainabilityEngine()
        text = await engine.generate_summary(
            {"method": "test", "feature_names": ["x"], "importance_ranked": [("x", 1.0)]},
            format="text",
        )
        assert "test" in text


class TestShapExplainer:
    def test_init_no_shap(self):
        with patch("research.explainability.shap_explainer.ShapExplainer._try_import_shap"):
            explainer = ShapExplainer(MagicMock())
            explainer._shap_available = False
            assert explainer._model is not None

    def test_init_with_shap(self):
        explainer = ShapExplainer(MagicMock())
        assert explainer._model is not None

    @pytest.mark.asyncio
    async def test_compute_fallback(self):
        model = MagicMock()
        model.feature_importances_ = np.array([0.6, 0.4])
        explainer = ShapExplainer(model)
        explainer._shap_available = False
        X = np.random.randn(10, 2)
        result = await explainer.compute(X)
        assert result["shap_available"] is False
        assert len(result["importance_values"]) == 2

    @pytest.mark.asyncio
    async def test_compute_fallback_coef(self):
        model = MagicMock()
        model.coef_ = np.array([[0.5, -0.3]])
        explainer = ShapExplainer(model)
        explainer._shap_available = False
        X = np.random.randn(10, 2)
        result = await explainer.compute(X)
        assert result["shap_available"] is False

    @pytest.mark.asyncio
    async def test_compute_fallback_no_attrs(self):
        model = MagicMock(spec=[])
        explainer = ShapExplainer(model)
        explainer._shap_available = False
        X = np.random.randn(10, 2)
        result = await explainer.compute(X)
        for v in result["importance_values"].values():
            assert v == 0.0

    @pytest.mark.asyncio
    async def test_summary_plot_fallback(self, tmp_path):
        model = MagicMock()
        explainer = ShapExplainer(model)
        output = str(tmp_path / "plot.png")
        mpl = MagicMock()
        mpl.use = MagicMock()
        plt = MagicMock()
        mpl.pyplot = plt
        plt.subplots.return_value = (MagicMock(), MagicMock())
        with patch.dict("sys.modules", {"matplotlib": mpl, "matplotlib.pyplot": plt}):
            path = await explainer.summary_plot(None, np.array([[1]]), output)
        assert path == output

    @pytest.mark.asyncio
    async def test_bar_plot_fallback(self, tmp_path):
        model = MagicMock()
        explainer = ShapExplainer(model)
        output = str(tmp_path / "bar.png")
        mpl = MagicMock()
        mpl.use = MagicMock()
        plt = MagicMock()
        mpl.pyplot = plt
        plt.subplots.return_value = (MagicMock(), MagicMock())
        with patch.dict("sys.modules", {"matplotlib": mpl, "matplotlib.pyplot": plt}):
            path = await explainer.bar_plot(None, ["a", "b"], output)
        assert path == output

    @pytest.mark.asyncio
    async def test_waterfall_plot_fallback(self, tmp_path):
        model = MagicMock()
        explainer = ShapExplainer(model)
        output = str(tmp_path / "waterfall.png")
        mpl = MagicMock()
        mpl.use = MagicMock()
        plt = MagicMock()
        mpl.pyplot = plt
        plt.subplots.return_value = (MagicMock(), MagicMock())
        with patch.dict("sys.modules", {"matplotlib": mpl, "matplotlib.pyplot": plt}):
            path = await explainer.waterfall_plot(None, np.array([[1]]), 0, output)
        assert path == output


class TestPermutationExplainer:
    @pytest.mark.asyncio
    async def test_compute(self):
        model = MagicMock()
        model.predict = MagicMock(return_value=np.array([0, 1, 0, 1, 0]))
        X = np.random.randn(20, 3)
        y = np.random.randint(0, 2, 20)
        explainer = PermutationExplainer()
        with patch("research.explainability.permutation.sk_permutation_importance") as mock_imp:
            mock_result = MagicMock()
            mock_result.importances_mean = np.array([0.5, 0.3, 0.2])
            mock_result.importances_std = np.array([0.1, 0.1, 0.1])
            mock_result.importances = np.array([[0.5, 0.3, 0.2]])
            mock_imp.return_value = mock_result
            result = await explainer.compute(model, X, y, n_repeats=2)
        assert "importance_values" in result
        assert "importance_ranked" in result
        assert len(result["importance_values"]) == 3

    @pytest.mark.asyncio
    async def test_compute_with_feature_names(self):
        model = MagicMock()
        model.predict = MagicMock(return_value=np.array([0, 1]))
        X = np.random.randn(10, 2)
        y = np.random.randint(0, 2, 10)
        explainer = PermutationExplainer()
        with patch("research.explainability.permutation.sk_permutation_importance") as mock_imp:
            mock_result = MagicMock()
            mock_result.importances_mean = np.array([0.5, 0.3])
            mock_result.importances_std = np.array([0.1, 0.1])
            mock_result.importances = np.array([[0.5, 0.3]])
            mock_imp.return_value = mock_result
            result = await explainer.compute(model, X, y, feature_names=["a", "b"])
        assert "a" in result["importance_values"]

    @pytest.mark.asyncio
    async def test_compute_handles_exception(self):
        model = MagicMock()
        model.predict = MagicMock(side_effect=ValueError("fail"))
        X = np.random.randn(5, 2)
        y = np.random.randint(0, 2, 5)
        explainer = PermutationExplainer()
        with patch("research.explainability.permutation.sk_permutation_importance", side_effect=ValueError("fail")):
            result = await explainer.compute(model, X, y)
        assert "error" in result
        for v in result["importance_values"].values():
            assert v == 0.0


class TestPartialDependenceExplainer:
    @pytest.mark.asyncio
    async def test_compute(self):
        model = MagicMock()
        model.predict = MagicMock(return_value=np.array([1.0, 2.0]))
        X = np.random.randn(20, 3)
        explainer = PartialDependenceExplainer()
        result = await explainer.compute(model, X, [0, 1], n_grid=10)
        assert "feature_labels" in result
        assert "feature_indices" in result

    @pytest.mark.asyncio
    async def test_compute_with_string_features(self):
        model = MagicMock()
        X = np.random.randn(20, 3)
        explainer = PartialDependenceExplainer()
        result = await explainer.compute(model, X, ["feature_0", "feature_1"], n_grid=10)
        assert len(result["feature_labels"]) == 2

    @pytest.mark.asyncio
    async def test_compute_handles_exception(self):
        model = MagicMock()
        model.predict = MagicMock(side_effect=ValueError("fail"))
        X = np.random.randn(5, 2)
        explainer = PartialDependenceExplainer()
        result = await explainer.compute(model, X, [0], n_grid=5)
        assert "error" in result
