"""Print DB host/username from env (no password). For debugging .env only."""
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parent.parent / ".env", encoding="utf-8")

if os.environ.get("PGHOST"):
    print("mode: PG* variables")
    print("PGHOST:", os.environ.get("PGHOST"))
    print("PGUSER:", os.environ.get("PGUSER") or "(default postgres)")
    print("PGPORT:", os.environ.get("PGPORT") or "5432")
else:
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1].strip()
    print("mode: DATABASE_URL")
    if not raw:
        print("DATABASE_URL: (empty)")
    else:
        p = urlparse(raw)
        print("username:", p.username or "(missing)")
        print("host:", p.hostname or "(missing)")
        print("port:", p.port or "(default)")
