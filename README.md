# Student Performance System

A Flask web app for tracking students, courses, attendance, exams, assignments, and feedback. It uses **PostgreSQL** (designed for [Supabase](https://supabase.com/)) and splits the UI into a **faculty/admin** area and a **student** portal.

## Features

- **Faculty / admin** (`/` and `/faculty`): students (with PRN and department panels), enrollment, section-based attendance sheet, exams and results, assignments and grading, course feedback.
- **Students** (`/student/…`): dashboard with CGPA-style summary, own marks and assignments, file uploads for submissions, attendance, and feedback.
- **Database**: `psycopg` with either `DATABASE_URL` or separate `PGHOST` / `PGUSER` / `PGPASSWORD` variables (helpful when passwords contain `#`, `@`, etc.).

## Requirements

- Python 3.10+
- A PostgreSQL database (Supabase or any Postgres with SSL as needed)

## Setup

1. **Clone and install dependencies**

   ```bash
   cd student-performance-system
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**

   Copy `.env.example` to `.env` and fill in your database settings and a secret:

   - `FLASK_SECRET_KEY` — use a long random string in production.
   - Either `DATABASE_URL` (quoted if the password has special characters) **or** `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, and `PGSSLMODE` as in `.env.example`.

3. **Create the database schema**

   In the Supabase **SQL Editor** (or `psql`), run in order:

   1. `supabase/schema.sql` — base tables and demo rows.
   2. `supabase/migrations/002_roles_submission_file.sql` — safe to re-run on existing DBs (uses `IF NOT EXISTS` where applicable).
   3. `supabase/migrations/003_student_prn.sql` — PRN / department prefix updates.

4. **Run the app**

   ```bash
   python app.py
   ```

   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) and sign in.

## Demo accounts (after running `schema.sql`)

| Username | Password | Role    |
|----------|----------|---------|
| `admin`  | `admin`  | Admin   |
| `jane`   | `jane`   | Student |
| `smith`  | `smith`  | Faculty |

Passwords are stored in plain text for local demos only—replace with proper hashing before any real deployment.

## Optional: random seed data

To generate extra departments, students (PRNs like `126224xxxx`), courses, attendance, exams, and assignments:

```bash
python scripts/seed_random_data.py
```

Requires a working `.env` and an already-migrated database.

## Project layout

- `app.py` — main Flask app and faculty routes.
- `student_portal.py` — student blueprint under `/student`.
- `db.py` — PostgreSQL connection helpers.
- `templates/` — Jinja templates (`faculty/`, `student/`, shared).
- `supabase/` — SQL schema and migrations.
- `uploads/assignments/` — stored assignment files (ignored by git except placeholders).

## License

Use and modify as needed for your institution or project.
