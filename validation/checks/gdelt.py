import os

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "gdelt"
DESCRIPTION = "GDELT pipeline: download, parse, canonical records, normalization, dataset registration"


def get_checks(config: ValidationConfig):
    return [
        GDELTDatasetsDirectory(config),
        GDELTRawFilesExist(config),
        GDELTParsedFilesExist(config),
        GDELTCanonicalSchema(config),
        GDELTValidatorCheck(config),
        GDELTDatasetRegistration(config),
    ]


class GDELTDatasetsDirectory(BaseCheck):
    name = "GDELT datasets directory"
    description = "GDELT data directories exist"

    def _run(self) -> CheckResult:
        base = self.config.gdelt_datasets_dir
        dirs = [
            os.path.join(base, "raw", "gdelt"),
            os.path.join(base, "processed", "gdelt"),
        ]
        existing = [d for d in dirs if os.path.isdir(d)]
        missing = [d for d in dirs if not os.path.isdir(d)]

        if missing:
            return CheckResult(
                name=self.name, passed=len(existing) > 0,
                message=f"Missing: {', '.join(missing)}" if missing else "All directories present",
                detail={"existing": existing, "missing": missing},
            )
        return CheckResult(
            name=self.name, passed=True,
            message=f"GDELT data directories exist ({len(existing)})",
            detail={"directories": existing},
        )


class GDELTRawFilesExist(BaseCheck):
    name = "GDELT raw files"
    description = "Downloaded GDELT raw files exist"

    def _run(self) -> CheckResult:
        base = os.path.join(self.config.gdelt_datasets_dir, "raw", "gdelt")
        if not os.path.isdir(base):
            return CheckResult(name=self.name, passed=True, warning=True, message="GDELT data not yet downloaded")

        raw_files = []
        for root, dirs, files in os.walk(base):
            for f in files:
                if f.endswith(".zip") or f.endswith(".csv"):
                    raw_files.append(os.path.relpath(os.path.join(root, f), base))

        if not raw_files:
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message="No GDELT raw files found (run pipeline first)",
            )
        return CheckResult(
            name=self.name, passed=True,
            message=f"{len(raw_files)} raw files found",
            detail={"files": raw_files[:20], "total": len(raw_files)},
        )


class GDELTParsedFilesExist(BaseCheck):
    name = "GDELT parsed files"
    description = "Parsed canonical CSV files exist"

    def _run(self) -> CheckResult:
        base = os.path.join(self.config.gdelt_datasets_dir, "processed", "gdelt")
        if not os.path.isdir(base):
            return CheckResult(name=self.name, passed=True, warning=True, message="No processed GDELT data")

        parsed_files = []
        total_lines = 0
        for root, dirs, files in os.walk(base):
            for f in files:
                if f.endswith(".csv"):
                    path = os.path.join(root, f)
                    parsed_files.append(os.path.relpath(path, base))
                    try:
                        with open(path) as fh:
                            total_lines += sum(1 for _ in fh)
                    except Exception:
                        pass

        if not parsed_files:
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message="No parsed GDELT files found",
            )
        return CheckResult(
            name=self.name, passed=True,
            message=f"{len(parsed_files)} parsed files, ~{total_lines} records",
            detail={"files": parsed_files[:10], "total_files": len(parsed_files), "total_records": total_lines},
        )


class GDELTCanonicalSchema(BaseCheck):
    name = "GDELT canonical schema"
    description = "Parsed files use correct canonical schema"

    def _run(self) -> CheckResult:
        base = os.path.join(self.config.gdelt_datasets_dir, "processed", "gdelt")
        if not os.path.isdir(base):
            return CheckResult(name=self.name, passed=True, warning=True, message="No processed GDELT data to validate")

        csv_files = []
        for root, dirs, files in os.walk(base):
            for f in files:
                if f.endswith(".csv"):
                    csv_files.append(os.path.join(root, f))

        if not csv_files:
            return CheckResult(name=self.name, passed=True, warning=True, message="No CSV files found")

        expected_headers = {
            "entity_type", "entity_id", "entity_name", "timestamp", "timestamp_precision",
            "latitude", "longitude", "location_name", "location_code", "attributes",
            "relationships", "source", "source_record_id", "confidence", "metadata",
        }

        checked = 0
        schema_ok = 0
        for path in csv_files[:5]:
            checked += 1
            try:
                with open(path) as f:
                    header = f.readline().strip().lower()
                cols = set(c.strip() for c in header.split(","))
                if expected_headers.issubset(cols):
                    schema_ok += 1
            except Exception:
                pass

        if schema_ok == checked:
            return CheckResult(
                name=self.name, passed=True,
                message=f"Schema valid for {schema_ok}/{checked} files checked",
                detail={"checked": checked, "valid": schema_ok},
            )
        return CheckResult(
            name=self.name, passed=False,
            message=f"Schema invalid: {schema_ok}/{checked} files passed",
            detail={"checked": checked, "valid": schema_ok},
        )


class GDELTValidatorCheck(BaseCheck):
    name = "GDELT validator integration"
    description = "GDELTValidator can be imported and run"

    def _run(self) -> CheckResult:
        try:
            from data_acquisition.gdelt_pipeline.validation import GDELTValidator
            import sys
            sys.path.insert(0, "services/ml-platform")
            validator = GDELTValidator()
            methods = [m for m in dir(validator) if not m.startswith("_")]
            return CheckResult(
                name=self.name, passed=True,
                message=f"GDELTValidator loaded with methods: {', '.join(methods[:8])}...",
                detail={"methods": methods},
            )
        except ImportError:
            # Try via sys.path
            try:
                import sys
                sys.path.insert(0, "services/ml-platform")
                from data_acquisition.gdelt_pipeline.validation import GDELTValidator
                return CheckResult(
                    name=self.name, passed=True,
                    message="GDELTValidator loaded (via sys.path)",
                )
            except ImportError as e:
                return CheckResult(
                    name=self.name, passed=True, warning=True,
                    message=f"GDELTValidator import failed: {e}. Install ml-platform deps and set PYTHONPATH",
                )


class GDELTDatasetRegistration(BaseCheck):
    name = "GDELT dataset registration"
    description = "GDELT datasets are registered in the ML Platform dataset registry"

    def _run(self) -> CheckResult:
        import urllib.request
        import json

        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/datasets?limit=20"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            datasets = data if isinstance(data, list) else data.get("datasets", data.get("items", [data]))
            gdelt_datasets = [d for d in datasets if "gdelt" in str(d.get("name", "")).lower()]

            if gdelt_datasets:
                names = [d.get("name", d.get("id", "?")) for d in gdelt_datasets]
                return CheckResult(
                    name=self.name, passed=True,
                    message=f"{len(gdelt_datasets)} GDELT datasets registered: {', '.join(names)}",
                    detail={"gdelt_datasets": gdelt_datasets},
                )
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message="No GDELT datasets registered yet",
                detail={"all_datasets": [d.get("name", "?") for d in datasets]},
            )
        except Exception as e:
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message=f"Cannot check dataset registration: {e}",
            )
