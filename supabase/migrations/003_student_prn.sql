-- PRN (permanent roll number) + department prefix for panel-wise numbering (e.g. CSE 126224xxxx).

ALTER TABLE department ADD COLUMN IF NOT EXISTS prn_prefix TEXT;

UPDATE department SET prn_prefix = '126224'
WHERE prn_prefix IS NULL
  AND (dept_name ILIKE '%computer%' OR dept_name ILIKE '%cse%');

ALTER TABLE student ADD COLUMN IF NOT EXISTS prn TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS student_prn_uidx ON student (prn) WHERE prn IS NOT NULL;

UPDATE student SET prn = '1262240001'
WHERE student_id = 1 AND (prn IS NULL OR prn = '');
