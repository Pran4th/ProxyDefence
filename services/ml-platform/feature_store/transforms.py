from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, LabelEncoder


class FeatureTransform(ABC):
    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.Series:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    def fit(self, df: pd.DataFrame):
        pass


class IdentityTransform(FeatureTransform):
    def __init__(self, column: str, output_name: str | None = None):
        self._column = column
        self._output_name = output_name or column

    def transform(self, df: pd.DataFrame) -> pd.Series:
        return df[self._column]

    @property
    def name(self) -> str:
        return self._output_name


class AggregateTransform(FeatureTransform):
    def __init__(self, group_by: str, agg_func: str, column: str, output_name: str | None = None):
        self._group_by = group_by
        self._agg_func = agg_func
        self._column = column
        self._output_name = output_name or f"{column}_{agg_func}_by_{group_by}"
        self._mapping: dict | None = None

    def fit(self, df: pd.DataFrame):
        self._mapping = df.groupby(self._group_by)[self._column].agg(self._agg_func).to_dict()

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self._mapping:
            return df[self._group_by].map(self._mapping).fillna(0)
        return df.groupby(self._group_by)[self._column].transform(self._agg_func)

    @property
    def name(self) -> str:
        return self._output_name


class LagTransform(FeatureTransform):
    def __init__(self, column: str, periods: int = 1, time_column: str | None = None,
                 group_by: str | None = None, output_name: str | None = None):
        self._column = column
        self._periods = periods
        self._time_column = time_column
        self._group_by = group_by
        self._output_name = output_name or f"{column}_lag_{periods}"

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self._time_column:
            df = df.sort_values(self._time_column)
        if self._group_by:
            return df.groupby(self._group_by)[self._column].shift(self._periods).fillna(0)
        return df[self._column].shift(self._periods).fillna(0)

    @property
    def name(self) -> str:
        return self._output_name


class RatioTransform(FeatureTransform):
    def __init__(self, numerator: str, denominator: str, output_name: str | None = None,
                 fill_value: float = 0.0):
        self._numerator = numerator
        self._denominator = denominator
        self._output_name = output_name or f"{numerator}_over_{denominator}"
        self._fill = fill_value

    def transform(self, df: pd.DataFrame) -> pd.Series:
        result = df[self._numerator] / df[self._denominator].replace(0, np.nan)
        return result.fillna(self._fill)

    @property
    def name(self) -> str:
        return self._output_name


class GeospatialTransform(FeatureTransform):
    CHOKEPOINTS = {
        "hormuz": (26.5677, 56.0995),
        "malacca": (2.0, 102.0),
        "suez": (30.4833, 32.35),
        "bab_el_mandeb": (12.5833, 43.3333),
        "panama": (9.08, -79.68),
    }

    def __init__(self, lat_col: str = "latitude", lng_col: str = "longitude",
                 chokepoint: str = "hormuz", output_name: str | None = None):
        self._lat = lat_col
        self._lng = lng_col
        self._chokepoint = chokepoint
        cp = self.CHOKEPOINTS.get(chokepoint)
        if not cp:
            raise ValueError(f"Unknown chokepoint: {chokepoint}")
        self._cp_lat, self._cp_lng = cp
        self._output_name = output_name or f"distance_to_{chokepoint}_km"

    def transform(self, df: pd.DataFrame) -> pd.Series:
        lat1 = np.radians(df[self._lat].fillna(0))
        lon1 = np.radians(df[self._lng].fillna(0))
        lat2 = np.radians(self._cp_lat)
        lon2 = np.radians(self._cp_lng)
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        return pd.Series(6371 * c, name=self._output_name)

    @property
    def name(self) -> str:
        return self._output_name


class StandardScaleTransform(FeatureTransform):
    def __init__(self, column: str, output_name: str | None = None):
        self._column = column
        self._output_name = output_name or f"{column}_zscore"
        self._scaler = StandardScaler()
        self._fitted = False

    def fit(self, df: pd.DataFrame):
        values = df[[self._column]].fillna(0).values
        self._scaler.fit(values)
        self._fitted = True

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if not self._fitted:
            self.fit(df)
        values = df[[self._column]].fillna(0).values
        return pd.Series(self._scaler.transform(values).flatten(), index=df.index, name=self._output_name)

    @property
    def name(self) -> str:
        return self._output_name


class MinMaxScaleTransform(FeatureTransform):
    def __init__(self, column: str, output_name: str | None = None, feature_range: tuple = (0, 1)):
        self._column = column
        self._output_name = output_name or f"{column}_minmax"
        self._scaler = MinMaxScaler(feature_range=feature_range)
        self._fitted = False

    def fit(self, df: pd.DataFrame):
        values = df[[self._column]].fillna(0).values
        self._scaler.fit(values)
        self._fitted = True

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if not self._fitted:
            self.fit(df)
        values = df[[self._column]].fillna(0).values
        return pd.Series(self._scaler.transform(values).flatten(), index=df.index, name=self._output_name)

    @property
    def name(self) -> str:
        return self._output_name


class RobustScaleTransform(FeatureTransform):
    def __init__(self, column: str, output_name: str | None = None):
        self._column = column
        self._output_name = output_name or f"{column}_robust"
        self._scaler = RobustScaler()
        self._fitted = False

    def fit(self, df: pd.DataFrame):
        values = df[[self._column]].fillna(0).values
        self._scaler.fit(values)
        self._fitted = True

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if not self._fitted:
            self.fit(df)
        values = df[[self._column]].fillna(0).values
        return pd.Series(self._scaler.transform(values).flatten(), index=df.index, name=self._output_name)

    @property
    def name(self) -> str:
        return self._output_name


class OneHotTransform(FeatureTransform):
    def __init__(self, column: str, drop_first: bool = False, output_name: str | None = None):
        self._column = column
        self._drop_first = drop_first
        self._prefix = output_name or column
        self._categories: list | None = None

    def fit(self, df: pd.DataFrame):
        self._categories = sorted(df[self._column].dropna().unique())

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self._categories is None:
            self.fit(df)
        dummies = pd.get_dummies(df[self._column], prefix=self._prefix, drop_first=self._drop_first)
        for cat in self._categories:
            col = f"{self._prefix}_{cat}" if not self._drop_first or cat != self._categories[0] else f"{self._prefix}_{cat}"
            if col not in dummies.columns:
                dummies[col] = 0
        return dummies

    @property
    def name(self) -> str:
        return f"{self._prefix}_onehot"


class LabelEncodeTransform(FeatureTransform):
    def __init__(self, column: str, output_name: str | None = None):
        self._column = column
        self._output_name = output_name or f"{column}_encoded"
        self._encoder = LabelEncoder()
        self._fitted = False

    def fit(self, df: pd.DataFrame):
        self._encoder.fit(df[self._column].fillna("unknown").astype(str))
        self._fitted = True

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if not self._fitted:
            self.fit(df)
        values = df[self._column].fillna("unknown").astype(str)
        mapping = dict(zip(self._encoder.classes_, self._encoder.transform(self._encoder.classes_)))
        return pd.Series(values.map(mapping).fillna(-1).astype(int), name=self._output_name)

    @property
    def name(self) -> str:
        return self._output_name


class FrequencyEncodeTransform(FeatureTransform):
    def __init__(self, column: str, output_name: str | None = None):
        self._column = column
        self._output_name = output_name or f"{column}_freq"
        self._freq_map: dict | None = None

    def fit(self, df: pd.DataFrame):
        self._freq_map = df[self._column].value_counts(normalize=True).to_dict()

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self._freq_map is None:
            self.fit(df)
        return df[self._column].map(self._freq_map).fillna(0)

    @property
    def name(self) -> str:
        return self._output_name


class BinaryEncodeTransform(FeatureTransform):
    def __init__(self, column: str, threshold: float | None = None, output_name: str | None = None):
        self._column = column
        self._threshold = threshold
        self._output_name = output_name or f"{column}_binary"

    def fit(self, df: pd.DataFrame):
        if self._threshold is None:
            self._threshold = df[self._column].median()

    def transform(self, df: pd.DataFrame) -> pd.Series:
        return (df[self._column] > self._threshold).astype(int)

    @property
    def name(self) -> str:
        return self._output_name


class TemporalTransform(FeatureTransform):
    def __init__(self, column: str, features: list[str] | None = None, output_name: str | None = None):
        self._column = column
        self._features = features or ["hour", "dow", "month", "quarter", "year", "weekend"]
        self._prefix = output_name or column

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        col = pd.to_datetime(df[self._column])
        result = pd.DataFrame(index=df.index)
        feature_map = {
            "hour": ("hour", col.dt.hour),
            "dow": ("dow", col.dt.dayofweek),
            "month": ("month", col.dt.month),
            "quarter": ("quarter", col.dt.quarter),
            "year": ("year", col.dt.year),
            "weekend": ("weekend", (col.dt.dayofweek >= 5).astype(int)),
            "day": ("day", col.dt.day),
            "week": ("week", col.dt.isocalendar().week.astype(int)),
        }
        for f in self._features:
            if f in feature_map:
                suffix, values = feature_map[f]
                result[f"{self._prefix}_{suffix}"] = values
        return result

    @property
    def name(self) -> str:
        return self._prefix


class RollingWindowTransform(FeatureTransform):
    def __init__(self, column: str, window: int = 7, agg: str = "mean",
                 min_periods: int = 1, output_name: str | None = None):
        self._column = column
        self._window = window
        self._agg = agg
        self._min_periods = min_periods
        self._output_name = output_name or f"{column}_rolling_{window}_{agg}"

    def transform(self, df: pd.DataFrame) -> pd.Series:
        roll = df[self._column].rolling(window=self._window, min_periods=self._min_periods)
        result = getattr(roll, self._agg)()
        return result.bfill().fillna(0)

    @property
    def name(self) -> str:
        return self._output_name


class EWMATransform(FeatureTransform):
    def __init__(self, column: str, alpha: float = 0.3, output_name: str | None = None):
        self._column = column
        self._alpha = alpha
        self._output_name = output_name or f"{column}_ewma_{alpha}"

    def transform(self, df: pd.DataFrame) -> pd.Series:
        return df[self._column].ewm(alpha=self._alpha, adjust=False).mean().fillna(0)

    @property
    def name(self) -> str:
        return self._output_name


class InteractionTransform(FeatureTransform):
    def __init__(self, columns: list[str], operation: str = "multiply", output_name: str | None = None):
        self._columns = columns
        self._operation = operation
        self._output_name = output_name or f"interaction_{'_'.join(columns)}_{operation}"

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self._operation == "multiply":
            result = df[self._columns[0]]
            for c in self._columns[1:]:
                result = result * df[c]
        elif self._operation == "add":
            result = sum(df[c] for c in self._columns)
        elif self._operation == "subtract":
            result = df[self._columns[0]] - df[self._columns[1]]
        elif self._operation == "divide":
            result = df[self._columns[0]] / df[self._columns[1]].replace(0, np.nan)
        else:
            raise ValueError(f"Unknown interaction operation: {self._operation}")
        return result.fillna(0)

    @property
    def name(self) -> str:
        return self._output_name


class PolynomialTransform(FeatureTransform):
    def __init__(self, column: str, degree: int = 2, include_bias: bool = False,
                 output_name: str | None = None):
        self._column = column
        self._degree = degree
        self._include_bias = include_bias
        self._output_name = output_name or f"{column}_poly_{degree}"

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        col = df[self._column].fillna(0)
        result = pd.DataFrame(index=df.index)
        start = 0 if self._include_bias else 1
        for d in range(start, self._degree + 1):
            result[f"{self._column}_power_{d}"] = col ** d
        return result

    @property
    def name(self) -> str:
        return self._output_name


class TargetEncodeTransform(FeatureTransform):
    def __init__(self, column: str, target_column: str, output_name: str | None = None):
        self._column = column
        self._target = target_column
        self._output_name = output_name or f"{column}_target_encoded"
        self._mapping: dict | None = None

    def fit(self, df: pd.DataFrame):
        self._mapping = df.groupby(self._column)[self._target].mean().to_dict()

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self._mapping is None:
            self.fit(df)
        return df[self._column].map(self._mapping).fillna(df[self._target].mean() if self._target in df.columns else 0)

    @property
    def name(self) -> str:
        return self._output_name


TRANSFORM_REGISTRY: dict[str, type[FeatureTransform]] = {
    "identity": IdentityTransform,
    "standard_scale": StandardScaleTransform,
    "minmax": MinMaxScaleTransform,
    "robust_scale": RobustScaleTransform,
    "one_hot": OneHotTransform,
    "label_encode": LabelEncodeTransform,
    "frequency_encode": FrequencyEncodeTransform,
    "binary_encode": BinaryEncodeTransform,
    "temporal": TemporalTransform,
    "rolling_window": RollingWindowTransform,
    "ewma": EWMATransform,
    "lag": LagTransform,
    "ratio": RatioTransform,
    "interaction": InteractionTransform,
    "polynomial": PolynomialTransform,
    "target_encode": TargetEncodeTransform,
    "aggregate": AggregateTransform,
    "geospatial": GeospatialTransform,
}
