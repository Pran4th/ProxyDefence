"""Unit tests for backend.shared.entity_normalization."""


class TestNormalizeEntity:
    def test_returns_original_for_unknown(self):
        from backend.shared.entity_normalization import normalize_entity
        assert normalize_entity("Unknown Entity") == "Unknown Entity"

    def test_normalizes_us(self):
        from backend.shared.entity_normalization import normalize_entity
        assert normalize_entity("us") == "United States"
        assert normalize_entity("US") == "United States"

    def test_normalizes_usa(self):
        from backend.shared.entity_normalization import normalize_entity
        assert normalize_entity("usa") == "United States"

    def test_normalizes_uk(self):
        from backend.shared.entity_normalization import normalize_entity
        assert normalize_entity("uk") == "United Kingdom"

    def test_normalizes_russia_possessive(self):
        from backend.shared.entity_normalization import normalize_entity
        assert normalize_entity("russia's") == "Russia"
        assert normalize_entity("Russia's") == "Russia"

    def test_normalizes_trump(self):
        from backend.shared.entity_normalization import normalize_entity
        assert normalize_entity("trump") == "Donald Trump"

    def test_strips_whitespace(self):
        from backend.shared.entity_normalization import normalize_entity
        assert normalize_entity("  us  ") == "United States"


class TestIsIgnoredEntity:
    def test_ignores_known_entities(self):
        from backend.shared.entity_normalization import is_ignored_entity
        assert is_ignored_entity("earthquakes") is True
        assert is_ignored_entity("band of brothers") is True

    def test_does_not_ignore_unknown(self):
        from backend.shared.entity_normalization import is_ignored_entity
        assert is_ignored_entity("Iran") is False

    def test_is_case_insensitive(self):
        from backend.shared.entity_normalization import is_ignored_entity
        assert is_ignored_entity("Earthquakes") is True


class TestIsBlacklistedEntity:
    def test_blacklists_news_sources(self):
        from backend.shared.entity_normalization import is_blacklisted_entity
        assert is_blacklisted_entity("Reuters") is True
        assert is_blacklisted_entity("AP") is True
        assert is_blacklisted_entity("BBC") is True

    def test_does_not_blacklist_other_entities(self):
        from backend.shared.entity_normalization import is_blacklisted_entity
        assert is_blacklisted_entity("Iran") is False

    def test_is_case_insensitive(self):
        from backend.shared.entity_normalization import is_blacklisted_entity
        assert is_blacklisted_entity("cnn") is True
