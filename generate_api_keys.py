import secrets

from app import app
from models.user import db
from models.device import Device


with app.app_context():

    devices = Device.query.all()

    for device in devices:

        if not device.api_key:

            device.api_key = secrets.token_urlsafe(32)

            print(
                f"API key generated for: "
                f"{device.name}"
            )

    db.session.commit()

    print("\nAll devices now have API keys!")