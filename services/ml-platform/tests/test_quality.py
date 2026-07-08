import pandas as pd
import pytest

from quality import QualityDimension, QualityScorer, QualityReporter, QualityDashboard


class TestQualityDimension:
    def test_constants(self):
        assert QualityDimension.COMPLETENESS == "completeness"
        assert QualityDimension.CONSISTENCY == "consistency"
        assert QualityDimension.UNIQUENESS == "uniqueness"
        assert QualityDimension.TIMELINESS == "timeliness"
        assert QualityDimension.VALIDITY == "validity"
        assert QualityDimension.INTEGRITY == "integrity"
        assert len({QualityDimension.COMPLETENESS, QualityDimension.CONSISTENCY,
                    QualityDimension.UNIQUENESS, QualityDimension.TIMELINESS,
                    QualityDimension.VALIDITY, QualityDimension.INTEGRITY}) == 6


class TestQualityScorer:
    @pytest.fixture
    def scorer(self):
        return QualityScorer()

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "a": [1, 2, 3, 4, 5],
            "b": [1.0, 2.0, None, 4.0, 5.0],
            "c": ["x", "y", "z", "w", "v"],
            "d": [None, None, None, None, None],
        })

    def test_score_completeness_perfect(self, scorer):
        df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})

        async def test():
            score, details = await scorer.score_completeness(df)
            assert score == 1.0
            assert details["total_missing"] == 0

        import asyncio
        asyncio.run(test())

    def test_score_completeness_with_missing(self, scorer, sample_df):
        async def test():
            score, details = await scorer.score_completeness(sample_df)
            assert score < 1.0
            assert details["total_missing"] > 0
            assert "per_column" in details

        import asyncio
        asyncio.run(test())

    def test_score_completeness_empty(self, scorer):
        df = pd.DataFrame()

        async def test():
            score, details = await scorer.score_completeness(df)
            assert score == 1.0

        import asyncio
        asyncio.run(test())

    def test_score_uniqueness_with_duplicates(self, scorer):
        df = pd.DataFrame({"x": [1, 1, 2, 3, 3]})

        async def test():
            score, details = await scorer.score_uniqueness(df)
            assert score < 1.0
            assert details["duplicate_rows"] == 2

        import asyncio
        asyncio.run(test())

    def test_score_uniqueness_no_duplicates(self, scorer):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})

        async def test():
            score, details = await scorer.score_uniqueness(df)
            assert score == 1.0
            assert details["duplicate_rows"] == 0

        import asyncio
        asyncio.run(test())

    def test_score_uniqueness_with_key_columns(self, scorer):
        df = pd.DataFrame({"id": [1, 1, 2], "val": ["a", "b", "c"]})

        async def test():
            score, details = await scorer.score_uniqueness(df, key_columns=["id"])
            assert score < 1.0
            assert details["key_violations"] is not None

        import asyncio
        asyncio.run(test())

    def test_score_validity_numeric_range(self, scorer):
        df = pd.DataFrame({"value": [1, 2, 3, 1000, 5]})

        async def test():
            score, details = await scorer.score_validity(df)
            assert score <= 1.0
            assert "numeric_range" in details["builtin_rules_applied"]

        import asyncio
        asyncio.run(test())

    def test_score_validity_email_detection(self, scorer):
        df = pd.DataFrame({"email": ["user@example.com", "not-an-email", "admin@test.org"]})

        async def test():
            score, details = await scorer.score_validity(df)
            assert "email" in details["builtin_rules_applied"]
            per_col = details["per_column_validity"]["email"]
            assert per_col["valid_count"] == 2

        import asyncio
        asyncio.run(test())

    def test_score_validity_url_detection(self, scorer):
        df = pd.DataFrame({"url": ["https://example.com", "not-a-url"]})

        async def test():
            score, details = await scorer.score_validity(df)
            assert "url" in details["builtin_rules_applied"]

        import asyncio
        asyncio.run(test())

    def test_score_validity_iso_date_detection(self, scorer):
        df = pd.DataFrame({"date_col": ["2025-01-15", "not-a-date", "2024-12-01"]})

        async def test():
            score, details = await scorer.score_validity(df)
            assert "iso_date" in details["builtin_rules_applied"]

        import asyncio
        asyncio.run(test())

    def test_score_validity_custom_rules(self, scorer):
        df = pd.DataFrame({"val": [10, 20, 30, 100]})
        rules = {"val": lambda x: x < 50}

        async def test():
            score, details = await scorer.score_validity(df, rules=rules)
            assert details["custom_rules"] is not None
            assert details["custom_rules"]["val"]["invalid"] == 1

        import asyncio
        asyncio.run(test())

    def test_overall_score_custom_weights(self, scorer):
        dim_scores = {
            QualityDimension.COMPLETENESS: 0.9,
            QualityDimension.CONSISTENCY: 0.8,
            QualityDimension.VALIDITY: 0.7,
        }
        weights = {QualityDimension.COMPLETENESS: 0.5, QualityDimension.CONSISTENCY: 0.3, QualityDimension.VALIDITY: 0.2}

        async def test():
            overall = await scorer.overall_score(dim_scores, weights)
            expected = (0.9 * 0.5 + 0.8 * 0.3 + 0.7 * 0.2) / (0.5 + 0.3 + 0.2)
            assert overall == pytest.approx(expected)

        import asyncio
        asyncio.run(test())

    def test_overall_score_default_weights(self, scorer):
        dim_scores = {
            QualityDimension.COMPLETENESS: 1.0,
            QualityDimension.CONSISTENCY: 1.0,
            QualityDimension.UNIQUENESS: 1.0,
            QualityDimension.TIMELINESS: 1.0,
            QualityDimension.VALIDITY: 1.0,
            QualityDimension.INTEGRITY: 1.0,
        }

        async def test():
            overall = await scorer.overall_score(dim_scores)
            assert overall == 1.0

        import asyncio
        asyncio.run(test())

    def test_score_all_returns_expected_structure(self, scorer):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})

        async def test():
            result = await scorer.score_all(df)
            assert "dimension_scores" in result
            assert "dimension_details" in result
            assert "overall_score" in result
            for dim in [QualityDimension.COMPLETENESS, QualityDimension.CONSISTENCY,
                        QualityDimension.UNIQUENESS, QualityDimension.TIMELINESS,
                        QualityDimension.VALIDITY, QualityDimension.INTEGRITY]:
                assert dim in result["dimension_scores"]

        import asyncio
        asyncio.run(test())

    def test_score_timeliness_no_date_column(self, scorer):
        df = pd.DataFrame({"a": [1, 2, 3]})

        async def test():
            score, details = await scorer.score_timeliness(df)
            assert score == 1.0
            assert "no date column" in details["note"]

        import asyncio
        asyncio.run(test())

    def test_score_consistency(self, scorer):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})

        async def test():
            score, details = await scorer.score_consistency(df)
            assert score > 0

        import asyncio
        asyncio.run(test())

    def test_score_consistency_empty(self, scorer):
        df = pd.DataFrame()

        async def test():
            score, details = await scorer.score_consistency(df)
            assert score == 1.0

        import asyncio
        asyncio.run(test())

    def test_score_integrity_no_references(self, scorer):
        df = pd.DataFrame({"fk": [1, 2, 3]})

        async def test():
            score, details = await scorer.score_integrity(df)
            assert score == 1.0

        import asyncio
        asyncio.run(test())

    def test_score_integrity_with_refs(self, scorer):
        df = pd.DataFrame({"fk": [1, 2, 99]})
        refs = {"fk": pd.DataFrame({"pk": [1, 2, 3]})}

        async def test():
            score, details = await scorer.score_integrity(df, reference_dfs=refs)
            assert score < 1.0
            assert details["total_violations"] == 1

        import asyncio
        asyncio.run(test())


class TestQualityReporter:
    @pytest.fixture
    def reporter(self):
        return QualityReporter()

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "a": [1, 2, 3],
            "b": ["x", "y", "z"],
            "c": [1.0, None, 3.0],
        })

    def test_generate_report_structure(self, reporter, sample_df):
        async def test():
            report = await reporter.generate_report(sample_df, dataset_name="test_ds", version=1)
            assert "metadata" in report
            assert "dimension_scores" in report
            assert "overall_score" in report
            assert "per_column_quality" in report
            assert "issues" in report
            assert "summary" in report
            assert report["metadata"]["dataset_name"] == "test_ds"
            assert report["metadata"]["dataset_version"] == 1
            assert report["metadata"]["row_count"] == 3

        import asyncio
        asyncio.run(test())

    def test_compare_reports_produces_delta(self, reporter, sample_df):
        async def test():
            report_a = await reporter.generate_report(sample_df, dataset_name="ds", version=1)
            report_b = await reporter.generate_report(sample_df, dataset_name="ds", version=2)
            comparison = await reporter.compare_reports(report_a, report_b)
            assert "report_a" in comparison
            assert "report_b" in comparison
            assert "deltas" in comparison
            assert "issues_delta" in comparison
            for dim_info in comparison["deltas"].values():
                assert "before" in dim_info
                assert "after" in dim_info
                assert "delta" in dim_info
                assert "direction" in dim_info

        import asyncio
        asyncio.run(test())

    def test_report_to_dataframe(self, reporter, sample_df):
        async def test():
            report = await reporter.generate_report(sample_df, dataset_name="ds", version=1)
            df = await reporter.report_to_dataframe(report)
            assert isinstance(df, pd.DataFrame)
            assert len(df) >= 6
            assert "dimension" in df.columns
            assert "score" in df.columns

        import asyncio
        asyncio.run(test())

    def test_generate_summary_empty(self, reporter):
        async def test():
            summary = await reporter.generate_summary([])
            assert summary["report_count"] == 0

        import asyncio
        asyncio.run(test())

    def test_generate_summary_with_reports(self, reporter, sample_df):
        async def test():
            r1 = await reporter.generate_report(sample_df, dataset_name="ds", version=1)
            r2 = await reporter.generate_report(sample_df, dataset_name="ds", version=2)
            summary = await reporter.generate_summary([r1, r2])
            assert summary["report_count"] == 2
            assert "average_scores" in summary
            assert "overall_average" in summary
            assert "issues_breakdown" in summary

        import asyncio
        asyncio.run(test())


class TestQualityDashboard:
    def test_class_exists(self):
        assert QualityDashboard is not None

    def test_method_signatures(self):
        import inspect
        methods = ["get_overall_quality", "get_dimension_trend", "get_lowest_scoring_columns",
                    "get_quality_summary", "get_issues", "snapshot_metrics"]
        for m in methods:
            assert hasattr(QualityDashboard, m), f"Missing method: {m}"
