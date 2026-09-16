from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)


# =========================================================
# SECRET KEY
# =========================================================
# Local: uses the default value
# Render: uses SECRET_KEY environment variable

app.secret_key = os.getenv(
    "SECRET_KEY",
    "smart_parking_secret_key_2026"
)


# =========================================================
# DATABASE CONFIGURATION
# =========================================================
# Local XAMPP MySQL:
#   Host     = 127.0.0.1
#   User     = root
#   Password = empty
#   Database = smart_parking
#
# Render:
#   These values will come from Environment Variables.

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "smart_parking"),
    "port": int(os.getenv("DB_PORT", "3306"))
}


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():

    try:

        connection = mysql.connector.connect(
            **DB_CONFIG
        )

        if connection.is_connected():
            return connection

    except Error as e:

        print("Database connection error:", e)

    return None


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:

            error = "Please enter email and password."

            return render_template(
                "login.html",
                error=error
            )

        connection = get_db_connection()

        if connection is None:

            return "Database connection failed."

        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email = %s
            AND password = %s
            """,
            (email, password)
        )

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user:

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]

            return redirect(url_for("dashboard"))

        else:

            error = "Invalid email or password."

    return render_template(
        "login.html",
        error=error
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(url_for("login"))

    connection = get_db_connection()

    if connection is None:

        return "Database connection failed."

    cursor = connection.cursor(dictionary=True)

    # Total slots
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM parking_slots
        """
    )

    total_slots = cursor.fetchone()["total"]

    # Available slots
    cursor.execute(
        """
        SELECT COUNT(*) AS available
        FROM parking_slots
        WHERE status = 'Available'
        """
    )

    available_slots = cursor.fetchone()["available"]

    # Occupied slots
    cursor.execute(
        """
        SELECT COUNT(*) AS occupied
        FROM parking_slots
        WHERE status = 'Occupied'
        """
    )

    occupied_slots = cursor.fetchone()["occupied"]

    # Reserved slots
    cursor.execute(
        """
        SELECT COUNT(*) AS reserved
        FROM parking_slots
        WHERE status = 'Reserved'
        """
    )

    reserved_slots = cursor.fetchone()["reserved"]

    cursor.close()
    connection.close()

    return render_template(
        "dashboard.html",
        total_slots=total_slots,
        available_slots=available_slots,
        occupied_slots=occupied_slots,
        reserved_slots=reserved_slots
    )


# =========================================================
# PARKING SLOTS
# =========================================================

@app.route("/slots")
def slots():

    if "user_id" not in session:

        return redirect(url_for("login"))

    connection = get_db_connection()

    if connection is None:

        return "Database connection failed."

    cursor = connection.cursor(dictionary=True)

    # Get all parking slots
    cursor.execute(
        """
        SELECT *
        FROM parking_slots
        ORDER BY id
        """
    )

    parking_slots = cursor.fetchall()

    # Get active parking records
    cursor.execute(
        """
        SELECT *
        FROM parking_records
        WHERE status = 'Active'
        """
    )

    parking_records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "slots.html",
        slots=parking_slots,
        parking_records=parking_records
    )


# =========================================================
# RESERVE PARKING
# =========================================================

@app.route("/reserve", methods=["GET", "POST"])
def reserve():

    if "user_id" not in session:

        return redirect(url_for("login"))

    connection = get_db_connection()

    if connection is None:

        return "Database connection failed."

    cursor = connection.cursor(dictionary=True)

    # Get available slots
    cursor.execute(
        """
        SELECT *
        FROM parking_slots
        WHERE status = 'Available'
        ORDER BY id
        """
    )

    available_slots = cursor.fetchall()

    # POST request
    if request.method == "POST":

        slot_id = request.form.get("slot_id")
        vehicle_number = request.form.get("vehicle_number")
        reservation_date = request.form.get("reservation_date")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        if not slot_id or not vehicle_number:

            cursor.close()
            connection.close()

            return render_template(
                "reserve.html",
                available_slots=available_slots,
                error="Please fill all required fields."
            )

        # Check slot availability
        cursor.execute(
            """
            SELECT *
            FROM parking_slots
            WHERE id = %s
            AND status = 'Available'
            """,
            (slot_id,)
        )

        slot = cursor.fetchone()

        if not slot:

            cursor.close()
            connection.close()

            return render_template(
                "reserve.html",
                available_slots=available_slots,
                error="This parking slot is no longer available."
            )

        # Insert reservation
        cursor.execute(
            """
            INSERT INTO reservations
            (
                user_id,
                slot_id,
                vehicle_number,
                reservation_date,
                start_time,
                end_time,
                status
            )
            VALUES
            (%s, %s, %s, %s, %s, %s, 'Confirmed')
            """,
            (
                session["user_id"],
                slot_id,
                vehicle_number,
                reservation_date,
                start_time,
                end_time
            )
        )

        # Update slot
        cursor.execute(
            """
            UPDATE parking_slots
            SET
                status = 'Reserved',
                vehicle_number = %s
            WHERE id = %s
            """,
            (
                vehicle_number,
                slot_id
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for("slots"))

    cursor.close()
    connection.close()

    return render_template(
        "reserve.html",
        available_slots=available_slots
    )


# =========================================================
# PAYMENT HISTORY
# =========================================================

@app.route("/payments")
def payments():

    if "user_id" not in session:

        return redirect(url_for("login"))

    connection = get_db_connection()

    if connection is None:

        return "Database connection failed."

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM payments
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (session["user_id"],)
    )

    payments_data = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "payments.html",
        payments=payments_data
    )


# =========================================================
# PARK VEHICLE
# =========================================================

@app.route("/park", methods=["POST"])
def park_vehicle():

    if "user_id" not in session:

        return redirect(url_for("login"))

    slot_id = request.form.get("slot_id")
    vehicle_number = request.form.get("vehicle_number")

    if not slot_id or not vehicle_number:

        return "Slot and vehicle number are required."

    connection = get_db_connection()

    if connection is None:

        return "Database connection failed."

    cursor = connection.cursor(dictionary=True)

    # Find slot
    cursor.execute(
        """
        SELECT *
        FROM parking_slots
        WHERE id = %s
        """,
        (slot_id,)
    )

    slot = cursor.fetchone()

    if not slot:

        cursor.close()
        connection.close()

        return "Parking slot not found."

    # Do not allow occupied/reserved slots
    if slot["status"] in ["Occupied", "Reserved"]:

        cursor.close()
        connection.close()

        return "Parking slot is not available."

    # Create parking record
    cursor.execute(
        """
        INSERT INTO parking_records
        (
            user_id,
            slot_id,
            vehicle_number,
            entry_time,
            status
        )
        VALUES
        (%s, %s, %s, NOW(), 'Active')
        """,
        (
            session["user_id"],
            slot_id,
            vehicle_number
        )
    )

    # Update slot
    cursor.execute(
        """
        UPDATE parking_slots
        SET
            status = 'Occupied',
            vehicle_number = %s
        WHERE id = %s
        """,
        (
            vehicle_number,
            slot_id
        )
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("slots"))


# =========================================================
# VEHICLE EXIT
# =========================================================

@app.route("/exit/<int:record_id>", methods=["POST"])
def vehicle_exit(record_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    connection = get_db_connection()

    if connection is None:

        return "Database connection failed."

    cursor = connection.cursor(dictionary=True)

    # Find active record
    cursor.execute(
        """
        SELECT *
        FROM parking_records
        WHERE id = %s
        AND status = 'Active'
        """,
        (record_id,)
    )

    record = cursor.fetchone()

    if not record:

        cursor.close()
        connection.close()

        return "Parking record not found."

    # Entry time
    entry_time = record["entry_time"]

    # Current time
    current_time = datetime.now()

    # Calculate duration
    duration_seconds = (
        current_time - entry_time
    ).total_seconds()

    duration_minutes = max(
        1,
        int(duration_seconds / 60)
    )

    # Calculate hours
    hours = (duration_minutes + 59) // 60

    # Parking charges
    if hours <= 1:

        amount = 20

    else:

        amount = 20 + ((hours - 1) * 10)

    # Update parking record
    cursor.execute(
        """
        UPDATE parking_records
        SET
            exit_time = NOW(),
            duration_minutes = %s,
            amount = %s,
            status = 'Completed'
        WHERE id = %s
        """,
        (
            duration_minutes,
            amount,
            record_id
        )
    )

    # Make slot available
    cursor.execute(
        """
        UPDATE parking_slots
        SET
            status = 'Available',
            vehicle_number = NULL
        WHERE id = %s
        """,
        (record["slot_id"],)
    )

    # Create transaction ID
    transaction_id = (
        "TXN"
        + str(record_id)
        + datetime.now().strftime("%Y%m%d%H%M%S")
    )

    # Insert payment
    cursor.execute(
        """
        INSERT INTO payments
        (
            user_id,
            parking_record_id,
            amount,
            payment_method,
            payment_status,
            transaction_id
        )
        VALUES
        (%s, %s, %s, %s, %s, %s)
        """,
        (
            record["user_id"],
            record_id,
            amount,
            "Cash",
            "Paid",
            transaction_id
        )
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("slots"))


# =========================================================
# API - PARKING SLOTS
# =========================================================

@app.route("/api/slots")
def api_slots():

    if "user_id" not in session:

        return jsonify({
            "error": "Login required"
        }), 401

    connection = get_db_connection()

    if connection is None:

        return jsonify({
            "error": "Database connection failed"
        }), 500

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            slot_number,
            floor,
            status,
            vehicle_number,
            sensor_status
        FROM parking_slots
        ORDER BY id
        """
    )

    slots_data = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(slots_data)


# =========================================================
# API - PARKING STATISTICS
# =========================================================

@app.route("/api/statistics")
def api_statistics():

    if "user_id" not in session:

        return jsonify({
            "error": "Login required"
        }), 401

    connection = get_db_connection()

    if connection is None:

        return jsonify({
            "error": "Database connection failed"
        }), 500

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_slots,
            SUM(status = 'Available') AS available_slots,
            SUM(status = 'Occupied') AS occupied_slots,
            SUM(status = 'Reserved') AS reserved_slots
        FROM parking_slots
        """
    )

    statistics = cursor.fetchone()

    cursor.close()
    connection.close()

    return jsonify({

        "total_slots":
            statistics["total_slots"] or 0,

        "available_slots":
            statistics["available_slots"] or 0,

        "occupied_slots":
            statistics["occupied_slots"] or 0,

        "reserved_slots":
            statistics["reserved_slots"] or 0
    })


# =========================================================
# API - IOT SENSOR
# =========================================================

@app.route("/api/sensor", methods=["POST"])
def api_sensor():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "error": "Login required"
        }), 401

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "error": "No sensor data received"
        }), 400

    slot_id = data.get("slot_id")
    sensor_id = data.get("sensor_id")
    distance = data.get("distance")
    occupied = data.get("occupied")

    if slot_id is None:

        return jsonify({
            "success": False,
            "error": "slot_id is required"
        }), 400

    if sensor_id is None:

        sensor_id = "SENSOR001"

    if distance is None:

        distance = 0

    if occupied is None:

        occupied = False

    connection = get_db_connection()

    if connection is None:

        return jsonify({
            "success": False,
            "error": "Database connection failed"
        }), 500

    cursor = connection.cursor(dictionary=True)

    # Check slot
    cursor.execute(
        """
        SELECT *
        FROM parking_slots
        WHERE id = %s
        """,
        (slot_id,)
    )

    slot = cursor.fetchone()

    if not slot:

        cursor.close()
        connection.close()

        return jsonify({
            "success": False,
            "error": "Parking slot not found"
        }), 404

    # Convert occupied value to integer
    occupied_value = 1 if occupied else 0

    # Insert sensor data
    cursor.execute(
        """
        INSERT INTO sensor_data
        (
            slot_id,
            sensor_id,
            distance,
            occupied,
            sensor_time
        )
        VALUES
        (%s, %s, %s, %s, NOW())
        """,
        (
            slot_id,
            sensor_id,
            distance,
            occupied_value
        )
    )

    # Update parking slot status
    if occupied_value == 1:

        cursor.execute(
            """
            UPDATE parking_slots
            SET
                status = 'Occupied',
                sensor_status = 'Online'
            WHERE id = %s
            """,
            (slot_id,)
        )

        new_status = "Occupied"

    else:

        cursor.execute(
            """
            UPDATE parking_slots
            SET
                status = 'Available',
                vehicle_number = NULL,
                sensor_status = 'Online'
            WHERE id = %s
            """,
            (slot_id,)
        )

        new_status = "Available"

    connection.commit()

    cursor.close()
    connection.close()

    return jsonify({

        "success": True,

        "message":
            "Sensor data updated successfully",

        "slot_id":
            slot_id,

        "sensor_id":
            sensor_id,

        "distance":
            distance,

        "occupied":
            bool(occupied_value),

        "status":
            new_status
    })


# =========================================================
# SENSOR PAGE
# =========================================================

@app.route("/sensor")
def sensor():

    if "user_id" not in session:

        return redirect(url_for("login"))

    return render_template("sensor.html")


# =========================================================
# ADMIN RECORDS
# =========================================================

@app.route("/admin/records")
def admin_records():

    if "user_id" not in session:

        return redirect(url_for("login"))

    if session.get("user_role") != "admin":

        return "Access denied. Admin only."

    connection = get_db_connection()

    if connection is None:

        return "Database connection failed."

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            pr.id,
            pr.vehicle_number,
            pr.entry_time,
            pr.exit_time,
            pr.duration_minutes,
            pr.amount,
            pr.status,
            u.name AS user_name,
            ps.slot_number
        FROM parking_records pr

        LEFT JOIN users u
            ON pr.user_id = u.id

        LEFT JOIN parking_slots ps
            ON pr.slot_id = ps.id

        ORDER BY pr.id DESC
        """
    )

    records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "dashboard.html",
        records=records,
        total_slots=0,
        available_slots=0,
        occupied_slots=0,
        reserved_slots=0
    )


# =========================================================
# TEST DATABASE
# =========================================================

@app.route("/test-db")
def test_db():

    connection = get_db_connection()

    if connection is None:

        return """
        <h2>Database Connection Failed</h2>
        <p>Please check MySQL and database configuration.</p>
        """

    cursor = connection.cursor()

    cursor.execute("SELECT DATABASE()")

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    return f"""
    <h2>Database Connected Successfully!</h2>
    <p>Database: {result[0]}</p>
    """


# =========================================================
# RUN FLASK APPLICATION
# =========================================================

if __name__ == "__main__":

    print("--------------------------------------------")
    print("IoT Smart Parking Management System")
    print("--------------------------------------------")
    print("Starting Flask Server...")
    print("Open: http://127.0.0.1:5000")
    print("--------------------------------------------")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )