-- Run after schema.sql. Adds roles, links users to student/faculty, submission file path, one submission per assignment per student.

ALTER TABLE app_user ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'admin';
UPDATE app_user SET role = 'admin' WHERE role IS NULL;

ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_role_check;
ALTER TABLE app_user ADD CONSTRAINT app_user_role_check
    CHECK (role IN ('student', 'faculty', 'admin'));

ALTER TABLE app_user ADD COLUMN IF NOT EXISTS student_id INT REFERENCES student (student_id) ON DELETE CASCADE;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS faculty_id INT REFERENCES faculty (faculty_id) ON DELETE CASCADE;

ALTER TABLE submission ADD COLUMN IF NOT EXISTS file_path TEXT;

DELETE FROM submission a
    USING submission b
WHERE a.submission_id > b.submission_id
  AND a.assignment_id = b.assignment_id
  AND a.student_id = b.student_id;

CREATE UNIQUE INDEX IF NOT EXISTS submission_assignment_student_uidx
    ON submission (assignment_id, student_id);

-- Demo portal users (optional): student jane / jane, faculty smith / smith
INSERT INTO app_user (username, password, role, student_id, faculty_id)
SELECT 'jane', 'jane', 'student', s.student_id, NULL
FROM student s
WHERE s.email = 'jane@uni.edu'
LIMIT 1
ON CONFLICT (username) DO UPDATE SET
    role = EXCLUDED.role,
    student_id = EXCLUDED.student_id,
    faculty_id = NULL;

INSERT INTO app_user (username, password, role, student_id, faculty_id)
SELECT 'smith', 'smith', 'faculty', NULL, f.faculty_id
FROM faculty f
WHERE f.email = 'smith@uni.edu'
LIMIT 1
ON CONFLICT (username) DO UPDATE SET
    role = EXCLUDED.role,
    faculty_id = EXCLUDED.faculty_id,
    student_id = NULL;
