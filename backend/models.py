"""Database model for saved image captions."""

from datetime import datetime, timezone

from .extensions import db


class ImageRecord(db.Model):
    """An uploaded image and the caption generated for it."""

    __tablename__ = "image_records"

    id = db.Column(db.String(36), primary_key=True)
    filename = db.Column(db.String(255), nullable=False, unique=True, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_key = db.Column(db.String(255), nullable=False, unique=True)
    caption = db.Column(db.Text, nullable=False)
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        """Serialize public record fields without exposing server file paths."""
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "caption": self.caption,
            "uploaded_at": self.uploaded_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "image_url": f"/api/images/{self.id}/file",
        }