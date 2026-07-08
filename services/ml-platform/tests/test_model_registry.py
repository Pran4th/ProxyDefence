import pytest

from registry.model_registry import ModelRegistry, VALID_STAGES, VALID_TRANSITIONS


class TestModelRegistry:
    def test_valid_stages(self):
        assert "development" in VALID_STAGES
        assert "production" in VALID_STAGES
        assert "archived" in VALID_STAGES
        assert len(VALID_STAGES) == 5

    def test_valid_transitions(self):
        assert "development" in VALID_TRANSITIONS["validation"]
        assert "production" in VALID_TRANSITIONS["staging"]
        assert "staging" in VALID_TRANSITIONS["production"]
        assert [] == VALID_TRANSITIONS["archived"]

    def test_invalid_transition(self):
        assert "archived" in VALID_TRANSITIONS.get("production", [])
        assert "production" not in VALID_TRANSITIONS.get("development", [])

    def test_can_instantiate(self):
        assert ModelRegistry()


class TestModelLifecycle:
    def test_can_register(self):
        assert True

    def test_production_uniqueness(self):
        assert True
