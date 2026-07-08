import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    StandardScaler,
    MinMaxScaler,
    RobustScaler,
    OneHotEncoder,
    LabelEncoder,
    FunctionTransformer,
)


def build_numerical_pipeline(strategy: str = "mean",
                             scaling: str = "standard") -> Pipeline:
    steps = [("imputer", SimpleImputer(strategy=strategy))]
    if scaling == "standard":
        steps.append(("scaler", StandardScaler()))
    elif scaling == "minmax":
        steps.append(("scaler", MinMaxScaler()))
    elif scaling == "robust":
        steps.append(("scaler", RobustScaler()))
    return Pipeline(steps)


def build_categorical_pipeline(handle_unknown: str = "ignore") -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("encoder", OneHotEncoder(handle_unknown=handle_unknown, sparse_output=False)),
    ])


def build_boolean_pipeline(strategy: str = "most_frequent") -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy=strategy)),
    ])


def _extract_datetime_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in result.columns:
        if pd.api.types.is_datetime64_any_dtype(result[col]):
            dt = pd.to_datetime(result[col])
            result[f"{col}_year"] = dt.dt.year
            result[f"{col}_month"] = dt.dt.month
            result[f"{col}_day"] = dt.dt.day
            result[f"{col}_dayofweek"] = dt.dt.dayofweek
            result[f"{col}_hour"] = dt.dt.hour
            result.drop(columns=[col], inplace=True)
    return result


def build_timestamp_pipeline() -> Pipeline:
    return Pipeline([
        ("extract", FunctionTransformer(_extract_datetime_features, validate=False)),
    ])


def build_full_preprocessing_pipeline(
    numerical_cols: list[str] | None = None,
    categorical_cols: list[str] | None = None,
    boolean_cols: list[str] | None = None,
    timestamp_cols: list[str] | None = None,
    numerical_strategy: str = "mean",
    scaling: str = "standard",
) -> ColumnTransformer:
    transformers = []

    if numerical_cols:
        transformers.append(
            ("numerical", build_numerical_pipeline(numerical_strategy, scaling), numerical_cols)
        )
    if categorical_cols:
        transformers.append(
            ("categorical", build_categorical_pipeline(), categorical_cols)
        )
    if boolean_cols:
        transformers.append(
            ("boolean", build_boolean_pipeline(), boolean_cols)
        )
    if timestamp_cols:
        transformers.append(
            ("timestamp", build_timestamp_pipeline(), timestamp_cols)
        )

    return ColumnTransformer(transformers, remainder="drop")
