from datetime import datetime, timezone

from models.user import db


class DeviceCommand(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id"),
        nullable=False
    )

    command = db.Column(
        db.String(50),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    status = db.Column(
        db.String(20),
        default="Pending"
    )