import os
import sqlite3
from datetime import datetime, date
from database import DB_PATH, init_db, calculate_edc_bill

def seed_database():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] > 0:
        print("Database already contains data. Skipping seed.")
        conn.close()
        return

    # 1. Seed Customers
    customers_data = [
        ("EDC-00101", "សុខ សុវណ្ណារ៉ា", "012 889 900", "010293847", "ផ្ទះលេខ ១២A ផ្លូវ ១៧៨ សង្កាត់ជ័យជំនះ", "ភ្នំពេញ - ដូនពេញ", "MTR-88101", "residential", "1-Phase 220V", 120.0, "active", None),
        ("EDC-00102", "ចាន់ ធីតា", "098 765 432", "010884729", "ផ្ទះលេខ ៤៥ ផ្លូវ ២៨៩ សង្កាត់បឹងកក់២", "ភ្នំពេញ - ទួលគោក", "MTR-88102", "residential", "1-Phase 220V", 340.0, "active", None),
        ("EDC-00103", "ហេង វិសាល", "077 123 456", "020993812", "អគារលេខ ៨៨ មហាវិថីព្រះនរោត្តម", "ភ្នំពេញ - ចំការមន", "MTR-88103", "commercial", "3-Phase 380V", 1500.0, "active", None),
        ("EDC-00104", "កែវ សុភា", "089 555 777", "010382910", "ផ្ទះលេខ ៧៣ ផ្លូវជាតិលេខ ៥ សង្កាត់គីឡូម៉ែត្រ៦", "ភ្នំពេញ - ឫស្សីកែវ", "MTR-88104", "residential", "1-Phase 220V", 80.0, "active", None),
        ("EDC-00105", "ក្រុមហ៊ុន កាហ្វេ អង្គរ (សាខាសៀមរាប)", "063 963 888", "030112233", "ភូមិមណ្ឌល១ ឃុំស្វាយដង្គុំ ក្រុងសៀមរាប", "សៀមរាប - ក្រុងសៀមរាប", "MTR-88105", "commercial", "3-Phase 380V", 2800.0, "active", None),
        ("EDC-00106", "រស់ គឹមសាន", "015 332 211", "010472819", "ផ្ទះលេខ ៨ ផ្លូវ ៥៩៨ សង្កាត់ភ្នំពេញថ្មី", "ភ្នំពេញ - សែនសុខ", "MTR-88106", "residential", "1-Phase 220V", 210.0, "active", None),
        ("EDC-00107", "ម៉េង សិរីរ័ត្ន", "092 444 888", "040556677", "ផ្ទះលេខ ១៥ ផ្លូវលេខ ៣ សង្កាត់ស្វាយប៉ោ ក្រុងបាត់ដំបង", "បាត់ដំបង - ក្រុងបាត់ដំបង", "MTR-88107", "residential", "1-Phase 220V", 450.0, "active", None),
        ("EDC-00108", "សេង ចិន្តា (មីនីម៉ាត ២៤)", "011 999 111", "010887766", "ផ្ទះលេខ ៩៩ ផ្លូវកម្ពុជាក្រោម សង្កាត់ផ្សារដេប៉ូ៣", "ភ្នំពេញ - ទួលគោក", "MTR-88108", "commercial", "3-Phase 380V", 3100.0, "active", None),
        ("EDC-00109", "ប៉ែន វ៉ាន់នី", "086 777 222", "010992211", "ផ្ទះលេខ ៦៤ ផ្លូវ ៣៦០ សង្កាត់បឹងកេងកង៣", "ភ្នំពេញ - បឹងកេងកង", "MTR-88109", "residential", "1-Phase 220V", 600.0, "inactive", "ផ្អាកផ្គត់ផ្គង់ដោយសារជំពាក់ប្រាក់លើស ៦០ ថ្ងៃ"),
        ("EDC-00110", "អ៊ុំ សុវត្ថិ", "010 654 321", "010554433", "ផ្ទះលេខ ២១ ផ្លូវលេខ ១ សង្កាត់ផ្សារដើមថ្កូវ", "ភ្នំពេញ - ចំការមន", "MTR-88110", "residential", "1-Phase 220V", 190.0, "active", None),
    ]

    cursor.executemany("""
    INSERT INTO customers (code, full_name, phone, national_id, address, area, meter_id, category, phase, initial_reading, status, status_reason, status_updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, customers_data)

    # Fetch inserted customer ids
    cursor.execute("SELECT id, code, category FROM customers")
    customers_map = {row[1]: (row[0], row[2]) for row in cursor.fetchall()}

    # 2. Seed Meter Readings & Invoices for Months: 2026-06, 2026-07, 2026-08
    # Monthly reading progressions:
    usage_seed = [
        # (cust_code, [(month, prev, curr, date_read, due_date, status, pay_method, pay_date)])
        ("EDC-00101", [
            ("2026-06", 120.0, 245.0, "2026-06-25", "2026-07-10", "paid", "KHQR", "2026-07-02 09:15:00"),
            ("2026-07", 245.0, 395.0, "2026-07-25", "2026-08-10", "paid", "ABA Pay", "2026-08-05 14:20:00"),
            ("2026-08", 395.0, 560.0, "2026-08-25", "2026-09-15", "unpaid", None, None),
        ]),
        ("EDC-00102", [
            ("2026-06", 340.0, 420.0, "2026-06-25", "2026-07-10", "paid", "Wing", "2026-07-08 11:00:00"),
            ("2026-07", 420.0, 510.0, "2026-07-25", "2026-08-10", "paid", "KHQR", "2026-08-02 16:45:00"),
            ("2026-08", 510.0, 615.0, "2026-08-25", "2026-09-15", "paid", "KHQR", "2026-09-02 10:11:00"),
        ]),
        ("EDC-00103", [ # Commercial
            ("2026-06", 1500.0, 2150.0, "2026-06-25", "2026-07-10", "paid", "ABA Pay", "2026-07-05 10:30:00"),
            ("2026-07", 2150.0, 2890.0, "2026-07-25", "2026-08-10", "paid", "ABA Pay", "2026-08-06 09:00:00"),
            ("2026-08", 2890.0, 3680.0, "2026-08-25", "2026-09-15", "unpaid", None, None),
        ]),
        ("EDC-00104", [
            ("2026-06", 80.0, 125.0, "2026-06-25", "2026-07-10", "paid", "Cash", "2026-07-06 13:20:00"),
            ("2026-07", 125.0, 172.0, "2026-07-25", "2026-08-10", "paid", "KHQR", "2026-08-04 15:10:00"),
            ("2026-08", 172.0, 220.0, "2026-08-25", "2026-09-15", "paid", "KHQR", "2026-09-03 08:45:00"),
        ]),
        ("EDC-00105", [ # Commercial Cafe
            ("2026-06", 2800.0, 3950.0, "2026-06-25", "2026-07-10", "paid", "KHQR", "2026-07-04 17:30:00"),
            ("2026-07", 3950.0, 5200.0, "2026-07-25", "2026-08-10", "paid", "ABA Pay", "2026-08-03 10:00:00"),
            ("2026-08", 5200.0, 6520.0, "2026-08-25", "2026-09-15", "unpaid", None, None),
        ]),
        ("EDC-00106", [
            ("2026-07", 210.0, 335.0, "2026-07-25", "2026-08-10", "paid", "KHQR", "2026-08-09 11:25:00"),
            ("2026-08", 335.0, 480.0, "2026-08-25", "2026-09-15", "paid", "ABA Pay", "2026-09-01 14:15:00"),
        ]),
        ("EDC-00107", [
            ("2026-07", 450.0, 560.0, "2026-07-25", "2026-08-10", "paid", "Cash", "2026-08-05 16:00:00"),
            ("2026-08", 560.0, 690.0, "2026-08-25", "2026-09-15", "unpaid", None, None),
        ]),
        ("EDC-00108", [ # Minimart Commercial
            ("2026-07", 3100.0, 4200.0, "2026-07-25", "2026-08-10", "paid", "KHQR", "2026-08-07 10:30:00"),
            ("2026-08", 4200.0, 5380.0, "2026-08-25", "2026-09-15", "unpaid", None, None),
        ]),
        ("EDC-00109", [ # Inactive Overdue
            ("2026-06", 600.0, 810.0, "2026-06-25", "2026-07-10", "overdue", None, None),
            ("2026-07", 810.0, 1030.0, "2026-07-25", "2026-08-10", "overdue", None, None),
        ]),
        ("EDC-00110", [
            ("2026-08", 190.0, 275.0, "2026-08-25", "2026-09-15", "paid", "KHQR", "2026-09-04 12:00:00"),
        ]),
    ]

    inv_counter = 1001
    for cust_code, readings in usage_seed:
        cust_id, category = customers_map[cust_code]
        for r in readings:
            month, prev_r, curr_r, r_date, due_d, p_status, p_method, p_date = r
            usage_kwh = curr_r - prev_r
            r_type = "smart_meter" if "commercial" in category else "manual"

            cursor.execute("""
            INSERT INTO meter_readings (customer_id, reading_month, previous_reading, current_reading, usage_kwh, reading_date, reading_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cust_id, month, prev_r, curr_r, usage_kwh, r_date, r_type, f"កត់ត្រាប្រចាំខែ {month}"))
            reading_id = cursor.lastrowid

            # Calculate billing
            bill = calculate_edc_bill(category, usage_kwh)
            inv_no = f"INV-{month.replace('-', '')}-{inv_counter}"
            inv_counter += 1
            ref_code = f"TXN-{inv_counter}KH" if p_method else None

            cursor.execute("""
            INSERT INTO invoices (invoice_no, customer_id, reading_id, billing_month, usage_kwh, base_amount_khr, maintenance_fee_khr, total_khr, total_usd, due_date, payment_status, payment_date, payment_method, payment_reference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inv_no, cust_id, reading_id, month, usage_kwh,
                bill["base_khr"], bill["maintenance_khr"], bill["total_khr"], bill["total_usd"],
                due_d, p_status, p_date, p_method, ref_code
            ))

    # 3. Seed Sample Notifications
    notifications_data = [
        ("payment_reminder", "រំលឹកបង់ប្រាក់វិក័យប័ត្រប្រចាំខែសីហា ២០២៦", "សូមគោរពរំលឹកអតិថិជនមេត្តាជ្រាបថា វិក័យប័ត្រអគ្គិសនីប្រចាំខែ ០៨/២០២៦ នឹងដល់កាលកំណត់បង់ត្រឹមថ្ងៃទី ១៥ ខែកញ្ញា ឆ្នាំ២០២៦។ លោកអ្នកអាចស្កេនបង់តាម KHQR ឬ ABA Pay ដោយឥតគិតថ្លៃសេវា។", "all", None, "Telegram", "sent", "2026-09-01 08:30:00"),
        ("outage_notice", "សេចក្តីជូនដំណឹង៖ ផ្អាកការផ្គត់ផ្គង់អគ្គិសនីបណ្តោះអាសន្ន ដើម្បីជួសជុលបណ្តាញ", "អគ្គិសនីកម្ពុជា (EDC) សូមជម្រាបជូនដំណឹងដល់អតិថិជននៅតំបន់ ដូនពេញ (ផ្លូវ ១៧៨ និងក្បែរវត្តឧណ្ណាលោម) ថានឹងមានការផ្អាកចរន្តអគ្គិសនីបណ្តោះអាសន្ននៅថ្ងៃទី ១៤ ខែកញ្ញា ឆ្នាំ២០២៦ ពីម៉ោង ០៨:០០ ព្រឹក ដល់ម៉ោង ១២:០០ ថ្ងៃត្រង់ ដើម្បីជួសជុល និងតភ្ជាប់ខ្សែបណ្តាញតង់ស្យុងមធ្យមថ្មី។ សូមអភ័យទោសចំពោះការរំខាន។", "area", "ភ្នំពេញ - ដូនពេញ", "Telegram", "sent", "2026-09-08 14:00:00"),
        ("payment_reminder", "រំលឹកបង់ប្រាក់បំណុលហួសកាលកំណត់ (អតិថិជន ប៉ែន វ៉ាន់នី)", "វិក័យប័ត្រលេខ INV-202607-1014 របស់លោកអ្នកបានហួសកាលកំណត់លើសពី ៣០ ថ្ងៃ។ សូមមេត្តាទូទាត់ជាបន្ទាន់ដើម្បីជៀសវាងការផ្អាកការផ្គត់ផ្គង់អគ្គិសនីជាបន្ត។", "individual", "9", "SMS", "sent", "2026-09-05 10:00:00")
    ]

    cursor.executemany("""
    INSERT INTO notifications (type, title, message, target_type, target_value, channel, status, sent_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, notifications_data)

    conn.commit()
    conn.close()
    print("Database seeded successfully with Cambodian EDC sample records!")

if __name__ == "__main__":
    seed_database()
