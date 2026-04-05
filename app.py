from flask import Flask, render_template, request, redirect, session
from db import get_connection

app = Flask(__name__)
app.secret_key = "secret123"


# 🔐 LOGIN
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM user WHERE username=%s AND password=%s",
                    (request.form['username'], request.form['password']))
        user = cur.fetchone()
        conn.close()

        if user:
            session['user'] = user['username']
            return redirect('/')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')


# 🔷 HOME
@app.route('/')
def index():
    if 'user' not in session:
        return redirect('/login')
    return render_template('index.html')


# 🔷 STUDENTS (SEARCH)
@app.route('/students')
def students():
    if 'user' not in session:
        return redirect('/login')

    conn = get_connection()
    cur = conn.cursor()

    search = request.args.get('search', '')

    cur.execute("""
        SELECT s.*, d.dept_name
        FROM student s
        LEFT JOIN department d ON s.dept_id = d.dept_id
        WHERE s.name LIKE %s
    """, (f"%{search}%",))

    data = cur.fetchall()
    conn.close()

    return render_template('students.html', students=data, search=search)


# 🔷 ADD STUDENT
@app.route('/add_student', methods=['GET','POST'])
def add_student():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM department")
    depts = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO student (name,email,dept_id,enrollment_year)
            VALUES (%s,%s,%s,%s)
        """, (
            request.form['name'],
            request.form['email'],
            request.form['dept_id'],
            request.form['year']
        ))
        conn.commit()
        conn.close()
        return redirect('/students')

    conn.close()
    return render_template('add_student.html', depts=depts)


# 🔷 ENROLL
@app.route('/enroll', methods=['GET','POST'])
def enroll():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM student")
    students = cur.fetchall()

    cur.execute("SELECT * FROM section")
    sections = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO enrollment (student_id,section_id)
            VALUES (%s,%s)
        """, (
            request.form['student_id'],
            request.form['section_id']
        ))
        conn.commit()
        conn.close()
        return redirect('/students')

    conn.close()
    return render_template('enroll.html', students=students, sections=sections)


# 🔷 ATTENDANCE
@app.route('/attendance', methods=['GET','POST'])
def attendance():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT e.enrollment_id, s.name
        FROM enrollment e
        JOIN student s ON e.student_id = s.student_id
    """)
    enrollments = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO attendance (enrollment_id,date,status)
            VALUES (%s,%s,%s)
        """, (
            request.form['enrollment_id'],
            request.form['date'],
            request.form['status']
        ))
        conn.commit()
        conn.close()
        return redirect('/attendance')

    conn.close()
    return render_template('attendance.html', enrollments=enrollments)


# 🔷 EXAMS
@app.route('/exams', methods=['GET','POST'])
def exams():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM section")
    sections = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO exam (section_id,exam_type,date,total_marks)
            VALUES (%s,%s,%s,%s)
        """, (
            request.form['section_id'],
            request.form['exam_type'],
            request.form['date'],
            request.form['total']
        ))
        conn.commit()
        conn.close()
        return redirect('/exams')

    conn.close()
    return render_template('exams.html', sections=sections)


@app.route('/results', methods=['POST'])
def results():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO result (exam_id,student_id,marks_obtained)
        VALUES (%s,%s,%s)
    """, (
        request.form['exam_id'],
        request.form['student_id'],
        request.form['marks']
    ))

    conn.commit()
    conn.close()
    return redirect('/students')


# 🔷 ASSIGNMENTS
@app.route('/assignments', methods=['GET','POST'])
def assignments():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM section")
    sections = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO assignment (section_id,title,due_date,max_marks)
            VALUES (%s,%s,%s,%s)
        """, (
            request.form['section_id'],
            request.form['title'],
            request.form['due_date'],
            request.form['max']
        ))
        conn.commit()
        conn.close()
        return redirect('/assignments')

    conn.close()
    return render_template('assignments.html', sections=sections)


@app.route('/submit', methods=['POST'])
def submit():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO submission (assignment_id,student_id,submission_date,marks,status)
        VALUES (%s,%s,%s,%s,%s)
    """, (
        request.form['assignment_id'],
        request.form['student_id'],
        request.form['date'],
        request.form['marks'],
        request.form['status']
    ))

    conn.commit()
    conn.close()
    return redirect('/students')


# 🔷 FEEDBACK
@app.route('/feedback', methods=['GET','POST'])
def feedback():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM student")
    students = cur.fetchall()

    cur.execute("SELECT * FROM section")
    sections = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO feedback (student_id,section_id,rating,comments)
            VALUES (%s,%s,%s,%s)
        """, (
            request.form['student_id'],
            request.form['section_id'],
            request.form['rating'],
            request.form['comments']
        ))
        conn.commit()
        conn.close()
        return redirect('/')

    conn.close()
    return render_template('feedback.html', students=students, sections=sections)


# 🔷 DASHBOARD
@app.route('/dashboard')
def dashboard():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT status, COUNT(*) as count FROM attendance GROUP BY status")
    data = cur.fetchall()

    conn.close()
    return render_template('dashboard.html', data=data)


if __name__ == '__main__':
    app.run(debug=True)
