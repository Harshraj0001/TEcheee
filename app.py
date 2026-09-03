import os
import secrets
from dotenv import load_dotenv

load_dotenv()

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify
)
from flask_migrate import Migrate
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from config import Config
from models.user import db, User
from models.device import Device
from models.sensor_data import SensorData
from models.device_command import DeviceCommand


app = Flask(__name__)
app.config.from_object(Config)

ADMIN_EMAIL = app.config.get("ADMIN_EMAIL", "harshraj72094@gmail.com")

# Initialize database
db.init_app(app)

# Initialize database migrations
migrate = Migrate(app, db)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Serializer for password reset tokens
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])


def generate_reset_token(email):
    return serializer.dumps(email, salt="password-reset-salt")


def verify_reset_token(token, max_age=1800):
    try:
        email = serializer.loads(
            token,
            salt="password-reset-salt",
            max_age=max_age  # 30 minutes
        )
        return email
    except (SignatureExpired, BadSignature):
        return None


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


# Create database tables
with app.app_context():
    db.create_all()


# Home page
@app.route("/")
def home():
    return render_template("index.html")


# Register page
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("register"))

        # Check username
        if User.query.filter_by(username=username).first():
            flash("Username already exists.")
            return redirect(url_for("register"))

        # Check email
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for("register"))

        # Hash password
        hashed_password = generate_password_hash(password)

        # Create user
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            is_admin=(email == ADMIN_EMAIL.lower()),
            is_active=True
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


# Login page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash("Invalid email or password.")
            return render_template("login.html")

        if not user.is_active:
            flash("Your account has been blocked.")
            return render_template("login.html")

        # Grant admin privilege if email matches configured admin email
        if user.email.lower() == ADMIN_EMAIL.lower() and not user.is_admin:
            user.is_admin = True
            db.session.commit()

        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# Forgot Password page
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Please enter your registered email address.")
            return render_template("forgot_password.html")

        user = User.query.filter_by(email=email).first()

        if not user:
            # Don't leak registered accounts, but confirm submission
            flash("If an account exists with that email, a password reset link has been created.")
            return redirect(url_for("login"))

        token = generate_reset_token(user.email)
        reset_url = url_for("reset_password", token=token, _external=True)

        # In local/demo environment without an SMTP mail server, flash the link for direct testing
        flash(f"Password reset link generated: {reset_url}")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


# Reset Password page
@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token)

    if not email:
        flash("The password reset link is invalid or has expired.")
        return redirect(url_for("forgot_password"))

    user = User.query.filter_by(email=email).first_or_404()

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password or not confirm_password:
            flash("All fields are required.")
            return render_template("reset_password.html", token=token)

        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("reset_password.html", token=token)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.")
            return render_template("reset_password.html", token=token)

        user.password = generate_password_hash(password)
        db.session.commit()

        flash("Your password has been reset successfully! Please log in.")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


# Dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    devices = Device.query.filter_by(
        user_id=current_user.id
    ).all()

    total_devices = len(devices)

    online_devices = len([
        device for device in devices
        if device.status == "Online"
    ])

    offline_devices = total_devices - online_devices

    return render_template(
        "dashboard.html",
        user=current_user,
        total_devices=total_devices,
        online_devices=online_devices,
        offline_devices=offline_devices
    )


# Add Device
@app.route("/add-device", methods=["GET", "POST"])
@login_required
def add_device():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        device_type = request.form.get("device_type", "").strip()
        device_id = request.form.get("device_id", "").strip()

        if not name or not device_type or not device_id:
            flash("All fields are required.")
            return redirect(url_for("add_device"))

        existing_device = Device.query.filter_by(
            device_id=device_id
        ).first()

        if existing_device:
            flash("This Device ID already exists.")
            return redirect(url_for("add_device"))

        new_device = Device(
            name=name,
            device_type=device_type,
            device_id=device_id,
            status="Offline",
            api_key=secrets.token_urlsafe(32),
            user_id=current_user.id
        )

        db.session.add(new_device)
        db.session.commit()

        flash("Device added successfully!")
        return redirect(url_for("devices"))

    return render_template("add_device.html")


# Devices List
@app.route("/devices")
@login_required
def devices():
    user_devices = Device.query.filter_by(
        user_id=current_user.id
    ).all()

    return render_template(
        "devices.html",
        devices=user_devices
    )


# Device Details
@app.route("/device/<int:device_id>")
@login_required
def device_details(device_id):
    device = Device.query.filter_by(
        id=device_id,
        user_id=current_user.id
    ).first_or_404()

    latest_reading = SensorData.query.filter_by(
        device_id=device.id
    ).order_by(
        SensorData.timestamp.desc()
    ).first()

    return render_template(
        "device_details.html",
        device=device,
        latest_reading=latest_reading
    )


# Toggle Device Status
@app.route("/device/<int:device_id>/toggle")
@login_required
def toggle_device(device_id):
    device = Device.query.filter_by(
        id=device_id,
        user_id=current_user.id
    ).first_or_404()

    if device.status == "Online":
        device.status = "Offline"
    else:
        device.status = "Online"

    db.session.commit()
    flash(f"Device status changed to {device.status}.")

    return redirect(
        url_for(
            "device_details",
            device_id=device.id
        )
    )


# Delete Device
@app.route("/device/<int:device_id>/delete")
@login_required
def delete_device(device_id):
    device = Device.query.filter_by(
        id=device_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(device)
    db.session.commit()

    flash("Device deleted successfully.")
    return redirect(url_for("devices"))


# Sensor Data History
@app.route("/device/<int:device_id>/history")
@login_required
def sensor_history(device_id):
    device = Device.query.filter_by(
        id=device_id,
        user_id=current_user.id
    ).first_or_404()

    sensor_readings = SensorData.query.filter_by(
        device_id=device.id
    ).order_by(
        SensorData.timestamp.desc()
    ).all()

    return render_template(
        "history.html",
        device=device,
        sensor_readings=sensor_readings
    )


# Sensor Data Charts
@app.route("/device/<int:device_id>/charts")
@login_required
def sensor_charts(device_id):
    device = Device.query.filter_by(
        id=device_id,
        user_id=current_user.id
    ).first_or_404()

    sensor_readings = SensorData.query.filter_by(
        device_id=device.id
    ).order_by(
        SensorData.timestamp.asc()
    ).all()

    timestamps = [
        reading.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        for reading in sensor_readings
    ]

    temperatures = [
        reading.temperature
        for reading in sensor_readings
    ]

    humidities = [
        reading.humidity
        for reading in sensor_readings
    ]

    voltages = [
        reading.voltage
        for reading in sensor_readings
    ]

    batteries = [
        reading.battery
        for reading in sensor_readings
    ]

    return render_template(
        "charts.html",
        device=device,
        timestamps=timestamps,
        temperatures=temperatures,
        humidities=humidities,
        voltages=voltages,
        batteries=batteries
    )


# API to get latest sensor data (AJAX polling in UI)
@app.route("/api/device/<int:device_id>/latest")
@login_required
def latest_sensor_data(device_id):
    device = Device.query.filter_by(
        id=device_id,
        user_id=current_user.id
    ).first_or_404()

    latest_reading = SensorData.query.filter_by(
        device_id=device.id
    ).order_by(
        SensorData.timestamp.desc()
    ).first()

    if not latest_reading:
        return {
            "success": False,
            "message": "No sensor data available"
        }, 404

    return {
        "success": True,
        "device_status": device.status,
        "temperature": latest_reading.temperature,
        "humidity": latest_reading.humidity,
        "voltage": latest_reading.voltage,
        "battery": latest_reading.battery,
        "timestamp": latest_reading.timestamp.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }


# API to receive sensor data (from IoT hardware)
@app.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():
    data = request.get_json(silent=True)

    if not data:
        return {
            "success": False,
            "message": "No JSON data received"
        }, 400

    device_id = data.get("device_id")
    api_key = data.get("api_key")

    if not device_id or not api_key:
        return {
            "success": False,
            "message": "Device ID and API key are required"
        }, 401

    # Support finding by either numeric database ID or string hardware device_id
    if isinstance(device_id, int) or (isinstance(device_id, str) and device_id.isdigit()):
        device = Device.query.filter(
            (Device.id == int(device_id)) | (Device.device_id == str(device_id))
        ).first()
    else:
        device = Device.query.filter_by(device_id=str(device_id)).first()

    if not device:
        return {
            "success": False,
            "message": "Device not found"
        }, 404

    if device.api_key != api_key:
        return {
            "success": False,
            "message": "Invalid API key"
        }, 403

    sensor_data = SensorData(
        device_id=device.id,
        temperature=data.get("temperature"),
        humidity=data.get("humidity"),
        voltage=data.get("voltage"),
        battery=data.get("battery")
    )

    db.session.add(sensor_data)
    device.status = "Online"
    db.session.commit()

    return {
        "success": True,
        "message": "Sensor data received successfully"
    }, 201


# USER/WEB CONTROL: Send command to device from UI
@app.route("/api/device/<int:device_id>/command", methods=["POST"])
@login_required
def send_device_command(device_id):
    device = Device.query.filter_by(
        id=device_id,
        user_id=current_user.id
    ).first_or_404()

    command = request.form.get("command")
    if not command and request.is_json:
        command = request.get_json().get("command")

    if not command:
        if request.is_json:
            return {"success": False, "message": "Command is required"}, 400
        flash("Command is required.")
        return redirect(url_for("device_details", device_id=device.id))

    new_command = DeviceCommand(
        device_id=device.id,
        command=command,
        status="Pending"
    )

    db.session.add(new_command)
    db.session.commit()

    if request.is_json:
        return {
            "success": True,
            "message": "Command sent successfully",
            "command": command
        }

    flash(f"Command '{command}' sent successfully.")
    return redirect(url_for("device_details", device_id=device.id))


# IOT HARDWARE: Poll pending command using API key
@app.route("/api/device/<int:device_id>/poll-command", methods=["POST"])
def get_device_command(device_id):
    data = request.get_json(silent=True)

    if not data:
        return {
            "success": False,
            "message": "No JSON data received"
        }, 400

    api_key = data.get("api_key")

    if not api_key:
        return {
            "success": False,
            "message": "API key is required"
        }, 401

    device = Device.query.filter_by(id=device_id).first()

    if not device:
        return {
            "success": False,
            "message": "Device not found"
        }, 404

    if device.api_key != api_key:
        return {
            "success": False,
            "message": "Invalid API key"
        }, 403

    pending_command = DeviceCommand.query.filter_by(
        device_id=device.id,
        status="Pending"
    ).order_by(
        DeviceCommand.created_at.asc()
    ).first()

    if not pending_command:
        return {
            "success": True,
            "command": None,
            "command_id": None,
            "message": "No pending commands"
        }, 200

    pending_command.status = "Sent"
    db.session.commit()

    return {
        "success": True,
        "command": pending_command.command,
        "command_id": pending_command.id,
        "status": pending_command.status
    }, 200


# =========================
# ADMIN PANEL ROUTES
# =========================

@app.route("/admin")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.")
        return redirect(url_for("dashboard"))

    total_users = User.query.count()
    total_devices = Device.query.count()
    online_devices = Device.query.filter_by(status="Online").count()
    offline_devices = total_devices - online_devices
    total_sensor_readings = SensorData.query.count()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_devices=total_devices,
        online_devices=online_devices,
        offline_devices=offline_devices,
        total_sensor_readings=total_sensor_readings
    )


@app.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    search = request.args.get("search", "").strip()
    role = request.args.get("role", "")
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = User.query

    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )

    if role == "admin":
        query = query.filter_by(is_admin=True)
    elif role == "user":
        query = query.filter_by(is_admin=False)

    if status == "active":
        query = query.filter_by(is_active=True)
    elif status == "blocked":
        query = query.filter_by(is_active=False)

    users = query.order_by(
        User.id.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template(
        "admin/users.html",
        users=users,
        search=search,
        role=role,
        status=status
    )


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot delete your own admin account.")
        return redirect(url_for("admin_users"))

    db.session.delete(user)
    db.session.commit()

    flash("User deleted successfully.")
    return redirect(url_for("admin_users"))


@app.route("/admin/user/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
def admin_toggle_role(user_id):
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot change your own admin role.")
        return redirect(url_for("admin_users"))

    user.is_admin = not user.is_admin
    db.session.commit()

    if user.is_admin:
        flash(f"{user.username} is now an admin.")
    else:
        flash(f"{user.username} is now a regular user.")

    return redirect(url_for("admin_users"))


@app.route("/admin/user/<int:user_id>/toggle-status", methods=["POST"])
@login_required
def admin_toggle_status(user_id):
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot block your own account.")
        return redirect(url_for("admin_users"))

    user.is_active = not user.is_active
    db.session.commit()

    if user.is_active:
        flash(f"{user.username} has been unblocked.")
    else:
        flash(f"{user.username} has been blocked.")

    return redirect(url_for("admin_users"))


@app.route("/admin/devices")
@login_required
def admin_devices():
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Device.query

    if search:
        query = query.filter(
            db.or_(
                Device.name.ilike(f"%{search}%"),
                Device.device_id.ilike(f"%{search}%")
            )
        )

    if status == "online":
        query = query.filter_by(status="Online")
    elif status == "offline":
        query = query.filter_by(status="Offline")

    devices = query.order_by(
        Device.id.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template(
        "admin/devices.html",
        devices=devices,
        search=search,
        status=status
    )


@app.route("/admin/device/<int:device_id>/delete", methods=["POST"])
@login_required
def admin_delete_device(device_id):
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    device = Device.query.get_or_404(device_id)

    db.session.delete(device)
    db.session.commit()

    flash(f"Device '{device.name}' deleted successfully.")
    return redirect(url_for("admin_devices"))


@app.route("/admin/device/<int:device_id>")
@login_required
def admin_device_details(device_id):
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    device = Device.query.get_or_404(device_id)

    latest_reading = SensorData.query.filter_by(
        device_id=device.id
    ).order_by(
        SensorData.timestamp.desc()
    ).first()

    commands = DeviceCommand.query.filter_by(
        device_id=device.id
    ).order_by(
        DeviceCommand.created_at.desc()
    ).all()

    return render_template(
        "admin/device_details.html",
        device=device,
        latest_reading=latest_reading,
        commands=commands
    )


@app.route("/admin/device/<int:device_id>/history")
@login_required
def admin_sensor_history(device_id):
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    device = Device.query.get_or_404(device_id)

    sensor_readings = SensorData.query.filter_by(
        device_id=device.id
    ).order_by(
        SensorData.timestamp.desc()
    ).all()

    return render_template(
        "admin/history.html",
        device=device,
        sensor_readings=sensor_readings
    )


@app.route("/admin/device/<int:device_id>/charts")
@login_required
def admin_sensor_charts(device_id):
    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("dashboard"))

    device = Device.query.get_or_404(device_id)

    sensor_readings = SensorData.query.filter_by(
        device_id=device.id
    ).order_by(
        SensorData.timestamp.asc()
    ).all()

    timestamps = [
        reading.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        for reading in sensor_readings
    ]

    temperatures = [
        reading.temperature
        for reading in sensor_readings
    ]

    humidities = [
        reading.humidity
        for reading in sensor_readings
    ]

    voltages = [
        reading.voltage
        for reading in sensor_readings
    ]

    batteries = [
        reading.battery
        for reading in sensor_readings
    ]

    return render_template(
        "admin/charts.html",
        device=device,
        timestamps=timestamps,
        temperatures=temperatures,
        humidities=humidities,
        voltages=voltages,
        batteries=batteries
    )


# Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("home"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 4000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )