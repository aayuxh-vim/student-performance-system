-- Run this in Supabase: SQL Editor → New query → Paste → Run.
-- Optional: reset public schema first (destructive): DROP SCHEMA public CASCADE; CREATE SCHEMA public; ...

CREATE TABLE department (
    dept_id SERIAL PRIMARY KEY,
    dept_name TEXT NOT NULL,
    prn_prefix TEXT
);

CREATE TABLE faculty (
    faculty_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    dept_id INT REFERENCES department (dept_id) ON DELETE SET NULL,
    designation TEXT,
    salary NUMERIC(14, 2)
);

ALTER TABLE department
    ADD COLUMN hod_id INT REFERENCES faculty (faculty_id) ON DELETE SET NULL;

CREATE TABLE student (
    student_id SERIAL PRIMARY KEY,
    prn TEXT UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    dob DATE,
    dept_id INT REFERENCES department (dept_id) ON DELETE SET NULL,
    enrollment_year INT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive'))
);

CREATE TABLE course (
    course_id SERIAL PRIMARY KEY,
    course_name TEXT NOT NULL,
    credits INT NOT NULL DEFAULT 3,
    dept_id INT REFERENCES department (dept_id) ON DELETE CASCADE,
    course_type TEXT NOT NULL DEFAULT 'core' CHECK (course_type IN ('core', 'elective'))
);

CREATE TABLE section (
    section_id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES course (course_id) ON DELETE CASCADE,
    faculty_id INT REFERENCES faculty (faculty_id) ON DELETE SET NULL,
    semester INT NOT NULL,
    year INT NOT NULL,
    room_no TEXT
);

CREATE TABLE enrollment (
    enrollment_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES student (student_id) ON DELETE CASCADE,
    section_id INT NOT NULL REFERENCES section (section_id) ON DELETE CASCADE,
    enrollment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    final_grade TEXT,
    UNIQUE (student_id, section_id)
);

CREATE TABLE attendance (
    attendance_id SERIAL PRIMARY KEY,
    enrollment_id INT NOT NULL REFERENCES enrollment (enrollment_id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late'))
);

CREATE TABLE exam (
    exam_id SERIAL PRIMARY KEY,
    section_id INT NOT NULL REFERENCES section (section_id) ON DELETE CASCADE,
    exam_type TEXT NOT NULL CHECK (exam_type IN ('midsem', 'endsem', 'quiz')),
    exam_date DATE NOT NULL,
    total_marks INT NOT NULL
);

CREATE TABLE result (
    result_id SERIAL PRIMARY KEY,
    exam_id INT NOT NULL REFERENCES exam (exam_id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES student (student_id) ON DELETE CASCADE,
    marks_obtained NUMERIC(8, 2) NOT NULL,
    grade TEXT,
    UNIQUE (exam_id, student_id)
);

CREATE TABLE assignment (
    assignment_id SERIAL PRIMARY KEY,
    section_id INT NOT NULL REFERENCES section (section_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    due_date DATE NOT NULL,
    max_marks INT NOT NULL
);

CREATE TABLE submission (
    submission_id SERIAL PRIMARY KEY,
    assignment_id INT NOT NULL REFERENCES assignment (assignment_id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES student (student_id) ON DELETE CASCADE,
    submission_date DATE NOT NULL,
    marks NUMERIC(8, 2),
    status TEXT NOT NULL CHECK (status IN ('submitted', 'late', 'missing')),
    file_path TEXT,
    UNIQUE (assignment_id, student_id)
);

CREATE TABLE prerequisite (
    course_id INT NOT NULL REFERENCES course (course_id) ON DELETE CASCADE,
    prereq_course_id INT NOT NULL REFERENCES course (course_id) ON DELETE CASCADE,
    PRIMARY KEY (course_id, prereq_course_id),
    CHECK (course_id <> prereq_course_id)
);

-- Portal login (not in ER diagram; required by the Flask app)
CREATE TABLE app_user (
    user_id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('student', 'faculty', 'admin')),
    student_id INT REFERENCES student (student_id) ON DELETE CASCADE,
    faculty_id INT REFERENCES faculty (faculty_id) ON DELETE CASCADE
);

-- Course feedback (UI feature)
CREATE TABLE feedback (
    feedback_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES student (student_id) ON DELETE CASCADE,
    section_id INT NOT NULL REFERENCES section (section_id) ON DELETE CASCADE,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comments TEXT
);

-- ---------- Seed (dev / demo) ----------
INSERT INTO app_user (username, password, role, student_id, faculty_id)
VALUES ('admin', 'admin', 'admin', NULL, NULL);

INSERT INTO department (dept_name, prn_prefix) VALUES ('Computer Science', '126224');

INSERT INTO faculty (name, email, phone, dept_id, designation, salary)
VALUES ('Dr. Smith', 'smith@uni.edu', '555-0101', 1, 'Professor', 125000.00);

UPDATE department SET hod_id = 1 WHERE dept_id = 1;

INSERT INTO course (course_name, credits, dept_id, course_type)
VALUES ('Database Systems', 4, 1, 'core');

INSERT INTO student (prn, name, email, phone, dob, dept_id, enrollment_year, status)
VALUES ('1262240001', 'Jane Doe', 'jane@uni.edu', '555-0200', '2003-04-15', 1, 2024, 'active');

INSERT INTO section (course_id, faculty_id, semester, year, room_no)
VALUES (1, 1, 1, 2024, 'A-101');

INSERT INTO enrollment (student_id, section_id)
VALUES (1, 1);

INSERT INTO app_user (username, password, role, student_id, faculty_id)
VALUES ('jane', 'jane', 'student', 1, NULL);

INSERT INTO app_user (username, password, role, student_id, faculty_id)
VALUES ('smith', 'smith', 'faculty', NULL, 1);
