import sqlite3
import os
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cam_edc.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Customers Table (មុខងារគ្រប់គ្រងអតិថិជន)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        national_id TEXT,
        address TEXT NOT NULL,
        area TEXT NOT NULL,
        meter_id TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL DEFAULT 'residential', -- 'residential' (លំនៅឋាន) ឬ 'commercial' (អាជីវកម្ម)
        phase TEXT NOT NULL DEFAULT '1-Phase 220V',  -- '1-Phase 220V' ឬ '3-Phase 380V'
        initial_reading REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'active',        -- 'active' (កំពុងប្រើប្រាស់) ឬ 'inactive' (ផ្អាកផ្គត់ផ្គង់)
        status_reason TEXT,
        status_updated_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Meter Readings Table (មុខងារគ្រប់គ្រងការប្រើប្រាស់ និងកុងទ័រ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meter_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        reading_month TEXT NOT NULL, -- ឧទាហរណ៍ '2026-08'
        previous_reading REAL NOT NULL,
        current_reading REAL NOT NULL,
        usage_kwh REAL NOT NULL,
        reading_date DATE NOT NULL,
        reading_type TEXT NOT NULL DEFAULT 'manual', -- 'manual' ឬ 'smart_meter'
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );
    """)

    # 3. Invoices Table (មុខងារវិក័យប័ត្រ និងការទូទាត់)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        reading_id INTEGER,
        billing_month TEXT NOT NULL,
        usage_kwh REAL NOT NULL,
        base_amount_khr REAL NOT NULL,
        maintenance_fee_khr REAL NOT NULL DEFAULT 2000.0,
        total_khr REAL NOT NULL,
        total_usd REAL NOT NULL,
        due_date DATE NOT NULL,
        payment_status TEXT NOT NULL DEFAULT 'unpaid', -- 'unpaid', 'paid', 'overdue'
        payment_date DATETIME,
        payment_method TEXT, -- 'KHQR', 'ABA Pay', 'Wing', 'Cash'
        payment_reference TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (reading_id) REFERENCES meter_readings(id) ON DELETE SET NULL
    );
    """)

    # 4. Notifications Table (របាយការណ៍ និងការជូនដំណឹង)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL, -- 'payment_reminder', 'outage_notice', 'status_change'
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        target_type TEXT NOT NULL DEFAULT 'all', -- 'all', 'area', 'individual'
        target_value TEXT,
        channel TEXT NOT NULL DEFAULT 'Telegram', -- 'Telegram', 'SMS', 'Broadcast'
        status TEXT NOT NULL DEFAULT 'sent',
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Admins Table (គណនីអ្នកគ្រប់គ្រងប្រព័ន្ធ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Super Admin',
        last_login DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Check and seed default admin account
    cursor.execute("SELECT COUNT(*) FROM admins")
    if cursor.fetchone()[0] == 0:
        default_hash = generate_password_hash("admin123")
        cursor.execute("""
            INSERT INTO admins (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        """, ("admin", default_hash, "អ្នកគ្រប់គ្រងប្រព័ន្ធ (Admin EDC)", "អគ្គនាយកប្រព័ន្ធ (Super Admin)"))

    # Auto migrations for additional EDC fields
    cols_admins = [c[1] for c in cursor.execute("PRAGMA table_info(admins)").fetchall()]
    if "status" not in cols_admins:
        cursor.execute("ALTER TABLE admins ADD COLUMN status TEXT NOT NULL DEFAULT 'active';")
    if "phone" not in cols_admins:
        cursor.execute("ALTER TABLE admins ADD COLUMN phone TEXT;")
    if "approved_by" not in cols_admins:
        cursor.execute("ALTER TABLE admins ADD COLUMN approved_by TEXT;")
    if "approved_at" not in cols_admins:
        cursor.execute("ALTER TABLE admins ADD COLUMN approved_at DATETIME;")
    if "notes" not in cols_admins:
        cursor.execute("ALTER TABLE admins ADD COLUMN notes TEXT;")

    cursor.execute("UPDATE admins SET status = 'active' WHERE username = 'admin' AND (status IS NULL OR status = '');")

    cols_customers = [c[1] for c in cursor.execute("PRAGMA table_info(customers)").fetchall()]
    if "street" not in cols_customers:
        cursor.execute("ALTER TABLE customers ADD COLUMN street TEXT;")
    if "location_code" not in cols_customers:
        cursor.execute("ALTER TABLE customers ADD COLUMN location_code TEXT;")

    cols_readings = [c[1] for c in cursor.execute("PRAGMA table_info(meter_readings)").fetchall()]
    if "multiplier" not in cols_readings:
        cursor.execute("ALTER TABLE meter_readings ADD COLUMN multiplier REAL DEFAULT 1.0;")
    if "reading_by" not in cols_readings:
        cursor.execute("ALTER TABLE meter_readings ADD COLUMN reading_by TEXT DEFAULT 'បុគ្គលិក EDC';")
    if "billing_cycle" not in cols_readings:
        cursor.execute("ALTER TABLE meter_readings ADD COLUMN billing_cycle TEXT DEFAULT 'ដុំទី ១';")
    if "date_from" not in cols_readings:
        cursor.execute("ALTER TABLE meter_readings ADD COLUMN date_from DATE;")
    if "date_to" not in cols_readings:
        cursor.execute("ALTER TABLE meter_readings ADD COLUMN date_to DATE;")

    conn.commit()
    conn.close()


def verify_admin_credentials(username, password):
    """ផ្ទៀងផ្ទាត់ឈ្មោះគណនី និងលេខសម្ងាត់របស់អ្នកគ្រប់គ្រង និងពិនិត្យស្ថានភាពអនុម័ត"""
    if not username or not password:
        return {"success": False, "status": "invalid", "message": "សូមបញ្ចូលឈ្មោះគណនី និងលេខសម្ងាត់!"}
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE username = ?", (username.strip(),))
    admin = cursor.fetchone()
    
    if not admin or not check_password_hash(admin["password_hash"], password.strip()):
        conn.close()
        return {"success": False, "status": "invalid", "message": "ឈ្មោះគណនី ឬលេខសម្ងាត់មិនត្រឹមត្រូវ! សូមព្យាយាមម្តងទៀត។"}
    
    admin_status = admin["status"] if "status" in admin.keys() and admin["status"] else "active"
    
    if admin_status == "pending":
        conn.close()
        return {
            "success": False, 
            "status": "pending", 
            "message": "គណនីរបស់អ្នកកំពុងស្ថិតក្នុងការរង់ចាំការអនុម័តពី Admin (Pending Approval)! សូមទាក់ទងអ្នកគ្រប់គ្រងដើម្បីពិនិត្យអនុម័ត។"
        }
    
    if admin_status == "rejected":
        conn.close()
        return {
            "success": False, 
            "status": "rejected", 
            "message": "គណនីរបស់អ្នកត្រូវបានបដិសេធ (Account Rejected)! សូមទាក់ទងផ្នែករដ្ឋបាល EDC ប្រសិនបើមានបញ្ហា។"
        }
    
    if admin_status in ("suspended", "inactive"):
        conn.close()
        return {
            "success": False, 
            "status": "suspended", 
            "message": "គណនីរបស់អ្នកត្រូវបានផ្អាកដំណើរការបណ្តោះអាសន្ន (Suspended Account)!"
        }
    
    # Status is active -> Update last login
    cursor.execute("UPDATE admins SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (admin["id"],))
    conn.commit()
    admin_dict = dict(admin)
    conn.close()
    return {"success": True, "status": "active", "user": admin_dict}


def get_admin_by_id(admin_id):
    """ទាញយកព័ត៌មាន Admin តាម ID"""
    if not admin_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, role, status, phone, last_login, created_at FROM admins WHERE id = ?", (admin_id,))
    admin = cursor.fetchone()
    conn.close()
    return dict(admin) if admin else None


# =========================================================
# USER MANAGEMENT & APPROVAL FUNCTIONS (មុខងារគ្រប់គ្រង & អនុម័ត)
# =========================================================

def register_user_request(username, password, full_name, phone, role):
    """ចុះឈ្មោះស្នើសុំគណនីថ្មី (Status = 'pending' រង់ចាំការអនុម័ត)"""
    username = username.strip().lower()
    full_name = full_name.strip()
    phone = phone.strip()
    role = role.strip() if role else "បុគ្គលិកកត់ត្រាការប្រើប្រាស់"

    if not username or not password or not full_name:
        return False, "សូមបំពេញព័ត៌មានចាំបាច់ឱ្យបានគ្រប់ជ្រុងជ្រោយ!"

    conn = get_db()
    cursor = conn.cursor()
    
    # Check if username already exists
    cursor.execute("SELECT id FROM admins WHERE LOWER(username) = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return False, f"ឈ្មោះគណនី '{username}' នេះមានក្នុងប្រព័ន្ធរួចហើយ! សូមជ្រើសរើសឈ្មោះគណនីផ្សេង។"

    password_hash = generate_password_hash(password)
    cursor.execute("""
        INSERT INTO admins (username, password_hash, full_name, phone, role, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
    """, (username, password_hash, full_name, phone, role))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return True, new_id


def admin_create_user(username, password, full_name, phone, role, status="active"):
    """Admin បង្កើតគណនីដោយផ្ទាល់ (Status = 'active')"""
    username = username.strip().lower()
    full_name = full_name.strip()
    phone = phone.strip()
    role = role.strip() if role else "បុគ្គលិកទូទៅ"

    if not username or not password or not full_name:
        return False, "សូមបំពេញព័ត៌មានឱ្យបានគ្រប់គ្រាន់!"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM admins WHERE LOWER(username) = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return False, f"ឈ្មោះគណនី '{username}' នេះមានក្នុងប្រព័ន្ធរួចហើយ!"

    password_hash = generate_password_hash(password)
    cursor.execute("""
        INSERT INTO admins (username, password_hash, full_name, phone, role, status, approved_by, approved_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'Admin', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (username, password_hash, full_name, phone, role, status))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return True, new_id


def get_all_users(status_filter=None, search=None):
    """ទាញយកបញ្ជីអ្នកប្រើប្រាស់ទាំងអស់"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT id, username, full_name, phone, role, status, approved_by, approved_at, last_login, created_at FROM admins WHERE 1=1"
    params = []

    if status_filter and status_filter != "all":
        query += " AND status = ?"
        params.append(status_filter)

    if search:
        s = f"%{search.strip()}%"
        query += " AND (full_name LIKE ? OR username LIKE ? OR phone LIKE ? OR role LIKE ?)"
        params.extend([s, s, s, s])

    # Pending first, then newest
    query += " ORDER BY CASE WHEN status = 'pending' THEN 0 ELSE 1 END, id DESC"
    
    cursor.execute(query, params)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users


def approve_user(user_id, admin_name="Admin", role=None):
    """អនុម័តគណនីអ្នកប្រើប្រាស់ (Status = 'active')"""
    conn = get_db()
    cursor = conn.cursor()
    if role:
        cursor.execute("""
            UPDATE admins 
            SET status = 'active', role = ?, approved_by = ?, approved_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (role, admin_name, user_id))
    else:
        cursor.execute("""
            UPDATE admins 
            SET status = 'active', approved_by = ?, approved_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (admin_name, user_id))
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def reject_user(user_id, admin_name="Admin"):
    """បដិសេធការស្នើសុំ (Status = 'rejected')"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE admins 
        SET status = 'rejected', approved_by = ?, approved_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, (admin_name, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def toggle_user_status(user_id):
    """បិទ/បើក ដំណើរការគណនី (Active <-> Suspended)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, status FROM admins WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "រកមិនឃើញគណនីនេះទេ!"
    
    if row["username"] == "admin":
        conn.close()
        return False, "មិនអាចផ្អាកដំណើរការគណនី Admin ចម្បងបានឡើយ!"

    current_status = row["status"] or "active"
    new_status = "suspended" if current_status == "active" else "active"
    
    cursor.execute("UPDATE admins SET status = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return True, new_status


def delete_user(user_id):
    """លុបគណនីអ្នកប្រើប្រាស់"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM admins WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "រកមិនឃើញគណនីនេះទេ!"
    
    if row["username"] == "admin":
        conn.close()
        return False, "មិនអាចលុបគណនី Admin ចម្បងបានឡើយ!"

    cursor.execute("DELETE FROM admins WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True, "បានលុបគណនីដោយជោគជ័យ!"


def get_pending_users_count():
    """ចំនួនគណនីរង់ចាំការអនុម័ត"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admins WHERE status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_user_stats():
    """ស្ថិតិអ្នកប្រើប្រាស់សម្រាប់ KPI cards"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admins")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM admins WHERE status = 'pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM admins WHERE status = 'active'")
    active = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM admins WHERE status IN ('rejected', 'suspended')")
    inactive = cursor.fetchone()[0]

    conn.close()
    return {
        "total": total,
        "pending": pending,
        "active": active,
        "inactive": inactive
    }




# --- EDC Tariff Calculation Helper ---
def calculate_edc_bill(category: str, usage_kwh: float):
    """
    គណនាតម្លៃភ្លើងតាមអត្រាកាំពន្ធស្ដង់ដារ អគ្គិសនីកម្ពុជា (EDC):
    - លំនៅឋាន (Residential):
        * 1-10 kWh: 380 KHR/kWh
        * 11-50 kWh: 480 KHR/kWh
        * 51-200 kWh: 610 KHR/kWh
        * >200 kWh: 730 KHR/kWh
    - អាជីវកម្ម (Commercial):
        * Flat rate 740 KHR/kWh + ថ្លៃថែទាំបណ្តាញ 4,000 KHR
    """
    usage = max(0.0, float(usage_kwh))
    breakdown = []
    base_khr = 0.0
    maintenance_khr = 2000.0 if category == "residential" else 4000.0

    if category == "residential":
        remaining = usage
        tier1 = min(remaining, 10.0)
        cost1 = tier1 * 380.0
        if tier1 > 0:
            breakdown.append({"tier": "1-10 kWh", "kwh": tier1, "rate": 380, "subtotal": cost1})
        remaining -= tier1

        tier2 = min(remaining, 40.0)
        cost2 = tier2 * 480.0
        if tier2 > 0:
            breakdown.append({"tier": "11-50 kWh", "kwh": tier2, "rate": 480, "subtotal": cost2})
        remaining -= tier2

        tier3 = min(remaining, 150.0)
        cost3 = tier3 * 610.0
        if tier3 > 0:
            breakdown.append({"tier": "51-200 kWh", "kwh": tier3, "rate": 610, "subtotal": cost3})
        remaining -= tier3

        tier4 = remaining
        cost4 = tier4 * 730.0
        if tier4 > 0:
            breakdown.append({"tier": "> 200 kWh", "kwh": tier4, "rate": 730, "subtotal": cost4})

        base_khr = cost1 + cost2 + cost3 + cost4
    else:
        # Commercial / អាជីវកម្ម
        rate = 740.0
        base_khr = usage * rate
        breakdown.append({"tier": "អាជីវកម្ម (Flat)", "kwh": usage, "rate": rate, "subtotal": base_khr})

    total_khr = round(base_khr + maintenance_khr)
    usd_rate = 4100.0
    total_usd = round(total_khr / usd_rate, 2)

    return {
        "usage_kwh": usage,
        "category": category,
        "base_khr": base_khr,
        "maintenance_khr": maintenance_khr,
        "total_khr": total_khr,
        "total_usd": total_usd,
        "breakdown": breakdown
    }
