"""Tests for frontend connection failures and API response handling."""

import requests

from frontend.api_client import ApiClient, ApiError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, content=b""):
        self.status_code = status_code
        self.ok = status_code < 400
        self._payload = payload or {"success": True, "data": {}}
        self.headers = headers or {"content-type": "application/json"}
        self.content = content

    def json(self):
        return self._payload


def test_client_posts_multipart_image_and_returns_record(monkeypatch):
    expected = {"id": "record-1", "caption": "A sample image"}
    calls = {}

    def fake_request(method, url, **kwargs):
        calls.update(method=method, url=url, **kwargs)
        return FakeResponse(payload={"success": True, "data": expected})

    monkeypatch.setattr("frontend.api_client.requests.request", fake_request)
    result = ApiClient("http://localhost:8000/").generate_caption(
        "sample.png", b"png bytes"
    )

    assert result == expected
    assert calls["method"] == "POST"
    assert calls["url"] == "http://localhost:8000/api/caption"
    assert calls["files"]["image"] == ("sample.png", b"png bytes")
    assert calls["timeout"] == 240


def test_client_exposes_backend_error_without_fake_success(monkeypatch):
    monkeypatch.setattr(
        "frontend.api_client.requests.request",
        lambda *_args, **_kwargs: FakeResponse(
            status_code=503,
            payload={
                "success": False,
                "error": {
                    "code": "caption_generation_failed",
                    "message": "Caption generation is temporarily unavailable.",
                },
            },
        ),
    )

    try:
        ApiClient("http://localhost:8000").generate_caption("a.png", b"data")
    except ApiError as error:
        assert error.status_code == 503
        assert "temporarily unavailable" in str(error)
    else:
        raise AssertionError("Expected the API error to be raised.")


def test_client_handles_unavailable_backend_and_timeout(monkeypatch):
    def connection_error(*_args, **_kwargs):
        raise requests.ConnectionError("private connection details")

    monkeypatch.setattr("frontend.api_client.requests.request", connection_error)
    try:
        ApiClient("http://localhost:8000").health()
    except ApiError as error:
        assert "could not be reached" in str(error)
        assert "private connection details" not in str(error)
    else:
        raise AssertionError("Expected an unavailable-backend error.")

    def timeout(*_args, **_kwargs):
        raise requests.Timeout()

    monkeypatch.setattr("frontend.api_client.requests.request", timeout)
    try:
        ApiClient("http://localhost:8000").health()
    except ApiError as error:
        assert "too long" in str(error)
    else:
        raise AssertionError("Expected a timeout error.")


def test_client_rejects_unexpected_response_shapes(monkeypatch):
    monkeypatch.setattr(
        "frontend.api_client.requests.request",
        lambda *_args, **_kwargs: FakeResponse(payload=["not", "an", "object"]),
    )

    try:
        ApiClient("http://localhost:8000").health()
    except ApiError as error:
        assert "unexpected response" in str(error)
    else:
        raise AssertionError("Expected a safe unexpected-response error.")