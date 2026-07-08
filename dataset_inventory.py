import pandas as pd
from pathlib import Path

files = [
    "datasets/raw/sdn.csv",
    "datasets/raw/ports.csv",
    "datasets/raw/global_energy_2025.csv",
    "datasets/raw/global_energy_2026.csv"
]

for f in files:
    print("="*80)
    print(f)
    try:
        df = pd.read_csv(f, low_memory=False)
        print(f"Rows: {len(df):,}")
        print(f"Columns: {len(df.columns)}")
        print("\nColumns:")
        print(list(df.columns))
        print("\nFirst 3 rows:")
        print(df.head(3))
        print("\nMissing values:")
        print(df.isnull().sum()[df.isnull().sum() > 0])
    except Exception as e:
        print("ERROR:", e)