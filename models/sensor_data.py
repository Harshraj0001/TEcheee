from datetime import datetime
from models.user import db


class SensorData(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    device_id = db.Column(
        db.Integer,
        db.ForeignKey("device.id"),
        nullable=False
    )

    temperature = db.Column(
        db.Float,
        nullable=True
    )

    humidity = db.Column(
        db.Float,
        nullable=True
    )

    voltage = db.Column(
        db.Float,
        nullable=True
    )

    battery = db.Column(
        db.Float,
        nullable=True
    )

    timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )