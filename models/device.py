from models.user import db


class Device(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    device_type = db.Column(
        db.String(100),
        nullable=False
    )

    device_id = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="Offline"
    )

    api_key = db.Column(
        db.String(100),
        unique=True,
        nullable=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    # Do NOT use backref="devices"
    user = db.relationship("User")