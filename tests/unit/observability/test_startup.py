"""Unit tests for backend.shared.observability.startup."""

import time


class TestStartupTimer:
    def test_init_records_start(self):
        from backend.shared.observability.startup import StartupTimer
        timer = StartupTimer("test-service")
        assert timer._service_name == "test-service"
        assert timer._current_phase is None
        assert timer._current_start is None
        assert timer._finished is False
        assert timer.total_seconds < 0.1

    def test_phase_transitions_record_previous(self):
        from backend.shared.observability.startup import StartupTimer
        timer = StartupTimer("test-service")
        timer.phase("config")
        time.sleep(0.01)
        timer.phase("database")
        timer.phase("ready")

        summary = timer.finish()
        assert summary["service"] == "test-service"
        assert len(summary["phases"]) == 3

    def test_finish_returns_summary(self):
        from backend.shared.observability.startup import StartupTimer
        timer = StartupTimer("test-service")
        timer.phase("config")
        timer.phase("database")
        timer.phase("ready")
        result = timer.finish()
        assert "service" in result
        assert "total_seconds" in result
        assert "phases" in result
        assert result["service"] == "test-service"

    def test_finish_is_idempotent(self):
        from backend.shared.observability.startup import StartupTimer
        timer = StartupTimer("test-service")
        timer.phase("config")
        timer.phase("ready")
        result1 = timer.finish()
        result2 = timer.finish()
        assert result1["total_seconds"] == result2["total_seconds"]
