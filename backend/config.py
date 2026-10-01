"""Environment-based configuration for local and hosted deployments."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _database_url() -> str:
    """Return an absolute SQLite URL locally or a normalized PostgreSQL URL."""
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        database_path = PROJECT_ROOT / "instance" / "captions.sqlite3"
        return f"sqlite:///{database_path.as_posix()}"

    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql+psycopg://", 1)
    elif value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+psycopg://", 1)

    # Resolve relative SQLite paths from the project root, not a process-specific
    # working directory. Keep in-memory SQLite URLs unchanged for tests.
    if value.startswith("sqlite:///") and not value.startswith("sqlite:////"):
        relative_path = value.removeprefix("sqlite:///")
        if relative_path != ":memory:":
            absolute_path = (PROJECT_ROOT / relative_path).resolve()
            value = f"sqlite:///{absolute_path.as_posix()}"

    return value


class BaseConfig:
    """Settings shared by development and production."""

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_DIR = os.getenv(
        "UPLOAD_DIR", str(Path(__file__).resolve().parent / "uploads")
    )
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
    MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", 25_000_000))
    MODEL_ID = os.getenv(
        "MODEL_ID", "nlpconnect/vit-gpt2-image-captioning"
    )
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8501,http://127.0.0.1:8501",
        ).split(",")
        if origin.strip()
    ]


class DevelopmentConfig(BaseConfig):
    """Configuration used for local development."""

    DEBUG = os.getenv("FLASK_DEBUG", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


class ProductionConfig(BaseConfig):
    """Configuration used by WSGI hosts such as Render."""

    DEBUG = False


class TestingConfig(BaseConfig):
    """Defaults for tests; tests override the database and upload directory."""

    TESTING = True
    DEBUG = False


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}