import os
import csv
import io
import random
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, session, flash
from database import (
    get_db, init_db, calculate_edc_bill, verify_admin_credentials, get_admin_by_id,
    register_user_request, admin_create_user, get_all_users, approve_user,
    reject_user, toggle_user_status, delete_user, get_pending_users_count, get_user_stats
)
from seed_data import seed_database

app = Flask(__name__)
app.secret_key = "cam-edc-secret-key-2026"
app.permanent_session_lifetime = timedelta(days=7)

# Ensure DB is created & seeded on startup
init_db()
seed_database()

# Context processor for global template variables
@app.context_processor
def inject_globals():
    today = date.today()
    current_user = None
    if "admin_id" in session:
        current_user = {
            "id": session.get("admin_id"),
            "username": session.get("admin_username"),
            "name": session.get("admin_name"),
            "role": session.get("admin_role")
        }
    pending_users_count = get_pending_users_count()
    return {
        "current_date": today.strftime("%d-%m-%Y"),
        "current_date_iso": today.strftime("%Y-%m-%d"),
        "current_month": today.strftime("%Y-%m"),
        "current_user": current_user,
        "pending_users_count": pending_users_count
    }

# ==========================================
# AUTHENTICATION & ACCESS CONTROL (ផ្ទៀងផ្ទាត់ Admin)
# ==========================================
@app.before_request
def require_login():
    # Public endpoints/paths that do not require authentication
    public_paths = ("/login", "/register", "/favicon.ico", "/api/users/register")
    if request.path.startswith("/static") or request.path in public_paths:
        return None
    
    if "admin_id" not in session:
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "សូមចូលគណនី Admin ជាមុនសិន!"}), 401
        return redirect(url_for("login_page", next=request.path))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if "admin_id" in session:
        return redirect(url_for("dashboard"))
    
    error_msg = None
    alert_type = "error"
    username_val = ""
    if request.method == "POST":
        username_val = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        remember_me = request.form.get("remember_me")

        auth_res = verify_admin_credentials(username_val, password)
        if auth_res.get("success"):
            admin = auth_res["user"]
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            session["admin_name"] = admin["full_name"]
            session["admin_role"] = admin["role"]
            if remember_me:
                session.permanent = True
            else:
                session.permanent = False
            
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("/login"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        else:
            error_msg = auth_res.get("message", "ឈ្មោះគណនី ឬលេខសម្ងាត់មិនត្រឹមត្រូវ!")
            alert_type = auth_res.get("status", "error")
    
    return render_template("login.html", error_msg=error_msg, alert_type=alert_type, username_val=username_val)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ==========================================
# USER MANAGEMENT & APPROVAL (គ្រប់គ្រង និងអនុម័តអ្នកប្រើប្រាស់)
# ==========================================
@app.route("/users")
def users_page():
    status_filter = request.args.get("status", "all")
    search_query = request.args.get("search", "").strip()
    users = get_all_users(status_filter=status_filter, search=search_query)
    stats = get_user_stats()
    return render_template(
        "users.html", 
        users=users, 
        stats=stats, 
        current_filter=status_filter, 
        search_query=search_query
    )

@app.route("/api/users/register", methods=["POST"])
def api_register_user():
    """ច្រកស្នើសុំគណនីថ្មី (Public)"""
    data = request.json or request.form or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    role = data.get("role", "បុគ្គលិកកត់ត្រាការប្រើប្រាស់").strip()

    if not username or not password or not full_name:
        return jsonify({"success": False, "error": "សូមបំពេញព័ត៌មានចាំបាច់ឱ្យបានគ្រប់គ្រាន់!"}), 400

    if len(password) < 4:
        return jsonify({"success": False, "error": "លេខសម្ងាត់ត្រូវមានយ៉ាងតិច ៤ តួអក្សរ!"}), 400

    success, result = register_user_request(username, password, full_name, phone, role)
    if success:
        return jsonify({
            "success": True, 
            "message": "ការស្នើសុំគណនីបានជោគជ័យ! សូមរង់ចាំការពិនិត្យ និងអនុម័តពី Admin ជាមុនសិន។"
        })
    else:
        return jsonify({"success": False, "error": result}), 400

@app.route("/api/users/add", methods=["POST"])
def api_add_user_admin():
    """Admin បង្កើតគណនីសកម្មផ្ទាល់"""
    data = request.json or request.form or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    role = data.get("role", "បុគ្គលិកកត់ត្រាការប្រើប្រាស់").strip()
    status = data.get("status", "active").strip()

    if not username or not password or not full_name:
        return jsonify({"success": False, "error": "សូមបំពេញព័ត៌មានឱ្យបានគ្រប់គ្រាន់!"}), 400

    success, result = admin_create_user(username, password, full_name, phone, role, status)
    if success:
        return jsonify({"success": True, "message": "បានបង្កើតគណនីអ្នកប្រើប្រាស់ដោយជោគជ័យ!"})
    else:
        return jsonify({"success": False, "error": result}), 400

@app.route("/api/users/<int:user_id>/approve", methods=["POST"])
def api_approve_user(user_id):
    """Admin អនុម័តគណនី"""
    data = request.json or {}
    role = data.get("role")
    admin_name = session.get("admin_name", "Admin EDC")
    ok = approve_user(user_id, admin_name=admin_name, role=role)
    if ok:
        return jsonify({"success": True, "message": "បានអនុម័តគណនីអ្នកប្រើប្រាស់ដោយជោគជ័យ!"})
    return jsonify({"success": False, "error": "មិនអាចអនុម័តគណនីនេះបានទេ!"}), 400

@app.route("/api/users/<int:user_id>/reject", methods=["POST"])
def api_reject_user(user_id):
    """Admin បដិសេធគណនី"""
    admin_name = session.get("admin_name", "Admin EDC")
    ok = reject_user(user_id, admin_name=admin_name)
    if ok:
        return jsonify({"success": True, "message": "បានបដិសេធការស្នើសុំគណនីនេះ!"})
    return jsonify({"success": False, "error": "មិនអាចបដិសេធគណនីនេះបានទេ!"}), 400

@app.route("/api/users/<int:user_id>/toggle-status", methods=["POST"])
def api_toggle_user_status(user_id):
    """Admin ផ្អាក ឬបើកដំណើរការឡើងវិញ"""
    ok, result = toggle_user_status(user_id)
    if ok:
        msg = "បានបើកដំណើរការគណនីឡើងវិញ!" if result == "active" else "បានផ្អាកដំណើរការគណនីបណ្តោះអាសន្ន!"
        return jsonify({"success": True, "status": result, "message": msg})
    return jsonify({"success": False, "error": result}), 400

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    """Admin លុបគណនី"""
    ok, msg = delete_user(user_id)
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "error": msg}), 400

# ==========================================
# 1. DASHBOARD
# ==========================================
@app.route("/")
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Total customers & status
    cursor.execute("SELECT COUNT(*) FROM customers")
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM customers WHERE status = 'active'")
    active_customers = cursor.fetchone()[0]
    inactive_customers = total_customers - active_customers

    # Total kWh & readings count
    cursor.execute("SELECT COALESCE(SUM(usage_kwh), 0), COUNT(*) FROM meter_readings")
    kwh_row = cursor.fetchone()
    total_kwh = kwh_row[0]
    total_readings = kwh_row[1]

    # Invoices & Revenue stats
    cursor.execute("SELECT COALESCE(SUM(total_khr), 0), COALESCE(SUM(total_usd), 0) FROM invoices WHERE payment_status = 'paid'")
    paid_row = cursor.fetchone()
    paid_khr = paid_row[0]
    paid_usd = paid_row[1]

    cursor.execute("SELECT COALESCE(SUM(total_khr), 0), COALESCE(SUM(total_usd), 0), COUNT(*) FROM invoices WHERE payment_status IN ('unpaid', 'overdue')")
    unpaid_row = cursor.fetchone()
    unpaid_khr = unpaid_row[0]
    unpaid_usd = unpaid_row[1]
    unpaid_count = unpaid_row[2]

    total_billed_khr = paid_khr + unpaid_khr
    collection_rate = round((paid_khr / total_billed_khr * 100), 1) if total_billed_khr > 0 else 0

    # Recent Invoices
    cursor.execute("""
        SELECT i.*, c.full_name as customer_name, c.meter_id, c.code as customer_code
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        ORDER BY i.id DESC
        LIMIT 6
    """)
    recent_invoices = cursor.fetchall()

    # Monthly usage chart data
    cursor.execute("""
        SELECT reading_month, SUM(usage_kwh) as total_kwh
        FROM meter_readings
        GROUP BY reading_month
        ORDER BY reading_month ASC
    """)
    usage_data = cursor.fetchall()
    chart_usage_months = [row["reading_month"] for row in usage_data]
    chart_usage_data = [round(row["total_kwh"], 1) for row in usage_data]

    conn.close()

    stats = {
        "total_customers": total_customers,
        "active_customers": active_customers,
        "inactive_customers": inactive_customers,
        "total_kwh": total_kwh,
        "total_readings": total_readings,
        "paid_khr": paid_khr,
        "paid_usd": paid_usd,
        "unpaid_khr": unpaid_khr,
        "unpaid_usd": unpaid_usd,
        "unpaid_count": unpaid_count,
        "collection_rate": collection_rate
    }

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_invoices=recent_invoices,
        chart_usage_months=chart_usage_months,
        chart_usage_data=chart_usage_data
    )

# ==========================================
# 2. CUSTOMER MANAGEMENT (ម៉ូឌុលទី ១)
# ==========================================
@app.route("/customers")
def customers_page():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY id DESC")
    customers = cursor.fetchall()
    conn.close()
    return render_template("customers.html", customers=customers)

@app.route("/api/customers", methods=["POST"])
def api_add_customer():
    data = request.json or {}
    code_input = data.get("code", "").strip()
    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    meter_id = data.get("meter_id", "").strip()
    address = data.get("address", "").strip()
    street = data.get("street", "").strip()
    location_code = data.get("location_code", "").strip()
    area = data.get("area", "ភ្នំពេញ - ដូនពេញ")
    national_id = data.get("national_id", "").strip()
    category = data.get("category", "residential")
    phase = data.get("phase", "1-Phase 220V")
    initial_reading = float(data.get("initial_reading", 0.0))

    if not full_name or not meter_id:
        return jsonify({"success": False, "error": "សូមបំពេញឈ្មោះអតិថិជន និងលេខនាឡិកាស្ទង់!"}), 400

    if not address and street:
        address = f"ផ្លូវ {street}"

    conn = get_db()
    cursor = conn.cursor()

    if code_input:
        code = code_input
    else:
        cursor.execute("SELECT MAX(id) FROM customers")
        max_id = cursor.fetchone()[0] or 100
        code = f"EDC-{max_id + 1:05d}"

    try:
        cursor.execute("""
            INSERT INTO customers (code, full_name, phone, national_id, address, area, street, location_code, meter_id, category, phase, initial_reading, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """, (code, full_name, phone or "012 345 678", national_id, address or "ភ្នំពេញ", area, street, location_code, meter_id, category, phase, initial_reading))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return jsonify({"success": True, "customer_id": new_id, "code": code})
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": f"លេខនាឡិកាស្ទង់ ឬកូដមានរួចហើយ: {str(e)}"}), 400

@app.route("/api/customers/search")
def api_search_customers():
    q = request.args.get("q", "").strip()
    conn = get_db()
    cursor = conn.cursor()
    if q:
        cursor.execute("""
            SELECT c.*,
                   COALESCE((SELECT current_reading FROM meter_readings WHERE customer_id = c.id ORDER BY reading_date DESC, id DESC LIMIT 1), c.initial_reading) as last_reading
            FROM customers c
            WHERE c.status = 'active'
            AND (c.code LIKE ? OR c.meter_id LIKE ? OR c.full_name LIKE ? OR c.phone LIKE ?)
            LIMIT 10
        """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
    else:
        cursor.execute("""
            SELECT c.*,
                   COALESCE((SELECT current_reading FROM meter_readings WHERE customer_id = c.id ORDER BY reading_date DESC, id DESC LIMIT 1), c.initial_reading) as last_reading
            FROM customers c
            WHERE c.status = 'active'
            ORDER BY c.id DESC
            LIMIT 10
        """)
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/customers/unread")
def api_unread_customers():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*,
               COALESCE((SELECT current_reading FROM meter_readings WHERE customer_id = c.id ORDER BY reading_date DESC, id DESC LIMIT 1), c.initial_reading) as last_reading
        FROM customers c
        WHERE c.status = 'active'
        AND c.id NOT IN (SELECT customer_id FROM meter_readings WHERE reading_month = ?)
        ORDER BY c.id ASC
    """, (month,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/customers/<int:customer_id>/status", methods=["POST"])
def api_toggle_customer_status(customer_id):
    data = request.json or {}
    new_status = data.get("status", "active")
    reason = data.get("reason", "")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE customers
        SET status = ?, status_reason = ?, status_updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_status, reason, customer_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "status": new_status})

@app.route("/api/customers/<int:customer_id>/last-reading")
def api_get_last_reading(customer_id):
    conn = get_db()
    cursor = conn.cursor()

    # Check latest meter reading
    cursor.execute("""
        SELECT current_reading FROM meter_readings
        WHERE customer_id = ?
        ORDER BY reading_date DESC, id DESC
        LIMIT 1
    """, (customer_id,))
    row = cursor.fetchone()

    if row:
        last_reading = row["current_reading"]
    else:
        # Fallback to initial reading
        cursor.execute("SELECT initial_reading FROM customers WHERE id = ?", (customer_id,))
        c_row = cursor.fetchone()
        last_reading = c_row["initial_reading"] if c_row else 0.0

    conn.close()
    return jsonify({"last_reading": last_reading})

# ==========================================
# 3. USAGE & METER MANAGEMENT (ម៉ូឌុលទី ២)
# ==========================================
@app.route("/usage")
def usage_page():
    customer_id = request.args.get("customer_id", type=int)
    conn = get_db()
    cursor = conn.cursor()

    # Load customers list for dropdown
    cursor.execute("SELECT id, code, full_name, meter_id, area, status FROM customers ORDER BY full_name ASC")
    customers = cursor.fetchall()

    selected_customer = None
    if customer_id:
        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        selected_customer = cursor.fetchone()

    # Query readings
    query = """
        SELECT r.*, c.full_name as customer_name, c.code as customer_code, c.meter_id,
               i.id as invoice_id
        FROM meter_readings r
        JOIN customers c ON r.customer_id = c.id
        LEFT JOIN invoices i ON r.id = i.reading_id
    """
    params = []
    if customer_id:
        query += " WHERE r.customer_id = ?"
        params.append(customer_id)
    query += " ORDER BY r.reading_date DESC, r.id DESC"

    cursor.execute(query, params)
    readings = cursor.fetchall()

    # Chart data
    chart_query = """
        SELECT reading_month, SUM(usage_kwh) as total_kwh
        FROM meter_readings
    """
    if customer_id:
        chart_query += " WHERE customer_id = ? GROUP BY reading_month ORDER BY reading_month ASC"
        cursor.execute(chart_query, (customer_id,))
    else:
        chart_query += " GROUP BY reading_month ORDER BY reading_month ASC"
        cursor.execute(chart_query)
    chart_rows = cursor.fetchall()
    chart_labels = [r["reading_month"] for r in chart_rows]
    chart_values = [round(r["total_kwh"], 1) for r in chart_rows]

    # Metrics
    cursor.execute("SELECT COALESCE(SUM(usage_kwh), 0) FROM meter_readings")
    total_kwh_sum = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM meter_readings WHERE reading_type = 'smart_meter'")
    smart_readings_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM meter_readings WHERE reading_type = 'manual'")
    manual_readings_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "usage.html",
        customers=customers,
        readings=readings,
        selected_customer_id=customer_id,
        selected_customer=selected_customer,
        chart_labels=chart_labels,
        chart_values=chart_values,
        total_kwh_sum=total_kwh_sum,
        smart_readings_count=smart_readings_count,
        manual_readings_count=manual_readings_count
    )

@app.route("/api/readings", methods=["POST"])
def api_add_reading():
    data = request.json or {}
    customer_id = int(data.get("customer_id"))
    reading_month = data.get("reading_month", date.today().strftime("%Y-%m"))
    reading_date = data.get("reading_date", date.today().strftime("%Y-%m-%d"))
    prev_r = float(data.get("previous_reading", 0.0))
    curr_r = float(data.get("current_reading", 0.0))
    notes = data.get("notes", "")
    reading_type = data.get("reading_type", "manual")

    multiplier = float(data.get("multiplier", 1.0))
    reading_by = data.get("reading_by", "បុគ្គលិក EDC")
    billing_cycle = data.get("billing_cycle", "ដុំទី ១")
    date_from = data.get("date_from") or None
    date_to = data.get("date_to") or None

    if curr_r < prev_r:
        return jsonify({"success": False, "error": "លេខកុងទ័រថ្មី ត្រូវតែធំជាង ឬស្មើលេខកុងទ័រចាស់!"}), 400

    usage_kwh = round((curr_r - prev_r) * multiplier, 1)

    conn = get_db()
    cursor = conn.cursor()

    # Get customer category
    cursor.execute("SELECT category FROM customers WHERE id = ?", (customer_id,))
    c_row = cursor.fetchone()
    if not c_row:
        conn.close()
        return jsonify({"success": False, "error": "រកមិនឃើញអតិថិជននេះទេ"}), 404

    category = c_row["category"]

    # 1. Insert meter reading
    cursor.execute("""
        INSERT INTO meter_readings (customer_id, reading_month, previous_reading, current_reading, usage_kwh, reading_date, reading_type, multiplier, reading_by, billing_cycle, date_from, date_to, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (customer_id, reading_month, prev_r, curr_r, usage_kwh, reading_date, reading_type, multiplier, reading_by, billing_cycle, date_from, date_to, notes))
    reading_id = cursor.lastrowid


    # 2. Auto-generate invoice
    bill = calculate_edc_bill(category, usage_kwh)
    cursor.execute("SELECT MAX(id) FROM invoices")
    max_inv_id = cursor.fetchone()[0] or 1000
    inv_no = f"INV-{reading_month.replace('-', '')}-{max_inv_id + 1}"

    # Due date is 15 days from reading date
    r_date_obj = datetime.strptime(reading_date, "%Y-%m-%d").date()
    due_date = (r_date_obj + timedelta(days=15)).strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO invoices (invoice_no, customer_id, reading_id, billing_month, usage_kwh, base_amount_khr, maintenance_fee_khr, total_khr, total_usd, due_date, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid')
    """, (
        inv_no, customer_id, reading_id, reading_month, usage_kwh,
        bill["base_khr"], bill["maintenance_khr"], bill["total_khr"], bill["total_usd"],
        due_date
    ))
    invoice_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "reading_id": reading_id,
        "invoice_id": invoice_id,
        "invoice_no": inv_no,
        "usage_kwh": usage_kwh,
        "total_khr": bill["total_khr"]
    })

@app.route("/api/smart-meter/sync", methods=["POST"])
def api_smart_meter_sync():
    """Simulate automatic IoT Smart Meter reading upload for all active customers for current month"""
    current_m = date.today().strftime("%Y-%m")
    today_str = date.today().strftime("%Y-%m-%d")

    conn = get_db()
    cursor = conn.cursor()

    # Find active customers who don't have reading for current_month
    cursor.execute("""
        SELECT c.id, c.category,
               COALESCE((SELECT current_reading FROM meter_readings WHERE customer_id = c.id ORDER BY reading_date DESC, id DESC LIMIT 1), c.initial_reading) as last_reading
        FROM customers c
        WHERE c.status = 'active'
        AND c.id NOT IN (SELECT customer_id FROM meter_readings WHERE reading_month = ?)
    """, (current_m,))
    eligible = cursor.fetchall()

    synced_count = 0
    inv_counter_start = 2000

    for row in eligible:
        cid = row["id"]
        cat = row["category"]
        prev_r = float(row["last_reading"])

        # Realistic usage increment
        increment = random.uniform(85.0, 320.0) if cat == "residential" else random.uniform(450.0, 1200.0)
        curr_r = round(prev_r + increment, 1)
        usage_kwh = round(curr_r - prev_r, 1)

        cursor.execute("""
            INSERT INTO meter_readings (customer_id, reading_month, previous_reading, current_reading, usage_kwh, reading_date, reading_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'smart_meter', 'ទាញទិន្នន័យស្វ័យប្រវត្តិតាម IoT Smart Meter')
        """, (cid, current_m, prev_r, curr_r, usage_kwh, today_str))
        r_id = cursor.lastrowid

        # Generate invoice
        bill = calculate_edc_bill(cat, usage_kwh)
        cursor.execute("SELECT MAX(id) FROM invoices")
        max_id = cursor.fetchone()[0] or inv_counter_start
        inv_no = f"INV-{current_m.replace('-', '')}-{max_id + 1}"
        due_d = (date.today() + timedelta(days=15)).strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO invoices (invoice_no, customer_id, reading_id, billing_month, usage_kwh, base_amount_khr, maintenance_fee_khr, total_khr, total_usd, due_date, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid')
        """, (
            inv_no, cid, r_id, current_m, usage_kwh,
            bill["base_khr"], bill["maintenance_khr"], bill["total_khr"], bill["total_usd"],
            due_d
        ))
        synced_count += 1

    conn.commit()
    conn.close()

    return jsonify({"success": True, "count": synced_count})

# ==========================================
# 4. BILLING & PAYMENT (ម៉ូឌុលទី ៣)
# ==========================================
@app.route("/billing")
def billing_page():
    status_filter = request.args.get("status")
    search_q = request.args.get("search")

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT i.*, c.full_name as customer_name, c.code as customer_code, c.phone, c.meter_id, c.category, c.area
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
    """
    params = []
    conditions = []

    if status_filter in ["paid", "unpaid", "overdue"]:
        conditions.append("i.payment_status = ?")
        params.append(status_filter)

    if search_q:
        conditions.append("(c.meter_id LIKE ? OR c.full_name LIKE ? OR i.invoice_no LIKE ?)")
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY i.id DESC"
    cursor.execute(query, params)
    invoices_raw = cursor.fetchall()

    invoices = []
    for inv in invoices_raw:
        item = dict(inv)
        item["category_label"] = "លំនៅឋាន" if inv["category"] == "residential" else "អាជីវកម្ម"
        invoices.append(item)

    # Metrics
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_khr), 0), COALESCE(SUM(total_usd), 0) FROM invoices WHERE payment_status = 'paid'")
    p_cnt, paid_amount_khr, paid_amount_usd = cursor.fetchone()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_khr), 0), COALESCE(SUM(total_usd), 0) FROM invoices WHERE payment_status = 'unpaid'")
    u_cnt, unpaid_amount_khr, unpaid_amount_usd = cursor.fetchone()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_khr), 0) FROM invoices WHERE payment_status = 'overdue'")
    o_cnt, overdue_amount_khr = cursor.fetchone()

    conn.close()

    return render_template(
        "billing.html",
        invoices=invoices,
        current_filter=status_filter,
        paid_invoices_count=p_cnt,
        paid_amount_khr=paid_amount_khr,
        paid_amount_usd=paid_amount_usd,
        unpaid_invoices_count=u_cnt,
        unpaid_amount_khr=unpaid_amount_khr,
        unpaid_amount_usd=unpaid_amount_usd,
        overdue_invoices_count=o_cnt,
        overdue_amount_khr=overdue_amount_khr
    )

@app.route("/api/invoices/<int:invoice_id>")
def api_get_invoice(invoice_id):
    import calendar
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.*, c.full_name as customer_name, c.code as customer_code, c.phone, c.national_id,
               c.address, c.area, c.meter_id, c.category, c.phase, c.location_code, c.street,
               r.previous_reading, r.current_reading, r.multiplier, r.reading_date, r.date_from, r.date_to
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        LEFT JOIN meter_readings r ON i.reading_id = r.id
        WHERE i.id = ?
    """, (invoice_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "រកមិនឃើញវិក័យប័ត្រ"}), 404

    inv = dict(row)

    # Fallbacks for location and street
    if not inv.get("location_code"):
        inv["location_code"] = f"J{(inv['customer_id'] % 9) + 1:02d}"

    # Dates
    b_month_str = inv.get("billing_month", "2026-08")
    try:
        b_year, b_month = map(int, b_month_str.split("-"))
    except Exception:
        b_year, b_month = 2026, 8

    _, last_day = calendar.monthrange(b_year, b_month)
    if not inv.get("date_from"):
        inv["date_from"] = f"01-{b_month:02d}-{b_year}"
    else:
        parts = str(inv["date_from"]).split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            inv["date_from"] = f"{parts[2]}-{parts[1]}-{parts[0]}"

    if not inv.get("date_to"):
        inv["date_to"] = f"{last_day:02d}-{b_month:02d}-{b_year}"
    else:
        parts = str(inv["date_to"]).split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            inv["date_to"] = f"{parts[2]}-{parts[1]}-{parts[0]}"

    inv["invoice_date"] = f"{min(29, last_day):02d}-{b_month:02d}-{b_year}"
    next_m = b_month + 1 if b_month < 12 else 1
    next_y = b_year if b_month < 12 else b_year + 1
    inv["start_payment_date"] = f"03-{next_m:02d}-{next_y}"

    # Balance brought forward (previous unpaid balance)
    cursor.execute("""
        SELECT COALESCE(SUM(total_khr), 0) as prev_unpaid
        FROM invoices
        WHERE customer_id = ? AND id != ? AND payment_status = 'unpaid' AND billing_month < ?
    """, (inv["customer_id"], invoice_id, b_month_str))
    p_unpaid = cursor.fetchone()
    inv["balance_brought_forward"] = float(p_unpaid["prev_unpaid"]) if p_unpaid else 0.0

    # Past 12-month readings history
    cursor.execute("""
        SELECT reading_month, usage_kwh
        FROM meter_readings
        WHERE customer_id = ?
        ORDER BY reading_month ASC
    """, (inv["customer_id"],))
    readings_map = {r["reading_month"]: r["usage_kwh"] for r in cursor.fetchall()}
    conn.close()

    history_12 = []
    for offset in range(11, -1, -1):
        m = b_month - offset
        y = b_year
        while m <= 0:
            m += 12
            y -= 1
        m_key = f"{y:04d}-{m:02d}"
        label = f"{m:02d}-{y}"
        if m_key in readings_map:
            kwh = float(readings_map[m_key])
        else:
            base_u = float(inv.get("usage_kwh") or 120.0)
            variation = ((m * 13 + y * 7) % 29) - 14
            kwh = max(10.0, round(base_u + variation, 1))
        history_12.append({
            "month_key": m_key,
            "label": label,
            "usage_kwh": kwh
        })
    inv["history_12"] = history_12

    # Tariff calculation breakdown
    calc = calculate_edc_bill(inv.get("category", "residential"), inv.get("usage_kwh", 0))
    inv["breakdown"] = calc.get("breakdown", [])

    return jsonify(inv)

@app.route("/api/invoices/<int:invoice_id>/pay", methods=["POST"])
def api_pay_invoice(invoice_id):
    data = request.json or {}
    payment_method = data.get("payment_method", "KHQR")
    payment_reference = data.get("payment_reference", f"TXN-{random.randint(100000, 999999)}")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices
        SET payment_status = 'paid',
            payment_date = CURRENT_TIMESTAMP,
            payment_method = ?,
            payment_reference = ?
        WHERE id = ?
    """, (payment_method, payment_reference, invoice_id))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "payment_status": "paid",
        "payment_method": payment_method,
        "payment_reference": payment_reference
    })

# ==========================================
# 5. REPORTS & NOTIFICATIONS (ម៉ូឌុលទី ៤)
# ==========================================
@app.route("/reports")
def reports_page():
    conn = get_db()
    cursor = conn.cursor()

    # Total collected vs debt
    cursor.execute("SELECT COALESCE(SUM(total_khr), 0), COALESCE(SUM(total_usd), 0) FROM invoices WHERE payment_status = 'paid'")
    total_collected_khr, total_collected_usd = cursor.fetchone()

    cursor.execute("SELECT COALESCE(SUM(total_khr), 0), COALESCE(SUM(total_usd), 0), COUNT(*) FROM invoices WHERE payment_status IN ('unpaid', 'overdue')")
    total_debt_khr, total_debt_usd, unpaid_count = cursor.fetchone()

    total_khr = total_collected_khr + total_debt_khr
    collection_rate = round((total_collected_khr / total_khr * 100), 1) if total_khr > 0 else 0

    cursor.execute("SELECT COALESCE(SUM(usage_kwh), 0) FROM invoices")
    total_kwh_billed = cursor.fetchone()[0]
    avg_khr_per_kwh = round(total_khr / total_kwh_billed) if total_kwh_billed > 0 else 610

    # Monthly revenue breakdown
    cursor.execute("""
        SELECT billing_month,
               COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN total_khr ELSE 0 END), 0) as paid_sum,
               COALESCE(SUM(CASE WHEN payment_status != 'paid' THEN total_khr ELSE 0 END), 0) as unpaid_sum
        FROM invoices
        GROUP BY billing_month
        ORDER BY billing_month ASC
    """)
    month_rows = cursor.fetchall()
    chart_months = [r["billing_month"] for r in month_rows]
    chart_paid_data = [r["paid_sum"] for r in month_rows]
    chart_unpaid_data = [r["unpaid_sum"] for r in month_rows]

    # Category breakdown
    cursor.execute("""
        SELECT c.category, COALESCE(SUM(i.total_khr), 0) as sum_khr
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        GROUP BY c.category
    """)
    cat_rows = cursor.fetchall()
    cat_residential_khr = 0
    cat_commercial_khr = 0
    for r in cat_rows:
        if r["category"] == "residential":
            cat_residential_khr = r["sum_khr"]
        else:
            cat_commercial_khr = r["sum_khr"]

    # Debtors list
    cursor.execute("""
        SELECT i.*, c.full_name as customer_name, c.phone, c.meter_id, c.area
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE i.payment_status IN ('unpaid', 'overdue')
        ORDER BY i.due_date ASC
    """)
    debtors = cursor.fetchall()

    conn.close()

    return render_template(
        "reports.html",
        total_collected_khr=total_collected_khr,
        total_collected_usd=total_collected_usd,
        total_debt_khr=total_debt_khr,
        total_debt_usd=total_debt_usd,
        unpaid_count=unpaid_count,
        collection_rate=collection_rate,
        avg_khr_per_kwh=avg_khr_per_kwh,
        chart_months=chart_months,
        chart_paid_data=chart_paid_data,
        chart_unpaid_data=chart_unpaid_data,
        cat_residential_khr=cat_residential_khr,
        cat_commercial_khr=cat_commercial_khr,
        debtors=debtors
    )

@app.route("/reports/export-debtors-csv")
def export_debtors_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.invoice_no, c.full_name, c.meter_id, c.phone, c.area, i.billing_month, i.total_khr, i.total_usd, i.due_date, i.payment_status
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE i.payment_status IN ('unpaid', 'overdue')
        ORDER BY i.due_date ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    # Add UTF-8 BOM so Excel opens Khmer characters cleanly
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["លេខវិក័យប័ត្រ", "ឈ្មោះអតិថិជន", "លេខកុងទ័រ", "លេខទូរស័ព្ទ", "តំបន់", "ខែ", "ទឹកប្រាក់ (KHR)", "ទឹកប្រាក់ (USD)", "កាលកំណត់បង់", "ស្ថានភាព"])

    for r in rows:
        writer.writerow([
            r["invoice_no"], r["full_name"], r["meter_id"], r["phone"], r["area"],
            r["billing_month"], r["total_khr"], r["total_usd"], r["due_date"], r["payment_status"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=EDC_Debtors_Report.csv"}
    )

@app.route("/notifications")
def notifications_page():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications ORDER BY id DESC")
    notifications = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM invoices WHERE payment_status IN ('unpaid', 'overdue')")
    unpaid_count = cursor.fetchone()[0]

    conn.close()
    return render_template("notifications.html", notifications=notifications, unpaid_count=unpaid_count)

@app.route("/api/notifications/send", methods=["POST"])
def api_send_notification():
    data = request.json or {}
    ntype = data.get("type", "payment_reminder")
    title = data.get("title", "").strip()
    message = data.get("message", "").strip()
    target_value = data.get("target_value", "all")
    channel = data.get("channel", "Telegram")

    if not title or not message:
        return jsonify({"success": False, "error": "សូមបញ្ចូលចំណងជើង និងខ្លឹមសារសារ!"}), 400

    target_type = "area" if "ភ្នំពេញ" in target_value or "សៀមរាប" in target_value or "បាត់ដំបង" in target_value else ("individual" if target_value.isdigit() or target_value.startswith("0") else "all")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notifications (type, title, message, target_type, target_value, channel, status)
        VALUES (?, ?, ?, ?, ?, ?, 'sent')
    """, (ntype, title, message, target_type, target_value, channel))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1")
    app.run(host="0.0.0.0", port=port, debug=debug)
