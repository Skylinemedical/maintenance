from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # เปลี่ยนเป็นรหัสลับของคุณ
STAFF_PASSWORD = '1234'  # กำหนดรหัสผ่าน staff ที่ต้องการ

DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fname TEXT NOT NULL,
            lname TEXT NOT NULL,
            phone TEXT NOT NULL,
            date TEXT NOT NULL,
            service_type TEXT NOT NULL,
            problem TEXT DEFAULT 'ปกติ',
            status TEXT DEFAULT 'รอดำเนินการ',
            model TEXT,
            serial_number TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS available_dates (
            date TEXT PRIMARY KEY
        )
    ''')
    c.execute("SELECT COUNT(*) FROM available_dates")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO available_dates (date) VALUES (?)", [
            ('2025-06-01',),
            ('2025-06-03',),
            ('2025-06-05',)
        ])
    conn.commit()
    conn.close()

def alter_table():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE registrations ADD COLUMN model TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE registrations ADD COLUMN serial_number TEXT")
    except:
        pass
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def register():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT date FROM available_dates ORDER BY date')
    allowed_dates = [row['date'] for row in c.fetchall()]

    if request.method == 'POST':
        fname = request.form['fname'].strip()
        lname = request.form['lname'].strip()
        phone = request.form['phone'].strip()
        date = request.form['date']
        service_type = request.form['service_type']

        if not phone.isdigit() or len(phone) < 9 or len(phone) > 12:
            flash("กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง (9-12 หลัก) ครับ")
            conn.close()
            return redirect(url_for('register'))

        if date not in allowed_dates:
            flash("วันดังกล่าวไม่ได้เปิดให้บริการ กรุณาเลือกวันใหม่ 🙏")
            conn.close()
            return redirect(url_for('register'))

        if service_type == 'ทำความสะอาด':
            c.execute('SELECT COUNT(*) FROM registrations WHERE date = ? AND service_type = ?', (date, 'ทำความสะอาด'))
            count_cleaning = c.fetchone()[0]
            if count_cleaning >= 10:
                flash("วันนี้รับเครื่องทำความสะอาดครบ 10 เครื่องแล้ว กรุณาเลือกวันอื่น 🙏")
                conn.close()
                return redirect(url_for('register'))

        c.execute('SELECT COUNT(*) FROM registrations WHERE phone = ? AND date = ?', (phone, date))
        already_registered = c.fetchone()[0]
        if already_registered > 0:
            flash("คุณได้ลงทะเบียนไว้แล้วในวันเดียวกัน ไม่สามารถลงทะเบียนซ้ำได้ 🙏")
            conn.close()
            return redirect(url_for('register'))

        c.execute('''
            INSERT INTO registrations (fname, lname, phone, date, service_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (fname, lname, phone, date, service_type))
        conn.commit()
        conn.close()
        flash("ลงทะเบียนเรียบร้อยแล้ว ✅")
        return redirect(url_for('success'))

    conn.close()
    return render_template('register.html', allowed_dates=allowed_dates)

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/check_status', methods=['GET', 'POST'])
def check_status():
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        conn = get_db_connection()
        registrations = conn.execute(
            'SELECT * FROM registrations WHERE phone = ? ORDER BY date', (phone,)
        ).fetchall()
        conn.close()
        return render_template('check_status_result.html', registrations=registrations, phone=phone)
    return render_template('check_status.html')

# --- Staff login system ---

@app.route('/staff_login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == STAFF_PASSWORD:
            session['staff_logged_in'] = True
            flash('เข้าสู่ระบบสำเร็จครับ')
            return redirect(url_for('staff'))
        else:
            flash('รหัสผ่านไม่ถูกต้องครับ')
            return redirect(url_for('staff_login'))
    return render_template('staff_login.html')

@app.route('/staff_logout')
def staff_logout():
    session.pop('staff_logged_in', None)
    flash('ออกจากระบบเรียบร้อยแล้วครับ')
    return redirect(url_for('staff_login'))

@app.route('/staff')
def staff():
    if not session.get('staff_logged_in'):
        flash('กรุณาเข้าสู่ระบบก่อนครับ')
        return redirect(url_for('staff_login'))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM registrations ORDER BY date')
    customers = c.fetchall()
    conn.close()
    return render_template('staff.html', customers=customers)

@app.route('/update_status/<int:id>', methods=['GET', 'POST'])
def update_status(id):
    if not session.get('staff_logged_in'):
        flash('กรุณาเข้าสู่ระบบก่อนครับ')
        return redirect(url_for('staff_login'))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM registrations WHERE id = ?', (id,))
    registration = c.fetchone()

    if registration is None:
        conn.close()
        flash("ไม่พบข้อมูลการลงทะเบียนนี้")
        return redirect(url_for('staff'))

    if request.method == 'POST':
        new_problem = request.form['problem']
        new_status = request.form['status']
        model = request.form['model']
        serial_number = request.form['serial_number']

        c.execute('''
            UPDATE registrations 
            SET problem = ?, status = ?, model = ?, serial_number = ?
            WHERE id = ?
        ''', (new_problem, new_status, model, serial_number, id))
        conn.commit()
        conn.close()
        flash("อัปเดตสถานะเรียบร้อยแล้วครับ")
        return redirect(url_for('staff'))

    conn.close()
    return render_template('update_status.html', registration=registration)

if __name__ == '__main__':
    init_db()
    alter_table()
    print("Starting Flask app...")
    from waitress import serve
    serve(app, host='0.0.0.0', port=8080)
