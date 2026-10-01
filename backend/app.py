"""Flask application factory and REST API routes."""

import io
import logging
import os
import uuid
import warnings
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from flask import Flask, current_app, jsonify, request, send_from_directory
from flask_cors import CORS
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from .caption_generator import CaptionGenerationError, generate_caption
from .config import CONFIG_BY_NAME
from .extensions import db
from .models import ImageRecord

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
EXPECTED_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}


def _error(message: str, code: str, status: int):
    return jsonify(
        {"success": False, "error": {"code": code, "message": message}}
    ), status


def _validate_and_normalize_image(
    image_bytes: bytes, supplied_filename: str, max_pixels: int
) -> tuple[Image.Image, bytes, str, str]:
    """Verify the actual image contents and re-encode it without metadata."""
    safe_original_name = secure_filename(supplied_filename)[:255]
    suffix = Path(safe_original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Upload a JPG, JPEG, or PNG image.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as candidate:
                detected_format = candidate.format
                width, height = candidate.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise ValueError(
                        "The image dimensions are too large. Choose a smaller image."
                    )
                candidate.verify()

            if detected_format != EXPECTED_FORMATS[suffix]:
                raise ValueError(
                    "The file extension does not match its image contents."
                )

            with Image.open(io.BytesIO(image_bytes)) as original:
                original.load()
                normalized = ImageOps.exif_transpose(original)
                if detected_format == "PNG":
                    if "A" in normalized.getbands():
                        normalized = normalized.convert("RGBA")
                    else:
                        normalized = normalized.convert("RGB")
                else:
                    normalized = normalized.convert("RGB")

                output = io.BytesIO()
                normalized.save(
                    output,
                    format=detected_format,
                    optimize=True,
                    **({"quality": 90} if detected_format == "JPEG" else {}),
                )
                return (
                    normalized.copy(),
                    output.getvalue(),
                    safe_original_name,
                    detected_format,
                )
    except ValueError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
    ) as exc:
        raise ValueError(
            "This file is not a valid, readable JPG, JPEG, or PNG image."
        ) from exc


def create_app(test_config: dict | None = None) -> Flask:
    """Create a configured API app; tests may pass an isolated configuration."""
    app = Flask(__name__)
    config_name = os.getenv("APP_ENV", "development").lower()
    app.config.from_object(CONFIG_BY_NAME.get(config_name, CONFIG_BY_NAME["development"]))
    if test_config:
        app.config.update(test_config)

    upload_dir = Path(app.config["UPLOAD_DIR"]).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"] = str(upload_dir)

    db.init_app(app)
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": app.config["CORS_ORIGINS"],
                "methods": ["GET", "POST", "DELETE", "OPTIONS"],
            }
        },
    )

    with app.app_context():
        # Local development remains zero-migration. Hosted databases should be
        # provisioned before the first request; this also creates their tables.
        db.create_all()

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(exception):
        return _error(
            "The image is larger than the configured upload limit.",
            "file_too_large",
            413,
        )

    @app.get("/api/health")
    def health():
        """Readiness check including a lightweight database query."""
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(
                {
                    "success": True,
                    "data": {"status": "ok", "database": "connected"},
                }
            )
        except SQLAlchemyError:
            current_app.logger.exception("Health check database query failed")
            return _error(
                "The database is unavailable.", "database_unavailable", 503
            )

    @app.post("/api/caption")
    def create_caption():
        """Validate, caption, store, and return one uploaded image."""
        uploaded = request.files.get("image")
        if uploaded is None or not uploaded.filename:
            return _error(
                "Choose an image file to generate a caption.",
                "image_required",
                400,
            )

        max_bytes = current_app.config["MAX_CONTENT_LENGTH"]
        image_bytes = uploaded.stream.read(max_bytes + 1)
        if len(image_bytes) > max_bytes:
            return _error(
                "The image is larger than the configured upload limit.",
                "file_too_large",
                413,
            )

        try:
            (
                image,
                normalized_bytes,
                original_name,
                image_format,
            ) = _validate_and_normalize_image(
                image_bytes, uploaded.filename, current_app.config["MAX_IMAGE_PIXELS"]
            )
        except ValueError as exc:
            return _error(str(exc), "invalid_image", 400)

        try:
            caption = generate_caption(image, current_app.config["MODEL_ID"])
        except CaptionGenerationError:
            current_app.logger.exception("Caption model request failed")
            return _error(
                "Caption generation is temporarily unavailable. Please try again.",
                "caption_generation_failed",
                503,
            )

        extension = ".png" if image_format == "PNG" else ".jpg"
        filename = f"{uuid.uuid4().hex}{extension}"
        storage_path = Path(current_app.config["UPLOAD_DIR"]) / filename
        record = ImageRecord(
            id=str(uuid.uuid4()),
            filename=filename,
            original_filename=original_name or f"image{extension}",
            storage_key=filename,
            caption=caption,
        )

        try:
            storage_path.write_bytes(normalized_bytes)
            db.session.add(record)
            db.session.commit()
        except (OSError, SQLAlchemyError):
            db.session.rollback()
            storage_path.unlink(missing_ok=True)
            current_app.logger.exception("Could not save the image caption record")
            return _error(
                "The image and caption could not be saved. Please try again.",
                "storage_failed",
                500,
            )

        return jsonify({"success": True, "data": record.to_dict()}), 201

    @app.get("/api/images")
    def list_images():
        """Return saved records newest-first."""
        try:
            records = ImageRecord.query.order_by(
                ImageRecord.uploaded_at.desc()
            ).all()
            return jsonify(
                {"success": True, "data": [record.to_dict() for record in records]}
            )
        except SQLAlchemyError:
            current_app.logger.exception("Could not list image records")
            return _error(
                "Saved captions could not be loaded.", "database_error", 500
            )

    @app.get("/api/images/<string:image_id>")
    def get_image(image_id: str):
        """Return one saved image record."""
        record = db.session.get(ImageRecord, image_id)
        if record is None:
            return _error("The requested image was not found.", "not_found", 404)
        return jsonify({"success": True, "data": record.to_dict()})

    @app.get("/api/images/<string:image_id>/file")
    def get_image_file(image_id: str):
        """Serve only the stored file associated with a known record."""
        record = db.session.get(ImageRecord, image_id)
        if record is None:
            return _error("The requested image was not found.", "not_found", 404)
        if not (Path(current_app.config["UPLOAD_DIR"]) / record.storage_key).is_file():
            return _error(
                "The stored image file could not be found.", "file_not_found", 404
            )
        try:
            return send_from_directory(
                current_app.config["UPLOAD_DIR"],
                record.storage_key,
                mimetype="image/png" if record.filename.endswith(".png") else "image/jpeg",
                conditional=True,
                max_age=3600,
            )
        except OSError:
            return _error(
                "The stored image file could not be found.", "file_not_found", 404
            )

    @app.delete("/api/images/<string:image_id>")
    def delete_image(image_id: str):
        """Delete a database record and then its associated stored image."""
        record = db.session.get(ImageRecord, image_id)
        if record is None:
            return _error("The requested image was not found.", "not_found", 404)

        storage_path = Path(current_app.config["UPLOAD_DIR"]) / record.storage_key
        try:
            db.session.delete(record)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Could not delete image record %s", image_id)
            return _error(
                "The image record could not be deleted.", "database_error", 500
            )

        try:
            storage_path.unlink(missing_ok=True)
        except OSError:
            # The record is already gone; keep the API success response but log
            # the orphaned file so an operator can clean persistent storage.
            current_app.logger.exception(
                "Could not remove stored image for record %s", image_id
            )

        return jsonify(
            {"success": True, "data": {"id": image_id, "deleted": True}}
        )

    @app.errorhandler(500)
    def handle_unexpected_error(exception):
        current_app.logger.exception("Unhandled API error")
        return _error(
            "The server could not complete this request.",
            "internal_server_error",
            500,
        )

    return app


app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        debug=app.config.get("DEBUG", False),
    )