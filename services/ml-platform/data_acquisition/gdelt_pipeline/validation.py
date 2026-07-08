from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class GDELTValidationResult:
    dataset_type: str
    version: str
    checks: list[ValidationCheck]
    all_passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int


class GDELTValidator:
    def validate_download(
        self,
        file_path: Path,
        expected_md5: str | None = None,
    ) -> list[ValidationCheck]:
        checks: list[ValidationCheck] = []

        if not file_path.exists():
            checks.append(ValidationCheck(
                name="file_exists", passed=False,
                detail=f"File not found: {file_path}"
            ))
            return checks

        checks.append(ValidationCheck(
            name="file_exists", passed=True,
            detail=f"File exists: {file_path.name} ({file_path.stat().st_size} bytes)"
        ))

        if file_path.stat().st_size == 0:
            checks.append(ValidationCheck(
                name="file_not_empty", passed=False,
                detail="File is empty"
            ))
        else:
            checks.append(ValidationCheck(
                name="file_not_empty", passed=True,
                detail=f"File size: {file_path.stat().st_size} bytes"
            ))

        import zipfile
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                checks.append(ValidationCheck(
                    name="zip_valid", passed=True,
                    detail=f"Valid ZIP with {len(names)} entries: {names}"
                ))
        except zipfile.BadZipFile as e:
            checks.append(ValidationCheck(
                name="zip_valid", passed=False,
                detail=f"Invalid ZIP: {e}"
            ))

        if expected_md5:
            import hashlib
            h = hashlib.md5()
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            actual = h.hexdigest()
            if actual == expected_md5:
                checks.append(ValidationCheck(
                    name="checksum_md5", passed=True,
                    detail=f"MD5 matches: {actual}"
                ))
            else:
                checks.append(ValidationCheck(
                    name="checksum_md5", passed=False,
                    detail=f"MD5 mismatch: expected {expected_md5}, got {actual}"
                ))

        return checks

    def validate_parsed_csv(self, csv_path: Path) -> list[ValidationCheck]:
        checks: list[ValidationCheck] = []

        if not csv_path.exists():
            checks.append(ValidationCheck(
                name="parsed_csv_exists", passed=False,
                detail=f"CSV not found: {csv_path}"
            ))
            return checks

        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            row_count = 0
            for row in reader:
                row_count += 1

        required = {"entity_type", "entity_id", "timestamp", "source"}
        missing = required - set(fieldnames)

        if missing:
            checks.append(ValidationCheck(
                name="canonical_fields", passed=False,
                detail=f"Missing canonical fields: {missing}"
            ))
        else:
            checks.append(ValidationCheck(
                name="canonical_fields", passed=True,
                detail=f"Has {len(fieldnames)} columns: {fieldnames[:10]}..."
            ))

        if row_count > 0:
            checks.append(ValidationCheck(
                name="has_records", passed=True,
                detail=f"{row_count} rows parsed"
            ))
        else:
            checks.append(ValidationCheck(
                name="has_records", passed=False,
                detail="No records parsed"
            ))

        return checks

    def validate_registration(
        self, registration_result: Any
    ) -> list[ValidationCheck]:
        checks: list[ValidationCheck] = []

        if getattr(registration_result, "status", "") == "registered":
            checks.append(ValidationCheck(
                name="registration_status", passed=True,
                detail=f"Registered: {getattr(registration_result, 'registration_id', '')}"
            ))
        else:
            checks.append(ValidationCheck(
                name="registration_status", passed=False,
                detail=f"Failed: {getattr(registration_result, 'error', 'unknown')}"
            ))

        stats = getattr(registration_result, "statistics", {})
        if stats:
            row_count = stats.get("row_count", 0)
            col_count = stats.get("column_count", 0)
            checks.append(ValidationCheck(
                name="statistics_generated", passed=True,
                detail=f"Statistics: {row_count} rows, {col_count} columns, "
                       f"{stats.get('missing_cells', 0)} missing"
            ))
        else:
            checks.append(ValidationCheck(
                name="statistics_generated", passed=False,
                detail="No statistics generated"
            ))

        return checks

    def full_validation(
        self,
        dataset_type: str,
        version: str,
        zip_path: Path | None = None,
        expected_md5: str | None = None,
        csv_path: Path | None = None,
        registration_result: Any = None,
    ) -> GDELTValidationResult:
        all_checks: list[ValidationCheck] = []

        if zip_path:
            all_checks.extend(
                self.validate_download(zip_path, expected_md5)
            )

        if csv_path:
            all_checks.extend(
                self.validate_parsed_csv(csv_path)
            )

        if registration_result:
            all_checks.extend(
                self.validate_registration(registration_result)
            )

        passed = sum(1 for c in all_checks if c.passed)
        failed = len(all_checks) - passed

        return GDELTValidationResult(
            dataset_type=dataset_type,
            version=version,
            checks=all_checks,
            all_passed=failed == 0,
            total_checks=len(all_checks),
            passed_checks=passed,
            failed_checks=failed,
        )
