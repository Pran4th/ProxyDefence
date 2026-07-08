import pytest

from feature_store.registry import FeatureRegistry, VALID_FEATURE_TYPES
from feature_store.transforms import (
    IdentityTransform,
    AggregateTransform,
    LagTransform,
    RatioTransform,
    GeospatialTransform,
)


class TestFeatureRegistry:
    def test_valid_feature_types(self):
        assert "numerical" in VALID_FEATURE_TYPES
        assert "categorical" in VALID_FEATURE_TYPES
        assert "graph_placeholder" in VALID_FEATURE_TYPES
        assert len(VALID_FEATURE_TYPES) > 10

    def test_create_raises_on_invalid_type(self):
        import asyncio
        with pytest.raises(ValueError, match="Invalid feature_type"):
            asyncio.run(FeatureRegistry().create("test", "invalid_type"))

    def test_can_instantiate(self):
        assert FeatureRegistry()


class TestTransforms:
    def test_identity(self):
        import pandas as pd
        df = pd.DataFrame({"x": [1, 2, 3]})
        t = IdentityTransform("x")
        result = t.transform(df)
        assert list(result) == [1, 2, 3]
        assert t.name == "x"

    def test_lag(self):
        import pandas as pd
        df = pd.DataFrame({"value": [1, 2, 3, 4]})
        t = LagTransform("value", periods=1)
        result = t.transform(df)
        assert list(result) == [0, 1, 2, 3]

    def test_ratio(self):
        import pandas as pd
        df = pd.DataFrame({"a": [10, 20], "b": [2, 5]})
        t = RatioTransform("a", "b")
        result = t.transform(df)
        assert list(result) == [5.0, 4.0]

    def test_geospatial(self):
        import pandas as pd
        df = pd.DataFrame({"latitude": [26.0], "longitude": [56.0]})
        t = GeospatialTransform("latitude", "longitude", "hormuz")
        result = t.transform(df)
        assert result.iloc[0] < 100
        assert t.name == "distance_to_hormuz_km"

    def test_geospatial_invalid_chokepoint(self):
        with pytest.raises(ValueError, match="Unknown chokepoint"):
            GeospatialTransform("lat", "lng", "nonexistent")
