from flask import Flask, render_template, request, redirect, session, flash, url_for
from db_connect_test import get_connection

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------- CHECK DB CONNECTION ----------
@app.before_request
def check_db():
    try:
        conn = get_connection()
        conn.close()
    except Exception as e:
        print("⚠️ DB connection failed:", e)
        return "<h3>Database not connected properly. Check db_connect_test.py</h3>"

@app.route('/dbtest')
def dbtest():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SHOW TABLES;")
        tables = [t[0] for t in cur.fetchall()]
        cur.close()
        conn.close()
        return f"<h3>Connected!</h3><p>Tables: {tables}</p>"
    except Exception as e:
        return f"<h3>DB Connection Error:</h3> {e}"

# ---------- LOGIN ----------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        user = None

        # --- ADMIN LOGIN ---
        if role == "admin":
            cur.execute("SELECT * FROM admin WHERE email=%s AND password=%s", (email, password))
            user = cur.fetchone()
            if user:
                session['role'] = 'admin'
                session['email'] = user['email']
                cur.close()
                conn.close()
                return redirect('/admin')

        # --- STAFF LOGIN ---
        elif role == "staff":
            cur.execute("SELECT * FROM staff WHERE email=%s AND password=%s", (email, password))
            user = cur.fetchone()
            if user:
                session['role'] = 'staff'
                session['email'] = user['email']
                session['staff_id'] = user['staff_id']
                cur.close()
                conn.close()
                return redirect('/staff')

        # --- CUSTOMER LOGIN ---
        elif role == "customer":
            cur.execute("SELECT * FROM customer WHERE email=%s AND password=%s", (email, password))
            user = cur.fetchone()
            if user:
                session['role'] = 'customer'
                session['email'] = user['email']
                session['customer_id'] = user['customer_id']
                cur.close()
                conn.close()
                return redirect('/customer')

        # --- INVALID CREDENTIALS ---
        cur.close()
        conn.close()
        flash("❌ Incorrect email or password combination", "danger")
        return redirect('/login')

    return render_template("login.html")

@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')

# ---------- ADMIN DASHBOARD ----------
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect('/')
    return render_template("admin_dashboard.html")

# ---------- VIEW TABLE ----------
@app.route('/admin/view/<table>')
def view_table(table):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(f"SELECT * FROM {table}")
    records = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    return render_template('view.html', table=table, columns=columns, records=records)

# ---------- ADD RECORD ----------
@app.route('/admin/add/<table>', methods=['GET', 'POST'])
def add_record(table):
    if session.get('role') != 'admin':
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(f"SHOW COLUMNS FROM {table}")
    columns = cur.fetchall()

    fk_data = {}

    # Populate dropdowns for related tables
    if table == "staff_schedule":
        cur.execute("SELECT staff_id, name FROM staff")
        fk_data["staffs"] = cur.fetchall()

    elif table == "admin":
        cur.execute("SELECT theatre_id, theatre_name FROM theatre")
        fk_data["theatres"] = cur.fetchall()

    elif table == "screen":
        cur.execute("SELECT theatre_id, theatre_name FROM theatre")
        fk_data["theatres"] = cur.fetchall()

    elif table == "showtime":
        cur.execute("SELECT movie_id, title FROM movie")
        fk_data["movies"] = cur.fetchall()
        cur.execute("SELECT screen_id, screen_name FROM screen")
        fk_data["screens"] = cur.fetchall()

    elif table == "booking":
        cur.execute("SELECT showtime_id FROM showtime")
        fk_data["showtimes"] = cur.fetchall()
        cur.execute("SELECT customer_id, name FROM customer")
        fk_data["customers"] = cur.fetchall()

    # Handle POST
    if request.method == 'POST':
        data = request.form.to_dict()
        fields, values = [], []

        for col in columns:
            if 'auto_increment' in col['Extra']:
                continue
            key = col['Field']
            if key in data:
                fields.append(key)
                values.append(data[key])

        placeholders = ','.join(['%s'] * len(values))
        sql = f"INSERT INTO {table} ({','.join(fields)}) VALUES ({placeholders})"

        try:
            cur.execute(sql, values)
            conn.commit()
            flash("✅ Record added successfully!", "success")
            return redirect(url_for('view_table', table=table))
        except Exception as e:
            flash(f"❌ Error adding record: {e}", "danger")

    cur.close()
    conn.close()
    return render_template('add_edit_record.html', table=table, columns=columns, record=None, fk_data=fk_data)

# ---------- EDIT RECORD ----------
@app.route('/admin/edit/<table>/<int:record_id>', methods=['GET', 'POST'])
def edit_record(table, record_id):
    if session.get('role') != 'admin':
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(f"SHOW COLUMNS FROM {table}")
    columns = cur.fetchall()

    pk = next((c["Field"] for c in columns if c["Key"] == "PRI"), None)
    if not pk:
        flash("No primary key found", "danger")
        return redirect(url_for('view_table', table=table))

    fk_data = {}

    # Load foreign key dropdowns for editing
    if table == "staff_schedule":
        cur.execute("SELECT staff_id, name FROM staff")
        fk_data["staffs"] = cur.fetchall()

    if request.method == 'POST':
        data = request.form.to_dict()
        updates = [f"{k}=%s" for k in data.keys()]
        values = list(data.values()) + [record_id]
        sql = f"UPDATE {table} SET {', '.join(updates)} WHERE {pk}=%s"

        try:
            cur.execute(sql, values)
            conn.commit()
            flash("✅ Record updated successfully!", "success")
            return redirect(url_for('view_table', table=table))
        except Exception as e:
            flash(f"❌ Error updating record: {e}", "danger")

    cur.execute(f"SELECT * FROM {table} WHERE {pk}=%s", (record_id,))
    record = cur.fetchone()

    cur.close()
    conn.close()
    return render_template('add_edit_record.html', table=table, columns=columns, record=record, fk_data=fk_data)

# ---------- DELETE RECORD ----------
@app.route('/admin/delete/<table>/<int:record_id>')
def delete_record(table, record_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Get primary key column dynamically
    cur.execute(f"SHOW KEYS FROM {table} WHERE Key_name = 'PRIMARY'")
    pk = cur.fetchone()['Column_name']

    try:
        cur.execute(f"DELETE FROM {table} WHERE {pk} = %s", (record_id,))
        conn.commit()
        flash("🗑 Record deleted successfully!", "success")
    except Exception as e:
        flash(f"❌ Delete failed: {e}", "danger")

    cur.close()
    conn.close()
    return redirect(url_for('view_table', table=table))

# ---------- MANAGE ADMINS ----------
@app.route('/admin/manage_admins')
def manage_admins():
    if session.get('role') != 'admin':
        return redirect('/')
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM admin")
    admins = cur.fetchall()
    cur.execute("SELECT theatre_id, theatre_name FROM theatre")
    theatres = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manage_admins.html', admins=admins, theatres=theatres)

@app.route('/admin/add_admin', methods=['POST'])
def add_admin():
    name = request.form['username']
    email = request.form['email']
    password = request.form['password']
    theatre_id = request.form.get('theatre_id') or None

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO admin (name, email, password, theatre_id) VALUES (%s, %s, %s, %s)",
            (name, email, password, theatre_id)
        )
        conn.commit()
        flash("✅ Admin added successfully!", "success")
    except Exception as e:
        flash(f"❌ Error: {e}", "danger")
    finally:
        conn.close()
    return redirect('/admin/manage_admins')

@app.route('/admin/delete_admin/<int:admin_id>')
def delete_admin(admin_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM admin WHERE admin_id=%s", (admin_id,))
        conn.commit()
        flash("🗑️ Admin deleted!", "success")
    except Exception as e:
        flash(f"❌ Error: {e}", "danger")
    finally:
        conn.close()
    return redirect('/admin/manage_admins')

# ---------- MANAGE STAFF (with schedule info) ----------
@app.route('/admin/manage_staff')
def manage_staff():
    if session.get('role') != 'admin':
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT s.staff_id, s.name, t.theatre_name,
               ss.schedule_id, ss.work_date, ss.day, ss.start_time, ss.end_time
        FROM staff s
        LEFT JOIN theatre t ON s.theatre_id = t.theatre_id
        LEFT JOIN staff_schedule ss ON s.staff_id = ss.staff_id
        ORDER BY s.staff_id, ss.work_date DESC
    """)
    staff_data = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("manage_staff.html", staff_data=staff_data)

# ---------- EDIT STAFF SCHEDULE ----------
@app.route('/admin/edit_staff_schedule/<int:schedule_id>', methods=['GET', 'POST'])
def edit_staff_schedule(schedule_id):
    if session.get('role') != 'admin':
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        work_date = request.form.get('work_date')
        day = request.form.get('day')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        cur.execute("""
            UPDATE staff_schedule 
            SET work_date=%s, day=%s, start_time=%s, end_time=%s
            WHERE schedule_id=%s
        """, (work_date, day, start_time, end_time, schedule_id))
        conn.commit()
        cur.close()
        conn.close()
        flash("✅ Schedule updated successfully!", "success")
        return redirect('/admin/manage_staff')

    cur.execute("SELECT * FROM staff_schedule WHERE schedule_id=%s", (schedule_id,))
    schedule = cur.fetchone()
    cur.close()
    conn.close()

    return render_template("edit_staff_schedule.html", schedule=schedule)

# ---------- DELETE STAFF SCHEDULE ----------
@app.route('/admin/delete_staff_schedule/<int:schedule_id>')
def delete_staff_schedule(schedule_id):
    if session.get('role') != 'admin':
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM staff_schedule WHERE schedule_id=%s", (schedule_id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("🗑 Schedule deleted successfully!", "success")
    return redirect('/admin/manage_staff')

# ---------- STAFF DASHBOARD ----------
@app.route('/staff')
def staff_dashboard():
    if session.get('role') != 'staff':
        return redirect('/')

    staff_id = session.get('staff_id')
    if not staff_id:
        flash("⚠️ Staff ID missing from session!", "danger")
        return redirect('/login')

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Get staff info with theatre name
    cur.execute("""
        SELECT s.*, t.theatre_name
        FROM staff s
        LEFT JOIN theatre t ON s.theatre_id = t.theatre_id
        WHERE s.staff_id = %s
    """, (staff_id,))
    staff = cur.fetchone()

    if not staff:
        cur.close()
        conn.close()
        flash("⚠️ Staff record not found!", "danger")
        return redirect('/login')

    # Get today's working schedule
    cur.execute("""
        SELECT * FROM staff_schedule
        WHERE staff_id = %s AND work_date = CURDATE()
    """, (staff_id,))
    work = cur.fetchone()

    # Get today's movie schedule for that theatre (if assigned)
    shows = []
    if staff.get('theatre_id'):
        cur.execute("""
            SELECT m.title, sc.screen_name, sh.show_time
            FROM showtime sh
            JOIN movie m ON sh.movie_id = m.movie_id
            JOIN screen sc ON sh.screen_id = sc.screen_id
            WHERE sc.theatre_id = %s AND sh.show_date = CURDATE()
        """, (staff['theatre_id'],))
        shows = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('staff_dashboard.html', staff=staff, work=work, shows=shows)

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = None
    category = None

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')

        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        # Check if email already exists
        cur.execute("SELECT * FROM customer WHERE email = %s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            message = "⚠️ You already have an account — please log in now."
            category = "warning"
        else:
            cur.execute("""
                INSERT INTO customer (name, email, phone, password)
                VALUES (%s, %s, %s, %s)
            """, (name, email, phone, password))
            conn.commit()
            message = "✅ Registered successfully! You can now log in."
            category = "success"

        cur.close()
        conn.close()

    return render_template("register.html", message=message, category=category)

# ---------- CUSTOMER DASHBOARD ----------
@app.route('/customer')
def customer_dashboard():
    if session.get('role') != 'customer':
        return redirect('/login')

    customer_email = session.get('email')
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch customer info
    cur.execute("SELECT * FROM customer WHERE email = %s", (customer_email,))
    customer = cur.fetchone()

    # Fetch available shows (upcoming)
    cur.execute("""
        SELECT sh.showtime_id, m.title, t.theatre_name, s.screen_name, 
               sh.show_date, sh.show_time, sh.price
        FROM showtime sh
        JOIN movie m ON sh.movie_id = m.movie_id
        JOIN screen s ON sh.screen_id = s.screen_id
        JOIN theatre t ON s.theatre_id = t.theatre_id
        WHERE sh.show_date >= CURDATE()
        ORDER BY sh.show_date, sh.show_time
    """)
    shows = cur.fetchall()

    # ✅ Fixed query for bookings (compatible with ONLY_FULL_GROUP_BY)
    cur.execute("""
        SELECT 
            b.booking_id,
            m.title,
            t.theatre_name,
            s.screen_name,
            sh.show_date,
            sh.show_time,
            ANY_VALUE(p.amount) AS amount,
            ANY_VALUE(p.status) AS status,
            GROUP_CONCAT(se.seat_number ORDER BY se.seat_number) AS seat_numbers
        FROM booking b
        JOIN showtime sh ON b.showtime_id = sh.showtime_id
        JOIN movie m ON sh.movie_id = m.movie_id
        JOIN screen s ON sh.screen_id = s.screen_id
        JOIN theatre t ON s.theatre_id = t.theatre_id
        LEFT JOIN payment p ON b.booking_id = p.booking_id
        JOIN bookedseat bs ON b.booking_id = bs.booking_id
        JOIN seat se ON bs.seat_id = se.seat_id
        WHERE b.customer_id = %s
        GROUP BY b.booking_id
        ORDER BY b.booking_id DESC
    """, (customer['customer_id'],))
    bookings = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('customer_dashboard.html', customer=customer, shows=shows, bookings=bookings)

# ---------- CANCEL BOOKING ----------
@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if session.get('role') != 'customer':
        return redirect('/login')

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Free booked seats
        cur.execute("DELETE FROM bookedseat WHERE booking_id = %s", (booking_id,))

        # Update booking and payment status
        cur.execute("UPDATE booking SET status = 'Cancelled' WHERE booking_id = %s", (booking_id,))
        cur.execute("UPDATE payment SET status = 'Refunded' WHERE booking_id = %s", (booking_id,))

        conn.commit()
        flash("✅ Booking cancelled successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash("❌ Error while cancelling booking: " + str(e), "danger")

    finally:
        cur.close()
        conn.close()

    return redirect('/customer')

@app.route('/book/<int:show_id>', methods=['GET', 'POST'])
def book_ticket(show_id):
    # Ensure only customers can book
    if session.get('role') != 'customer':
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # 🎬 Get show details
    cur.execute("""
        SELECT sh.showtime_id, m.title, t.theatre_name, s.screen_name,
               s.screen_id, sh.show_date, sh.show_time, sh.price
        FROM showtime sh
        JOIN movie m ON sh.movie_id = m.movie_id
        JOIN screen s ON sh.screen_id = s.screen_id
        JOIN theatre t ON s.theatre_id = t.theatre_id
        WHERE sh.showtime_id = %s
    """, (show_id,))
    show = cur.fetchone()

    # ❌ If no show found
    if not show:
        cur.close()
        conn.close()
        return "<h4>❌ Show not found.</h4><a href='/customer'>Back</a>"

    # 💺 Fetch all seats for that screen
    cur.execute("SELECT seat_id, seat_number FROM seat WHERE screen_id = %s", (show['screen_id'],))
    all_seats = cur.fetchall()

    # 🚫 Fetch already booked seats for this showtime
    cur.execute("""
        SELECT bs.seat_id
        FROM bookedseat bs
        JOIN booking b ON bs.booking_id = b.booking_id
        WHERE b.showtime_id = %s
    """, (show_id,))
    booked_seat_ids = [r['seat_id'] for r in cur.fetchall()]

    message = None

    # 🧾 Handle form submission (seat booking)
    if request.method == 'POST':
        seat_ids_str = request.form.get('seat_ids', '').strip()

        if not seat_ids_str:
            message = "⚠️ Please select at least one seat."
        else:
            # Convert seat IDs to list of ints
            try:
                seat_list = [int(sid) for sid in seat_ids_str.split(',') if sid.strip()]
            except ValueError:
                seat_list = []
            
            if not seat_list:
                message = "⚠️ Invalid seat selection."
            else:
                customer_id = session.get('customer_id')

                # Re-check booked seats to prevent race conditions
                cur.execute("""
                    SELECT bs.seat_id
                    FROM bookedseat bs
                    JOIN booking b ON bs.booking_id = b.booking_id
                    WHERE b.showtime_id = %s
                """, (show_id,))
                latest_booked_ids = [r['seat_id'] for r in cur.fetchall()]

                # Filter out any seats that just got booked
                available_seats = [sid for sid in seat_list if sid not in latest_booked_ids]

                if not available_seats:
                    message = "❌ All selected seats have already been booked. Please try again."
                else:
                    # 1️⃣ Create booking record
                    cur.execute("""
                        INSERT INTO booking (showtime_id, customer_id, booking_date)
                        VALUES (%s, %s, CURDATE())
                    """, (show_id, customer_id))
                    conn.commit()
                    booking_id = cur.lastrowid

                    # 2️⃣ Insert each selected seat
                    for seat_id in available_seats:
                        cur.execute(
                            "INSERT INTO bookedseat (booking_id, seat_id) VALUES (%s, %s)",
                            (booking_id, seat_id)
                        )
                    conn.commit()

                    # 3️⃣ Payment record
                    price_per_ticket = show.get('price') or 150.0
                    total_amount = len(available_seats) * price_per_ticket

                    cur.execute("""
                        INSERT INTO payment (booking_id, amount, payment_date, status)
                        VALUES (%s, %s, CURDATE(), 'Success')
                    """, (booking_id, total_amount))
                    conn.commit()

                    message = f"✅ Booking successful! You booked {len(available_seats)} seats. Total ₹{total_amount:.2f}."

    cur.close()
    conn.close()

    return render_template(
        'book_ticket.html',
        show=show,
        all_seats=all_seats,
        booked_seat_ids=booked_seat_ids,
        message=message
    )

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()  # Clear all user session data
    flash("👋 Logged out successfully!", "info")
    return redirect('/login')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000,debug=False)
