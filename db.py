import os

try:
    from pathlib import Path

    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, encoding="utf-8")
except ImportError:
    pass

import psycopg
from psycopg.rows import dict_row


def _normalize_database_url(url: str) -> str:
    url = (url or "").strip()
    if len(url) >= 2 and url[0] == url[-1] and url[0] in "\"'":
        url = url[1:-1].strip()
    return url


def _append_conn_param(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"


def _connect_from_params():
    host = os.environ.get("PGHOST", "").strip()
    if not host:
        return None
    port = int(os.environ.get("PGPORT", "5432").strip() or "5432")
    user = os.environ.get("PGUSER", "postgres").strip() or "postgres"
    password = os.environ.get("PGPASSWORD", "")
    dbname = os.environ.get("PGDATABASE", "postgres").strip() or "postgres"
    sslmode = os.environ.get("PGSSLMODE", "require").strip() or "require"
    timeout = int(os.environ.get("PGCONNECT_TIMEOUT", "15").strip() or "15")
    kwargs = {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
        "sslmode": sslmode,
        "connect_timeout": timeout,
        "row_factory": dict_row,
    }
    return psycopg.connect(**kwargs)


def get_connection():
    url = _normalize_database_url(os.environ.get("DATABASE_URL", ""))

    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if "sslmode=" not in url and ".supabase.co" in url:
            url = _append_conn_param(url, "sslmode", "require")
        if "connect_timeout=" not in url:
            url = _append_conn_param(
                url, "connect_timeout", os.environ.get("PGCONNECT_TIMEOUT", "15").strip() or "15"
            )
        try:
            return psycopg.connect(url, row_factory=dict_row)
        except psycopg.OperationalError as e:
            err = str(e).lower()
            if "getaddrinfo" in err or "failed to resolve" in err or "could not translate" in err:
                raise RuntimeError(
                    "DATABASE_URL looks invalid: the hostname could not be resolved. "
                    "Copy the URI again from Supabase → Database → Connection string (URI). "
                    "Use one line, no spaces. If your password has @ # : or other symbols, "
                    "URL-encode it (e.g. @ as %40). Or leave DATABASE_URL empty and set "
                    "PGHOST, PGUSER, PGPASSWORD, PGDATABASE in .env instead."
                ) from e
            raise

    conn = _connect_from_params()
    if conn is not None:
        return conn

    raise RuntimeError(
        "No database configuration found. Either set DATABASE_URL to the Supabase URI, "
        "or set PGHOST (e.g. db.your-project.supabase.co), PGUSER, PGPASSWORD, and "
        "optionally PGPORT (5432), PGDATABASE (postgres), PGSSLMODE (require)."
    )
