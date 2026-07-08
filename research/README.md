# ML Research Lab

Research environment for the ProxyDefence Machine Learning Platform.

**Never runs inside Docker.** No production code. No FastAPI. Pure experimentation.

## Setup

```bash
pip install -r requirements-research.txt
```

This installs the full ML stack: mlflow, dvc, shap, optuna, lightgbm, jupyter, matplotlib, plotly, seaborn, statsmodels, prophet.

**Do NOT install `services/ml-platform/requirements.txt`** — that file is for production Docker only.

## Data

Fetch energy infrastructure data from the running Energy Service:

```bash
python datasets/fetch_data.py
```

This creates `datasets/energy_dataset.parquet` + `datasets/metadata.json`.

If the Energy Service is unavailable, synthetic data is generated automatically.

## Notebooks

| # | Notebook | Topic | Key Concepts |
|---|----------|-------|-------------|
| 1 | `01_EDA.ipynb` | Exploratory Data Analysis | Distributions, correlations, target analysis |
| 2 | `02_Data_Preprocessing.ipynb` | Data Cleaning | Missing values, outliers, data types |
| 3 | `03_Feature_Engineering.ipynb` | Feature Engineering | Encoding, scaling, aggregation, selection |
| 4 | `04_Baseline_Models.ipynb` | Logistic Regression & Decision Trees | Decision boundaries, entropy, bias-variance |
| 5 | `05_Model_Comparison.ipynb` | Ensemble Methods | RF, XGBoost, LightGBM, cross-validation |
| 6 | `06_Hyperparameter_Tuning.ipynb` | Hyperparameter Optimization | Grid/Random search, Optuna |
| 7 | `07_Model_Explainability.ipynb` | Explainability | SHAP, feature importance, PDP |
| 8 | `08_Final_Model_Export.ipynb` | Model Export | Final training, export, model card |

## Workflow

1. Fetch data (`python datasets/fetch_data.py`)
2. Open notebooks in order (01 → 08)
3. Each notebook teaches concepts, shows visualizations, and maps to production
4. Notebook 08 exports the final model to `models/` for production consumption

## ML Problem

**Predict infrastructure criticality** (low/medium/high/critical) from energy infrastructure features.

- **Type**: Multiclass classification
- **Data source**: Energy Service (or synthetic fallback)
- **Features**: Port throughput, oil field production, refinery capacity, location, organization type
- **Target**: `criticality_score` (0=low, 1=medium, 2=high, 3=critical)

## Production Mapping

Research notebooks discover the best model + parameters.

The production ML Platform (`services/ml-platform/`) reproduces and serves them.

```
Notebook 08 export → models/best_model.joblib → services/ml-platform/registry/
                                                   → Prediction API
```
