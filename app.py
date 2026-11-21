import os
import sqlite3
import smtplib
import json
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import date
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
secret_key = os.environ.get("AUTOHUB_SECRET_KEY")
if os.environ.get("AUTOHUB_ENV") == "production" and not secret_key:
    raise RuntimeError("Set AUTOHUB_SECRET_KEY before running the public website")
app.secret_key = secret_key or "local-development-key-change-before-publishing"
app.config["DATABASE"] = Path(__file__).with_name("autohub.db")

SHOWROOM = "AutoHub Showroom"
ADMIN_PASSWORD = os.environ.get("AUTOHUB_ADMIN_PASSWORD", "admin12345")
if os.environ.get("AUTOHUB_ENV") == "production" and ADMIN_PASSWORD == "admin12345":
    raise RuntimeError("Set a private AUTOHUB_ADMIN_PASSWORD before running the public website")
NOTIFICATION_EMAIL = os.environ.get("AUTOHUB_NOTIFICATION_EMAIL", "")
SMTP_USER = os.environ.get("AUTOHUB_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("AUTOHUB_SMTP_PASSWORD", "")
SMTP_HOST = os.environ.get("AUTOHUB_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("AUTOHUB_SMTP_PORT", "587"))
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("AUTOHUB_WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.environ.get("AUTOHUB_WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_TO = "".join(character for character in os.environ.get("AUTOHUB_WHATSAPP_TO", "") if character.isdigit())
WHATSAPP_TEMPLATE = os.environ.get("AUTOHUB_WHATSAPP_TEMPLATE", "autohub_notification")
WHATSAPP_LANGUAGE = os.environ.get("AUTOHUB_WHATSAPP_LANGUAGE", "en_US")
META_GRAPH_API_VERSION = os.environ.get("AUTOHUB_META_GRAPH_API_VERSION", "v27.0")


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response

SAMPLE_CARS = [
    ("Maruti Suzuki Baleno", 2022, 720000, "Petrol", "Manual", "A comfortable, fuel-efficient hatchback for everyday drives.", "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=1000&q=85"),
    ("Hyundai Creta", 2021, 1280000, "Diesel", "Automatic", "A spacious SUV with a smooth ride and useful features.", "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?auto=format&fit=crop&w=1000&q=85"),
    ("Tata Nexon", 2023, 1050000, "Petrol", "Manual", "A compact SUV ready for city trips and longer journeys.", "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=1000&q=85"),
]


def send_notification(subject, body):
    """Send a notification email when SMTP credentials are configured."""
    if not SMTP_USER or not SMTP_PASSWORD or not NOTIFICATION_EMAIL:
        app.logger.warning("Email notification skipped: configure email values in .env")
        return False
    message = EmailMessage()
    message["Subject"] = f"AutoHub Showroom: {subject}"
    message["From"] = SMTP_USER
    message["To"] = NOTIFICATION_EMAIL
    message.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        app.logger.exception("Could not send AutoHub email notification")
        return False


def send_whatsapp_notification(subject, body):
    """Send a WhatsApp template notification through Meta's Cloud API."""
    if not WHATSAPP_PHONE_NUMBER_ID or not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_TO:
        app.logger.warning("WhatsApp notification skipped: configure WhatsApp Cloud API values in .env")
        return False
    message_text = f"{subject}: {body}"[:1000]
    payload = {
        "messaging_product": "whatsapp",
        "to": WHATSAPP_TO,
        "type": "template",
        "template": {
            "name": WHATSAPP_TEMPLATE,
            "language": {"code": WHATSAPP_LANGUAGE},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": message_text}],
            }],
        },
    }
    api_url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    api_request = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(api_request, timeout=20) as response:
            response.read()
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        app.logger.exception("Could not send AutoHub WhatsApp notification")
        return False


def notify_owner(subject, body):
    send_notification(subject, body)
    send_whatsapp_notification(subject, body)


def get_db():
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def database():
    connection = get_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with database() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                price INTEGER NOT NULL,
                fuel TEXT NOT NULL,
                transmission TEXT NOT NULL,
                description TEXT NOT NULL,
                image_url TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS service_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                car_model TEXT NOT NULL,
                service_type TEXT NOT NULL,
                preferred_date TEXT NOT NULL,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'New',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sell_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                car_model TEXT NOT NULL,
                year INTEGER NOT NULL,
                kilometers INTEGER,
                expected_price INTEGER,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'New',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        count = db.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
        if count == 0:
            db.executemany("INSERT INTO cars (name, year, price, fuel, transmission, description, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)", SAMPLE_CARS)


init_db()


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in or create an account to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def current_user_context():
    user = None
    if session.get("user_id"):
        with database() as db:
            user = db.execute("SELECT id, name, email FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return {"current_user": user, "is_admin": session.get("is_admin", False)}


@app.route("/")
def home():
    with database() as db:
        cars = db.execute("SELECT * FROM cars ORDER BY id DESC LIMIT 2").fetchall()
    return render_template("index.html", showroom=SHOWROOM, cars=cars)


@app.route("/cars")
def cars():
    filters = {
        "q": request.args.get("q", "").strip(),
        "fuel": request.args.get("fuel", ""),
        "transmission": request.args.get("transmission", ""),
        "min_year": request.args.get("min_year", ""),
        "max_price": request.args.get("max_price", ""),
    }
    sql = "SELECT * FROM cars WHERE 1=1"
    values = []
    if filters["q"]:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        values.extend([f"%{filters['q']}%", f"%{filters['q']}%"])
    if filters["fuel"] in ("Petrol", "Diesel", "Electric", "Hybrid"):
        sql += " AND fuel = ?"
        values.append(filters["fuel"])
    if filters["transmission"] in ("Manual", "Automatic"):
        sql += " AND transmission = ?"
        values.append(filters["transmission"])
    if filters["min_year"].isdigit():
        sql += " AND year >= ?"
        values.append(int(filters["min_year"]))
    if filters["max_price"].isdigit():
        sql += " AND price <= ?"
        values.append(int(filters["max_price"]))
    with database() as db:
        car_list = db.execute(sql + " ORDER BY year DESC", values).fetchall()
    return render_template("cars.html", showroom=SHOWROOM, cars=car_list, filters=filters)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not name or not email or not phone or len(password) < 8:
            flash("Fill in every field. Your password needs at least 8 characters.", "error")
            return render_template("auth.html", showroom=SHOWROOM, mode="register")
        try:
            with database() as db:
                cursor = db.execute("INSERT INTO users (name, email, phone, password_hash) VALUES (?, ?, ?, ?)", (name, email, phone, generate_password_hash(password)))
                session["user_id"] = cursor.lastrowid
            notify_owner("New customer account", f"Name: {name}\nEmail: {email}\nPhone: {phone}")
            flash("Your account is ready. Welcome to AutoHub!", "success")
            return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            flash("That email already has an account. Please sign in.", "error")
    return render_template("auth.html", showroom=SHOWROOM, mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with database() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name']}!", "success")
            destination = request.args.get("next", "")
            if destination.startswith("/") and not destination.startswith("//"):
                return redirect(destination)
            return redirect(url_for("home"))
        flash("Email or password was not recognized.", "error")
    return render_template("auth.html", showroom=SHOWROOM, mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("home"))


@app.route("/book-service", methods=["GET", "POST"])
@customer_required
def book_service():
    if request.method == "POST":
        car_model = request.form.get("car_model", "").strip()
        service_type = request.form.get("service_type", "").strip()
        preferred_date = request.form.get("preferred_date", "")
        if not car_model or not service_type or not preferred_date or preferred_date < date.today().isoformat():
            flash("Please complete the required fields and choose a date from today onward.", "error")
            return redirect(url_for("book_service"))
        with database() as db:
            db.execute("INSERT INTO service_bookings (user_id, car_model, service_type, preferred_date, notes) VALUES (?, ?, ?, ?, ?)", (session["user_id"], car_model, service_type, preferred_date, request.form.get("notes", "").strip()))
            customer = db.execute("SELECT name, email, phone FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        notify_owner("New service booking", f"Customer: {customer['name']}\nEmail: {customer['email']}\nPhone: {customer['phone']}\nCar: {car_model}\nService: {service_type}\nPreferred date: {preferred_date}\nNotes: {request.form.get('notes', '').strip() or 'None'}")
        flash("Your service request was saved. The showroom will contact you to confirm.", "success")
        return redirect(url_for("home"))
    return render_template("service.html", showroom=SHOWROOM, today=date.today().isoformat())


@app.route("/sell-car", methods=["GET", "POST"])
@customer_required
def sell_car():
    if request.method == "POST":
        car_model = request.form.get("car_model", "").strip()
        year = request.form.get("year", "")
        if not car_model or not year.isdigit() or not (1980 <= int(year) <= date.today().year + 1):
            flash("Enter a car model and a valid year.", "error")
            return redirect(url_for("sell_car"))
        kilometers = request.form.get("kilometers", "").strip()
        expected_price = request.form.get("expected_price", "").strip()
        with database() as db:
            db.execute("INSERT INTO sell_requests (user_id, car_model, year, kilometers, expected_price, notes) VALUES (?, ?, ?, ?, ?, ?)", (session["user_id"], car_model, int(year), int(kilometers) if kilometers.isdigit() else None, int(expected_price) if expected_price.isdigit() else None, request.form.get("notes", "").strip()))
            customer = db.execute("SELECT name, email, phone FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        notify_owner("New car selling request", f"Customer: {customer['name']}\nEmail: {customer['email']}\nPhone: {customer['phone']}\nCar: {car_model}\nYear: {year}\nKilometers: {kilometers or 'Not supplied'}\nExpected price: {expected_price or 'Not supplied'}\nNotes: {request.form.get('notes', '').strip() or 'None'}")
        flash("Your car details were saved. The showroom will get in touch.", "success")
        return redirect(url_for("home"))
    return render_template("sell.html", showroom=SHOWROOM)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password", "") == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("That admin password is incorrect.", "error")
    return render_template("auth.html", showroom=SHOWROOM, mode="admin")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    notification = None
    with database() as db:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add_car":
                fields = [request.form.get(key, "").strip() for key in ("name", "year", "price", "fuel", "transmission", "description", "image_url")]
                if fields[0] and fields[1].isdigit() and fields[2].isdigit() and fields[5] and fields[6]:
                    db.execute("INSERT INTO cars (name, year, price, fuel, transmission, description, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)", (fields[0], int(fields[1]), int(fields[2]), fields[3], fields[4], fields[5], fields[6]))
                    flash("Car listing added.", "success")
                    notification = ("Car listing added", f"Car: {fields[0]}\nYear: {fields[1]}\nPrice: ₹{fields[2]}\nFuel: {fields[3]}\nTransmission: {fields[4]}")
                else:
                    flash("Enter the car details, year, price, description, and photo URL.", "error")
            elif action == "delete_car":
                removed = db.execute("SELECT name, year, price FROM cars WHERE id = ?", (request.form.get("car_id", "0"),)).fetchone()
                db.execute("DELETE FROM cars WHERE id = ?", (request.form.get("car_id", "0"),))
                if removed:
                    flash("Car listing removed.", "success")
                    notification = ("Car listing removed", f"Car: {removed['name']}\nYear: {removed['year']}\nPrice: ₹{removed['price']}")
            elif action == "booking_status":
                status = request.form.get("status")
                if status in ("New", "Contacted", "Confirmed", "Completed"):
                    booking = db.execute("SELECT b.car_model, b.service_type, b.preferred_date, u.name, u.email, u.phone FROM service_bookings b JOIN users u ON u.id = b.user_id WHERE b.id = ?", (request.form.get("booking_id", "0"),)).fetchone()
                    db.execute("UPDATE service_bookings SET status = ? WHERE id = ?", (status, request.form.get("booking_id", "0")))
                    if booking:
                        notification = ("Service booking status updated", f"Customer: {booking['name']}\nEmail: {booking['email']}\nPhone: {booking['phone']}\nCar: {booking['car_model']}\nService: {booking['service_type']}\nPreferred date: {booking['preferred_date']}\nNew status: {status}")
            elif action == "sell_status":
                status = request.form.get("status")
                if status in ("New", "Contacted", "Reviewed", "Closed"):
                    request_row = db.execute("SELECT s.car_model, s.year, u.name, u.email, u.phone FROM sell_requests s JOIN users u ON u.id = s.user_id WHERE s.id = ?", (request.form.get("request_id", "0"),)).fetchone()
                    db.execute("UPDATE sell_requests SET status = ? WHERE id = ?", (status, request.form.get("request_id", "0")))
                    if request_row:
                        notification = ("Car selling request status updated", f"Customer: {request_row['name']}\nEmail: {request_row['email']}\nPhone: {request_row['phone']}\nCar: {request_row['car_model']}\nYear: {request_row['year']}\nNew status: {status}")
        if request.method == "POST":
            admin_cars = bookings = sell_requests = None
        else:
            admin_cars = db.execute("SELECT * FROM cars ORDER BY id DESC").fetchall()
            bookings = db.execute("SELECT b.*, u.name, u.email, u.phone FROM service_bookings b JOIN users u ON u.id = b.user_id ORDER BY b.created_at DESC").fetchall()
            sell_requests = db.execute("SELECT s.*, u.name, u.email, u.phone FROM sell_requests s JOIN users u ON u.id = s.user_id ORDER BY s.created_at DESC").fetchall()
    if request.method == "POST":
        if notification:
            notify_owner(*notification)
        return redirect(url_for("admin_dashboard"))
    return render_template("admin.html", showroom=SHOWROOM, cars=admin_cars, bookings=bookings, sell_requests=sell_requests)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
