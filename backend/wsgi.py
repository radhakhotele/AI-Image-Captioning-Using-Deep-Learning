"""WSGI entry point used by Gunicorn."""

from .app import app

__all__ = ["app"]