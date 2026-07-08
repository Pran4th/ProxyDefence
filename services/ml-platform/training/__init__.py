from training.models import (
    LogisticRegressionWrapper,
    DecisionTreeWrapper,
    RandomForestWrapper,
    XGBoostWrapper,
    MODEL_REGISTRY,
)
from training.trainer import ModelTrainer
from training.experiment import ExperimentTracker
from training.optimization import (
    GridSearchOptimizer,
    RandomSearchOptimizer,
)

try:
    from training.models import LightGBMWrapper  # type: ignore
    _HAS_LGBM = True
except ImportError:
    _HAS_LGBM = False

try:
    from training.optimization import OptunaOptimizer  # type: ignore
    _HAS_OPTUNA = True
except ImportError:
    _HAS_OPTUNA = False

__all__ = [
    "LogisticRegressionWrapper",
    "DecisionTreeWrapper",
    "RandomForestWrapper",
    "XGBoostWrapper",
    "MODEL_REGISTRY",
    "ModelTrainer",
    "ExperimentTracker",
    "GridSearchOptimizer",
    "RandomSearchOptimizer",
]
if _HAS_LGBM:
    __all__.append("LightGBMWrapper")
if _HAS_OPTUNA:
    __all__.append("OptunaOptimizer")
