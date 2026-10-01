"""Small, testable HTTP client for the Flask caption API."""

from typing import Any

import requests


class ApiError(RuntimeError):
    """A safe, user-facing API error with an optional HTTP status."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    """Keep HTTP and response validation out of the Streamlit page code."""

    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: int = 20,
        **kwargs: Any,
    ) -> dict:
        try:
            response = requests.request(
                method,
                f"{self.backend_url}{path}",
                timeout=timeout,
                **kwargs,
            )
        except requests.Timeout as exc:
            raise ApiError(
                "The backend took too long to respond. Please try again."
            ) from exc
        except requests.ConnectionError as exc:
            raise ApiError(
                "The caption service could not be reached. Check the backend URL "
                "and try again."
            ) from exc
        except requests.RequestException as exc:
            raise ApiError(
                "The request could not be completed. Please try again."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError(
                "The caption service returned an unexpected response.",
                response.status_code,
            ) from exc

        if not isinstance(payload, dict):
            raise ApiError(
                "The caption service returned an unexpected response.",
                response.status_code,
            )

        if not response.ok or payload.get("success") is not True:
            error = payload.get("error", {})
            message = (
                error.get("message")
                if isinstance(error, dict)
                else None
            ) or "The request could not be completed."
            raise ApiError(message, response.status_code)

        data = payload.get("data")
        if not isinstance(data, (dict, list)):
            raise ApiError(
                "The caption service returned an unexpected response.",
                response.status_code,
            )
        return data

    def health(self) -> dict:
        data = self._request("GET", "/api/health", timeout=10)
        if not isinstance(data, dict) or not data.get("status"):
            raise ApiError("The caption service returned an unexpected health response.")
        return data

    def generate_caption(self, filename: str, image_bytes: bytes) -> dict:
        data = self._request(
            "POST",
            "/api/caption",
            files={"image": (filename, image_bytes)},
            timeout=240,
        )
        if (
            not isinstance(data, dict)
            or not data.get("id")
            or not isinstance(data.get("caption"), str)
        ):
            raise ApiError("The caption service returned an unexpected caption response.")
        return data

    def list_images(self) -> list[dict]:
        data = self._request("GET", "/api/images")
        if not isinstance(data, list) or any(
            not isinstance(record, dict)
            or not record.get("id")
            or not isinstance(record.get("caption"), str)
            for record in data
        ):
            raise ApiError("The caption service returned an unexpected history response.")
        return data

    def get_image(self, image_id: str) -> bytes:
        try:
            response = requests.get(
                f"{self.backend_url}/api/images/{image_id}/file", timeout=20
            )
        except requests.Timeout as exc:
            raise ApiError("The image took too long to load. Please try again.") from exc
        except requests.ConnectionError as exc:
            raise ApiError(
                "The caption service could not be reached. Check the backend URL "
                "and try again."
            ) from exc
        except requests.RequestException as exc:
            raise ApiError("The image could not be loaded. Please try again.") from exc

        if not response.ok or not response.headers.get("content-type", "").startswith(
            "image/"
        ):
            raise ApiError("The saved image could not be loaded.", response.status_code)
        return response.content

    def delete_image(self, image_id: str) -> dict:
        return self._request("DELETE", f"/api/images/{image_id}")