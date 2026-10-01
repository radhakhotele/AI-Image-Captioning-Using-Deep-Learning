"""API tests use a stubbed caption function and never download model weights."""

from io import BytesIO

import pytest
from PIL import Image

import backend.app as app_module
from backend.app import create_app


def _png_bytes(color=(95, 82, 220, 255)):
    image = Image.new("RGBA", (24, 16), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "generate_caption",
        lambda _image, _model_id: "A small purple square on a plain background.",
    )
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.sqlite3'}",
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "MAX_CONTENT_LENGTH": 1024 * 1024,
            "MAX_IMAGE_PIXELS": 100_000,
            "CORS_ORIGINS": ["http://localhost:8501"],
            "MODEL_ID": "test-model",
        }
    )
    yield test_app
    with test_app.app_context():
        from backend.extensions import db

        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _upload(client, name="sample.png", content=None):
    return client.post(
        "/api/caption",
        data={
            "image": (
                BytesIO(content if content is not None else _png_bytes()),
                name,
                "application/octet-stream",
            )
        },
        content_type="multipart/form-data",
    )


def test_health_reports_database_status(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json == {
        "success": True,
        "data": {"status": "ok", "database": "connected"},
    }


def test_upload_saves_caption_and_safe_image(client, app):
    response = _upload(client, name="../../holiday photo.png")

    assert response.status_code == 201
    payload = response.json["data"]
    assert payload["caption"] == "A small purple square on a plain background."
    assert payload["original_filename"] == "holiday_photo.png"
    assert payload["filename"].endswith(".png")
    assert "/" not in payload["filename"]
    assert payload["id"]
    assert payload["uploaded_at"]

    history = client.get("/api/images")
    assert history.status_code == 200
    assert len(history.json["data"]) == 1
    assert history.json["data"][0]["id"] == payload["id"]

    detail = client.get(f"/api/images/{payload['id']}")
    assert detail.status_code == 200
    assert detail.json["data"]["caption"] == payload["caption"]

    image_response = client.get(f"/api/images/{payload['id']}/file")
    assert image_response.status_code == 200
    assert image_response.mimetype == "image/png"
    assert image_response.data.startswith(b"\x89PNG")
    assert (tmp_path_uploads(app) / payload["filename"]).is_file()


def tmp_path_uploads(app):
    from pathlib import Path

    return Path(app.config["UPLOAD_DIR"])


def test_invalid_extension_and_mismatched_content_are_rejected(client):
    bad_extension = _upload(client, name="notes.txt", content=_png_bytes())
    mismatched_content = _upload(client, name="photo.jpg", content=_png_bytes())

    assert bad_extension.status_code == 400
    assert bad_extension.json["success"] is False
    assert bad_extension.json["error"]["code"] == "invalid_image"
    assert mismatched_content.status_code == 400
    assert "extension does not match" in mismatched_content.json["error"]["message"]


def test_non_image_bytes_are_rejected(client):
    response = _upload(client, name="fake.png", content=b"not an image")

    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_image"


def test_image_over_pixel_limit_is_rejected(client):
    oversized = Image.new("RGB", (317, 317), "white")
    image_data = BytesIO()
    oversized.save(image_data, format="PNG")

    response = _upload(client, content=image_data.getvalue())

    assert response.status_code == 400
    assert "dimensions are too large" in response.json["error"]["message"]


def test_request_over_upload_limit_returns_json_413(client):
    response = _upload(
        client,
        content=b"x" * (1024 * 1024 + 1),
    )

    assert response.status_code == 413
    assert response.json["error"]["code"] == "file_too_large"


def test_missing_upload_is_rejected(client):
    response = client.post("/api/caption", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
    assert response.json["error"]["code"] == "image_required"


def test_model_failure_does_not_save_an_image_or_record(client, app, monkeypatch):
    def fail_caption(_image, _model_id):
        raise app_module.CaptionGenerationError("model loading details")

    monkeypatch.setattr(app_module, "generate_caption", fail_caption)
    response = _upload(client)

    assert response.status_code == 503
    assert response.json["error"]["code"] == "caption_generation_failed"
    assert client.get("/api/images").json["data"] == []
    assert list(tmp_path_uploads(app).iterdir()) == []


def test_delete_removes_record_and_file(client, app):
    created = _upload(client).json["data"]
    stored_file = tmp_path_uploads(app) / created["filename"]
    assert stored_file.exists()

    response = client.delete(f"/api/images/{created['id']}")

    assert response.status_code == 200
    assert response.json["data"] == {"id": created["id"], "deleted": True}
    assert not stored_file.exists()
    assert client.get(f"/api/images/{created['id']}").status_code == 404


def test_missing_records_return_consistent_404_responses(client):
    record = client.get("/api/images/not-a-real-id")
    image_file = client.get("/api/images/not-a-real-id/file")
    delete = client.delete("/api/images/not-a-real-id")

    assert record.status_code == 404
    assert image_file.status_code == 404
    assert delete.status_code == 404
    assert record.json["error"]["code"] == "not_found"


def test_missing_image_file_returns_json_404(client, app):
    record = _upload(client).json["data"]
    (tmp_path_uploads(app) / record["filename"]).unlink()

    response = client.get(f"/api/images/{record['id']}/file")

    assert response.status_code == 404
    assert response.json["error"]["code"] == "file_not_found"