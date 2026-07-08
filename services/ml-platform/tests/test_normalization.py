import pytest

from normalization.base import (
    BaseNormalizer,
    NormalizationRule,
    NormalizationResult,
    NormalizationConfig,
)
from normalization.registry import NormalizationRegistry, normalization_registry
from normalization.rules.country_normalizer import CountryNormalizer, _COUNTRY_MAP
from normalization.rules.org_normalizer import OrgNormalizer, _ORG_ABBREVIATIONS
from normalization.rules.unit_normalizer import UnitNormalizer, _UNIT_CONVERSIONS
from normalization.rules.currency_normalizer import CurrencyNormalizer
from normalization.rules.date_normalizer import DateNormalizer, DATE_FORMAT_PATTERNS
from normalization.rules.column_standardizer import ColumnStandardizer
from normalization.rules.duplicate_remover import DuplicateRemover


class TestNormalizationRule:
    def test_minimal(self):
        r = NormalizationRule(name="test", rule_type="country")
        assert r.is_active is True
        assert r.config == {}
        assert r.source_pattern is None

    def test_full(self):
        r = NormalizationRule(
            name="full", rule_type="org", source_pattern=".*corp",
            target_format="full_name", config={"mode": "strict"}, is_active=False,
        )
        assert r.source_pattern == ".*corp"
        assert r.is_active is False


class TestNormalizationResult:
    def test_defaults(self):
        r = NormalizationResult(rule_name="r1")
        assert r.records_affected == 0
        assert r.changes == []
        assert r.errors == []
        assert r.duration_ms == 0.0


class TestNormalizationConfig:
    def test_defaults(self):
        c = NormalizationConfig()
        assert c.max_errors == 10
        assert c.strict_mode is False
        assert c.dry_run is False
        assert c.report_changes is True

    def test_custom(self):
        c = NormalizationConfig(max_errors=5, strict_mode=True, dry_run=True, report_changes=False)
        assert c.strict_mode is True
        assert c.dry_run is True


class TestNormalizationRegistry:
    def test_register_and_get(self):
        reg = NormalizationRegistry()
        reg.register("test_type", CountryNormalizer)
        cls = reg.get("test_type")
        assert cls is CountryNormalizer

    def test_get_unknown_raises(self):
        reg = NormalizationRegistry()
        with pytest.raises(KeyError, match="no normalizer registered"):
            reg.get("nonexistent")

    def test_list_types(self):
        reg = NormalizationRegistry()
        reg.register("a", CountryNormalizer)
        reg.register("b", OrgNormalizer)
        types = reg.list_types()
        assert "a" in types
        assert "b" in types

    def test_create_returns_instance(self):
        reg = NormalizationRegistry()
        reg.register("country", CountryNormalizer)
        rule = NormalizationRule(name="c", rule_type="country")
        instance = reg.create(rule)
        assert isinstance(instance, CountryNormalizer)
        assert instance.rule.name == "c"

    def test_registry_has_all_14_types(self):
        types = normalization_registry.list_types()
        assert len(types) == 14
        expected = {
            "country", "organization", "unit", "currency", "date",
            "timestamp", "column_std", "duplicate", "entity_id",
            "geospatial", "categorical", "missing", "schema_map",
            "ontology_map",
        }
        for t in expected:
            assert t in types, f"Missing type: {t}"


class TestCountryNormalizer:
    def test_mapping_has_50_plus_entries(self):
        assert len(_COUNTRY_MAP) >= 50

    def test_usa_resolves(self):
        normalizer = CountryNormalizer(NormalizationRule(name="c", rule_type="country"))
        result = normalizer._standardize("usa")
        assert result == "United States"

    def test_us_resolves(self):
        normalizer = CountryNormalizer(NormalizationRule(name="c", rule_type="country"))
        result = normalizer._standardize("us")
        assert result == "United States"

    def test_unknown_returns_none(self):
        normalizer = CountryNormalizer(NormalizationRule(name="c", rule_type="country"))
        result = normalizer._standardize("atlantis")
        assert result is None

    def test_alpha2_code_lookup(self):
        normalizer = CountryNormalizer(NormalizationRule(name="c", rule_type="country"))
        result = normalizer._standardize("GB")
        assert result == "United Kingdom"

    def test_alpha3_code_lookup(self):
        normalizer = CountryNormalizer(NormalizationRule(name="c", rule_type="country"))
        result = normalizer._standardize("USA")
        assert result == "United States"

    def test_numeric_code_lookup(self):
        normalizer = CountryNormalizer(NormalizationRule(name="c", rule_type="country"))
        result = normalizer._standardize("840")
        assert result == "United States"

    def test_alpha2_export_format(self):
        rule = NormalizationRule(name="c", rule_type="country", config={"target_format": "alpha2"})
        normalizer = CountryNormalizer(rule)
        result = normalizer._standardize("usa")
        assert result == "US"

    def test_alpha3_export_format(self):
        rule = NormalizationRule(name="c", rule_type="country", config={"target_format": "alpha3"})
        normalizer = CountryNormalizer(rule)
        result = normalizer._standardize("usa")
        assert result == "USA"

    def test_numeric_export_format(self):
        rule = NormalizationRule(name="c", rule_type="country", config={"target_format": "numeric"})
        normalizer = CountryNormalizer(rule)
        result = normalizer._standardize("usa")
        assert result == "840"

    def test_validate_rule_valid(self):
        normalizer = CountryNormalizer(NormalizationRule(name="c", rule_type="country"))

        async def test():
            errors = await normalizer.validate_rule()
            assert errors == []

        import asyncio
        asyncio.run(test())

    def test_validate_invalid_format(self):
        rule = NormalizationRule(name="c", rule_type="country", config={"target_format": "invalid"})
        normalizer = CountryNormalizer(rule)

        async def test():
            errors = await normalizer.validate_rule()
            assert len(errors) == 1
            assert "invalid target_format" in errors[0]

        import asyncio
        asyncio.run(test())


class TestOrgNormalizer:
    def test_abbreviations_has_30_plus_entries(self):
        assert len(_ORG_ABBREVIATIONS) >= 30

    def test_opec_resolves(self):
        normalizer = OrgNormalizer(NormalizationRule(name="o", rule_type="organization"))
        result = normalizer._standardize("opec", dict(_ORG_ABBREVIATIONS))
        assert "Petroleum" in result

    def test_unknown_org_unchanged(self):
        normalizer = OrgNormalizer(NormalizationRule(name="o", rule_type="organization"))
        result = normalizer._standardize("Some Random Corp", dict(_ORG_ABBREVIATIONS))
        assert result is not None

    def test_strip_inc_suffix(self):
        normalizer = OrgNormalizer(NormalizationRule(name="o", rule_type="organization"))
        result = normalizer._standardize("Acme Inc", dict(_ORG_ABBREVIATIONS))
        assert "Inc" not in result

    def test_validate_valid(self):
        normalizer = OrgNormalizer(NormalizationRule(name="o", rule_type="organization"))

        async def test():
            errors = await normalizer.validate_rule()
            assert errors == []

        import asyncio
        asyncio.run(test())

    def test_validate_invalid_case(self):
        rule = NormalizationRule(name="o", rule_type="organization", config={"standardize_case": "wrong"})
        normalizer = OrgNormalizer(rule)

        async def test():
            errors = await normalizer.validate_rule()
            assert len(errors) == 1
            assert "invalid standardize_case" in errors[0]

        import asyncio
        asyncio.run(test())


class TestUnitNormalizer:
    def test_conversion_factors_exist(self):
        assert "volume" in _UNIT_CONVERSIONS
        assert "mass" in _UNIT_CONVERSIONS
        assert "energy" in _UNIT_CONVERSIONS
        assert "length" in _UNIT_CONVERSIONS
        assert "temperature" in _UNIT_CONVERSIONS
        assert "pressure" in _UNIT_CONVERSIONS

    def test_volume_conversion(self):
        normalizer = UnitNormalizer(NormalizationRule(
            name="u", rule_type="unit",
            config={"source_unit": "barrel", "target_unit": "barrel", "unit_type": "volume"},
        ))
        conv = normalizer.unit_type_map()
        assert conv.get("barrel") == 1.0
        assert conv.get("bbl") == 1.0

    def test_validate_valid(self):
        normalizer = UnitNormalizer(NormalizationRule(
            name="u", rule_type="unit",
            config={"unit_type": "volume"},
        ))

        async def test():
            errors = await normalizer.validate_rule()
            assert errors == []

        import asyncio
        asyncio.run(test())

    def test_validate_invalid_type(self):
        normalizer = UnitNormalizer(NormalizationRule(
            name="u", rule_type="unit",
            config={"unit_type": "invalid"},
        ))

        async def test():
            errors = await normalizer.validate_rule()
            assert any("invalid unit_type" in e for e in errors)

        import asyncio
        asyncio.run(test())


class TestCurrencyNormalizer:
    def test_parse_usd_symbol(self):
        normalizer = CurrencyNormalizer(NormalizationRule(name="c", rule_type="currency"))
        value, currency = normalizer._parse_currency("$1,234.56")
        assert value == pytest.approx(1234.56)
        assert currency == "USD"

    def test_parse_eur_symbol(self):
        normalizer = CurrencyNormalizer(NormalizationRule(name="c", rule_type="currency"))
        value, currency = normalizer._parse_currency("€500")
        assert value == 500.0
        assert currency == "EUR"

    def test_parse_gbp_symbol(self):
        normalizer = CurrencyNormalizer(NormalizationRule(name="c", rule_type="currency"))
        value, currency = normalizer._parse_currency("£99.99")
        assert value == pytest.approx(99.99)
        assert currency == "GBP"

    def test_parse_currency_suffix(self):
        normalizer = CurrencyNormalizer(NormalizationRule(name="c", rule_type="currency"))
        value, currency = normalizer._parse_currency("123.45 USD")
        assert value == pytest.approx(123.45)
        assert currency == "USD"

    def test_parse_numeric_only(self):
        normalizer = CurrencyNormalizer(NormalizationRule(name="c", rule_type="currency"))
        value, currency = normalizer._parse_currency("1000")
        assert value == 1000.0
        assert currency is None

    def test_parse_empty_returns_none(self):
        normalizer = CurrencyNormalizer(NormalizationRule(name="c", rule_type="currency"))
        value, currency = normalizer._parse_currency("")
        assert value is None
        assert currency is None

    def test_parse_na_value(self):
        normalizer = CurrencyNormalizer(NormalizationRule(name="c", rule_type="currency"))
        value, currency = normalizer._parse_currency("N/A")
        assert value is None

    def test_parse_parentheses_negative(self):
        normalizer = CurrencyNormalizer(NormalizationRule(name="c", rule_type="currency"))
        value, currency = normalizer._parse_currency("(500)")
        assert value == pytest.approx(-500.0)
        assert currency is None

    def test_validate_matching_separators(self):
        rule = NormalizationRule(
            name="c", rule_type="currency",
            config={"decimal_separator": ".", "thousand_separator": "."},
        )
        normalizer = CurrencyNormalizer(rule)

        async def test():
            errors = await normalizer.validate_rule()
            assert any("must differ" in e for e in errors)

        import asyncio
        asyncio.run(test())


class TestDateNormalizer:
    def test_format_patterns_populated(self):
        assert len(DATE_FORMAT_PATTERNS) >= 18

    def test_parse_iso_date(self):
        normalizer = DateNormalizer(NormalizationRule(name="d", rule_type="date"))
        result = normalizer._parse_date("2025-01-15", DATE_FORMAT_PATTERNS)
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_us_format(self):
        normalizer = DateNormalizer(NormalizationRule(name="d", rule_type="date"))
        result = normalizer._parse_date("01/15/2025", DATE_FORMAT_PATTERNS)
        assert result is not None
        assert result.month == 1
        assert result.day == 15

    def test_parse_year_only(self):
        normalizer = DateNormalizer(NormalizationRule(name="d", rule_type="date"))
        result = normalizer._parse_date("2025", DATE_FORMAT_PATTERNS)
        assert result is not None
        assert result.year == 2025

    def test_parse_invalid_returns_none(self):
        normalizer = DateNormalizer(NormalizationRule(name="d", rule_type="date"))
        result = normalizer._parse_date("not-a-date", DATE_FORMAT_PATTERNS)
        assert result is None

    def test_parse_empty_returns_none(self):
        normalizer = DateNormalizer(NormalizationRule(name="d", rule_type="date"))
        result = normalizer._parse_date("", DATE_FORMAT_PATTERNS)
        assert result is None

    def test_validate_valid(self):
        normalizer = DateNormalizer(NormalizationRule(name="d", rule_type="date"))

        async def test():
            errors = await normalizer.validate_rule()
            assert errors == []

        import asyncio
        asyncio.run(test())

    def test_validate_invalid_strategy(self):
        rule = NormalizationRule(name="d", rule_type="date", config={"error_strategy": "invalid"})
        normalizer = DateNormalizer(rule)

        async def test():
            errors = await normalizer.validate_rule()
            assert any("invalid error_strategy" in e for e in errors)

        import asyncio
        asyncio.run(test())


class TestColumnStandardizer:
    def test_snake_case_conversion(self):
        normalizer = ColumnStandardizer(NormalizationRule(name="c", rule_type="column_std"))
        result = normalizer._standardize_name("FirstName")
        assert result == "first_name"

    def test_snake_case_with_spaces(self):
        normalizer = ColumnStandardizer(NormalizationRule(name="c", rule_type="column_std"))
        result = normalizer._standardize_name("First Name")
        assert result == "first_name"

    def test_camel_case_preservation(self):
        rule = NormalizationRule(name="c", rule_type="column_std", config={"naming": "camelCase"})
        normalizer = ColumnStandardizer(rule)
        result = normalizer._standardize_name("first_name")
        assert "first" in result.lower()

    def test_pascal_case(self):
        rule = NormalizationRule(name="c", rule_type="column_std", config={"naming": "PascalCase"})
        normalizer = ColumnStandardizer(rule)
        result = normalizer._standardize_name("FirstName")
        assert result == "FirstName"

    def test_kebab_case(self):
        rule = NormalizationRule(name="c", rule_type="column_std", config={"naming": "kebab-case"})
        normalizer = ColumnStandardizer(rule)
        result = normalizer._standardize_name("FirstName")
        assert result == "first-name"

    def test_strip_special_chars(self):
        normalizer = ColumnStandardizer(NormalizationRule(name="c", rule_type="column_std"))
        result = normalizer._standardize_name("price@$%")
        assert "@" not in result
        assert "$" not in result

    def test_prefix_suffix(self):
        rule = NormalizationRule(
            name="c", rule_type="column_std",
            config={"prefix": "feat_", "suffix": "_v2"},
        )
        normalizer = ColumnStandardizer(rule)
        result = normalizer._standardize_name("age")
        assert result == "feat_age_v2"

    def test_max_length_truncation(self):
        rule = NormalizationRule(name="c", rule_type="column_std", config={"max_length": 10})
        normalizer = ColumnStandardizer(rule)
        result = normalizer._standardize_name("very_long_column_name")
        assert len(result) <= 10

    def test_validate_valid(self):
        normalizer = ColumnStandardizer(NormalizationRule(name="c", rule_type="column_std"))

        async def test():
            errors = await normalizer.validate_rule()
            assert errors == []

        import asyncio
        asyncio.run(test())

    def test_validate_invalid_naming(self):
        rule = NormalizationRule(name="c", rule_type="column_std", config={"naming": "bad"})
        normalizer = ColumnStandardizer(rule)

        async def test():
            errors = await normalizer.validate_rule()
            assert any("invalid naming" in e for e in errors)

        import asyncio
        asyncio.run(test())


class TestDuplicateRemover:
    def test_validate_valid(self):
        remover = DuplicateRemover(NormalizationRule(name="d", rule_type="duplicate"))

        async def test():
            errors = await remover.validate_rule()
            assert errors == []

        import asyncio
        asyncio.run(test())

    def test_validate_invalid_keep(self):
        rule = NormalizationRule(name="d", rule_type="duplicate", config={"keep": "invalid"})
        remover = DuplicateRemover(rule)

        async def test():
            errors = await remover.validate_rule()
            assert any("invalid keep" in e for e in errors)

        import asyncio
        asyncio.run(test())

    def test_validate_fuzzy_threshold_out_of_range(self):
        rule = NormalizationRule(name="d", rule_type="duplicate", config={"fuzzy_threshold": 200})
        remover = DuplicateRemover(rule)

        async def test():
            errors = await remover.validate_rule()
            assert any("fuzzy_threshold" in e for e in errors)

        import asyncio
        asyncio.run(test())

    def test_default_config(self):
        remover = DuplicateRemover(NormalizationRule(name="d", rule_type="duplicate"))
        assert remover.subset is None
        assert remover.keep == "first"
        assert remover.ignore_case is False
        assert remover.fuzzy_threshold == 0
