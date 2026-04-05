import os
from datetime import date

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from db import get_connection

student_bp = Blueprint("student", __name__, url_prefix="/student")

ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "zip", "txt"}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


@student_bp.before_request
def _student_only():
    if "user" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "student":
        return redirect(url_for("faculty_home"))


def _student_id():
    sid = session.get("student_id")
    if not sid:
        flash("This account is not linked to a student profile.", "danger")
        return None
    return sid


@student_bp.route("/")
def dashboard():
    sid = _student_id()
    if sid is None:
        return render_template("student/unlinked.html")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COALESCE(
            AVG((r.marks_obtained::float / NULLIF(e.total_marks, 0)) * 10), 0
        ) AS exam_index
        FROM result r
        JOIN exam e ON e.exam_id = r.exam_id
        WHERE r.student_id = %s AND e.total_marks > 0
        """,
        (sid,),
    )
    exam_index = float(cur.fetchone()["exam_index"] or 0)

    cur.execute(
        """
        SELECT COALESCE(
            AVG((sub.marks::float / NULLIF(a.max_marks, 0)) * 10), 0
        ) AS assign_index
        FROM submission sub
        JOIN assignment a ON a.assignment_id = sub.assignment_id
        WHERE sub.student_id = %s AND sub.marks IS NOT NULL AND a.max_marks > 0
        """,
        (sid,),
    )
    assign_index = float(cur.fetchone()["assign_index"] or 0)

    if exam_index > 0 and assign_index > 0:
        cgpa = round(0.6 * exam_index + 0.4 * assign_index, 2)
    elif exam_index > 0:
        cgpa = round(exam_index, 2)
    elif assign_index > 0:
        cgpa = round(assign_index, 2)
    else:
        cgpa = None

    cur.execute(
        """
        SELECT COUNT(*)::int AS n FROM enrollment WHERE student_id = %s
        """,
        (sid,),
    )
    enroll_count = cur.fetchone()["n"]

    cur.execute("SELECT prn FROM student WHERE student_id = %s", (sid,))
    prn_row = cur.fetchone()
    student_prn = prn_row.get("prn") if prn_row else None

    cur.execute(
        """
        SELECT COUNT(*)::int AS n
        FROM assignment a
        JOIN enrollment e ON e.section_id = a.section_id
        LEFT JOIN submission sub
          ON sub.assignment_id = a.assignment_id AND sub.student_id = e.student_id
        WHERE e.student_id = %s AND sub.submission_id IS NULL AND a.due_date >= CURRENT_DATE
        """,
        (sid,),
    )
    open_assignments = cur.fetchone()["n"]

    conn.close()

    return render_template(
        "student/dashboard.html",
        cgpa=cgpa,
        exam_index=round(exam_index, 2) if exam_index else None,
        assign_index=round(assign_index, 2) if assign_index else None,
        enroll_count=enroll_count,
        open_assignments=open_assignments,
        student_prn=student_prn,
    )


@student_bp.route("/marks")
def marks():
    sid = _student_id()
    if sid is None:
        return render_template("student/unlinked.html")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.marks_obtained, r.grade, e.total_marks, e.exam_type, e.exam_date,
               c.course_name, sec.semester, sec.year
        FROM result r
        JOIN exam e ON e.exam_id = r.exam_id
        JOIN section sec ON sec.section_id = e.section_id
        JOIN course c ON c.course_id = sec.course_id
        WHERE r.student_id = %s
        ORDER BY e.exam_date DESC NULLS LAST
        """,
        (sid,),
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("student/marks.html", marks=rows)


@student_bp.route("/assignments", methods=["GET", "POST"])
def assignments():
    sid = _student_id()
    if sid is None:
        return render_template("student/unlinked.html")

    upload_folder = current_app.config["ASSIGNMENT_UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    if request.method == "POST":
        aid = request.form.get("assignment_id")
        if not aid:
            flash("Missing assignment.", "danger")
            return redirect(url_for("student.assignments"))

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM enrollment e
            JOIN assignment a ON a.section_id = e.section_id
            WHERE e.student_id = %s AND a.assignment_id = %s
            """,
            (sid, aid),
        )
        if not cur.fetchone():
            conn.close()
            flash("You are not enrolled in that assignment's section.", "danger")
            return redirect(url_for("student.assignments"))

        file_path_saved = None
        f = request.files.get("file")
        if f and f.filename and _allowed(f.filename):
            fn = secure_filename(f.filename)
            unique = f"{sid}_{aid}_{fn}"
            full = os.path.join(upload_folder, unique)
            f.save(full)
            file_path_saved = unique
        elif f and f.filename:
            conn.close()
            flash("File type not allowed. Use pdf, doc, docx, images, zip, or txt.", "warning")
            return redirect(url_for("student.assignments"))

        cur.execute(
            """
            INSERT INTO submission (assignment_id, student_id, submission_date, marks, status, file_path)
            VALUES (%s, %s, %s, NULL, %s, %s)
            ON CONFLICT (assignment_id, student_id) DO UPDATE SET
                submission_date = EXCLUDED.submission_date,
                status = EXCLUDED.status,
                file_path = COALESCE(EXCLUDED.file_path, submission.file_path)
            """,
            (
                aid,
                sid,
                request.form.get("submission_date") or date.today().isoformat(),
                "late" if request.form.get("late") == "1" else "submitted",
                file_path_saved,
            ),
        )
        conn.commit()
        conn.close()
        flash("Submission saved.", "success")
        return redirect(url_for("student.assignments"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.assignment_id, a.title, a.due_date, a.max_marks,
               c.course_name, sec.semester, sec.year, sec.section_id,
               sub.submission_id, sub.submission_date, sub.status, sub.marks, sub.file_path
        FROM enrollment e
        JOIN section sec ON sec.section_id = e.section_id
        JOIN course c ON c.course_id = sec.course_id
        JOIN assignment a ON a.section_id = e.section_id
        LEFT JOIN submission sub
          ON sub.assignment_id = a.assignment_id AND sub.student_id = e.student_id
        WHERE e.student_id = %s
        ORDER BY a.due_date DESC
        """,
        (sid,),
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("student/assignments.html", assignments=rows)


@student_bp.route("/attendance")
def attendance():
    sid = _student_id()
    if sid is None:
        return render_template("student/unlinked.html")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT att.attendance_date, att.status, c.course_name, sec.semester, sec.year
        FROM attendance att
        JOIN enrollment e ON e.enrollment_id = att.enrollment_id
        JOIN section sec ON sec.section_id = e.section_id
        JOIN course c ON c.course_id = sec.course_id
        WHERE e.student_id = %s
        ORDER BY att.attendance_date DESC
        """,
        (sid,),
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("student/attendance.html", rows=rows)


@student_bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    sid = _student_id()
    if sid is None:
        return render_template("student/unlinked.html")

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute(
            """
            INSERT INTO feedback (student_id, section_id, rating, comments)
            VALUES (%s, %s, %s, %s)
            """,
            (
                sid,
                request.form["section_id"],
                request.form["rating"],
                request.form.get("comments") or None,
            ),
        )
        conn.commit()
        conn.close()
        flash("Thanks for your feedback.", "success")
        return redirect(url_for("student.feedback"))

    cur.execute(
        """
        SELECT sec.section_id, c.course_name, sec.semester, sec.year
        FROM enrollment e
        JOIN section sec ON sec.section_id = e.section_id
        JOIN course c ON c.course_id = sec.course_id
        WHERE e.student_id = %s
        ORDER BY sec.year DESC, sec.semester, c.course_name
        """,
        (sid,),
    )
    sections = cur.fetchall()

    cur.execute(
        """
        SELECT f.rating, f.comments, c.course_name, sec.semester, sec.year, f.feedback_id
        FROM feedback f
        JOIN section sec ON sec.section_id = f.section_id
        JOIN course c ON c.course_id = sec.course_id
        WHERE f.student_id = %s
        ORDER BY f.feedback_id DESC
        """,
        (sid,),
    )
    previous = cur.fetchall()
    conn.close()

    return render_template(
        "student/feedback.html", sections=sections, previous=previous
    )
