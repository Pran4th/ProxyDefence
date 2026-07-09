"""Directly extracts+parses all downloaded GDELT GKG zips using GKGParser,
bypassing the CLI's slower events->mentions->gkg sequential loop (we only
need GKG here, for topic-classifier training).

Run from services/ml-platform/:
    .venv/Scripts/python.exe scripts/parse_gkg_direct.py
"""
from __future__ import annotations

import asyncio
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_acquisition.parser.sources.gdelt import GKGParser  # noqa: E402
from data_acquisition.parser.base import ParseConfig  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "datasets" / "raw" / "gdelt" / "gkg" / "20260707"
OUT_DIR = REPO_ROOT / "datasets" / "processed" / "gdelt-gkg-merged"


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zips = sorted(RAW_DIR.glob("*.zip"))
    print(f"found {len(zips)} GKG zips")

    parser = GKGParser()
    total_parsed, total_failed = 0, 0
    csv_files = []

    for i, zpath in enumerate(zips):
        extract_dir = RAW_DIR / "extracted"
        extract_dir.mkdir(exist_ok=True)
        try:
            with zipfile.ZipFile(zpath, "r") as z:
                names = z.namelist()
                z.extractall(extract_dir)
        except zipfile.BadZipFile:
            print(f"  [skip] {zpath.name}: bad zip")
            continue

        for name in names:
            csv_path = extract_dir / name
            if not csv_path.exists():
                continue
            out_path = OUT_DIR / f"{csv_path.stem}.parsed.csv"
            config = ParseConfig(source="gdelt-gkg", version="20260707", input_path=csv_path, output_path=out_path)
            try:
                result = await parser.parse(config)
                total_parsed += result.records_parsed
                total_failed += result.records_failed
                csv_files.append(out_path)
            except Exception as e:
                print(f"  [error] {csv_path.name}: {e}")
            csv_path.unlink(missing_ok=True)

        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{len(zips)} zips done, {total_parsed} records so far")

    print(f"\ntotal: {total_parsed} parsed, {total_failed} failed across {len(csv_files)} files")

    # merge into one file
    import pandas as pd
    dfs = [pd.read_csv(f) for f in csv_files if f.exists() and f.stat().st_size > 0]
    if dfs:
        merged = pd.concat(dfs, ignore_index=True)
        merged_path = OUT_DIR / "gkg-merged.csv"
        merged.to_csv(merged_path, index=False)
        print(f"merged {len(merged)} rows -> {merged_path}")


if __name__ == "__main__":
    asyncio.run(main())
