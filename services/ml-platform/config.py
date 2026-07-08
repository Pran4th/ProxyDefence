"""ML Platform configuration.

PostgreSQL credentials come from :mod:`backend.shared.settings`; vars
specific to ML Platform (Energy Service URL, MLflow, DVC, dataset paths)
are parsed here.
"""

import os

from backend.shared.settings import settings

# PostgreSQL (re-exported for local db.py)
POSTGRES_PORT = settings.POSTGRES_PORT

# ML Platform specific
ENERGY_SERVICE_URL = os.getenv("ENERGY_SERVICE_URL", "http://energy-service:8000")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
DVC_REMOTE = os.getenv("DVC_REMOTE", "./data/dvc-store")

DATASET_DIR = os.getenv("DATASET_DIR", "./data/datasets")
ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "./data/artifacts")
REPORT_DIR = os.getenv("REPORT_DIR", "./data/reports")

DEFAULT_RANDOM_SEED = int(os.getenv("DEFAULT_RANDOM_SEED", "42"))
DEFAULT_TEST_SIZE = float(os.getenv("DEFAULT_TEST_SIZE", "0.2"))
DEFAULT_VAL_SIZE = float(os.getenv("DEFAULT_VAL_SIZE", "0.1"))
