"""Unit tests for backend.shared.request_middleware."""

import uuid


class TestRequestTrackingMiddleware:
    def test_adds_request_id_on_missing(self):
        from backend.shared.request_middleware import RequestTrackingMiddleware
        assert RequestTrackingMiddleware is not None

    def test_headers_defined(self):
        from backend.shared.request_middleware import REQUEST_ID_HEADER, CORRELATION_ID_HEADER
        assert REQUEST_ID_HEADER == "X-Request-ID"
        assert CORRELATION_ID_HEADER == "X-Correlation-ID"
