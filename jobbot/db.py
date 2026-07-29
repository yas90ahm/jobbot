import sqlite3
from pathlib import Path


def connect(path="data/jobs.db"):
    """
    Connect to SQLite database, creating parent dirs and table if needed.
    Returns connection with row factory set to return dicts.
    """
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = lambda cursor, row: dict(zip([d[0] for d in cursor.description], row))

    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            description TEXT,
            source TEXT,
            posted TEXT,
            score REAL DEFAULT 0,
            status TEXT DEFAULT 'found',
            tailor_dir TEXT DEFAULT '',
            applied_at TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """)
    # migration for databases created before LLM fit scoring existed
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(jobs)")]
    if "fit" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN fit REAL DEFAULT -1")
        conn.execute("ALTER TABLE jobs ADD COLUMN fit_notes TEXT DEFAULT ''")
    conn.commit()

    return conn


def upsert(conn, jobs):
    """
    Insert or ignore job dicts by id. Returns count of newly inserted rows.
    """
    if not jobs:
        return 0

    columns = ['id', 'title', 'company', 'location', 'url', 'description', 'source', 'posted', 'score', 'status']
    placeholders = ','.join(['?'] * len(columns))
    sql = f"INSERT OR IGNORE INTO jobs ({','.join(columns)}) VALUES ({placeholders})"

    rows_before = conn.total_changes

    for job in jobs:
        values = [job.get(col) for col in columns]
        conn.execute(sql, values)

    conn.commit()
    return conn.total_changes - rows_before


def list_jobs(conn, status=None, min_score=None, limit=None):
    """
    List jobs with optional filters, ordered by score DESC.
    """
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if status is not None:
        query += " AND status = ?"
        params.append(status)

    if min_score is not None:
        query += " AND score >= ?"
        params.append(min_score)

    query += " ORDER BY score DESC"

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    return conn.execute(query, params).fetchall()


def update(conn, job_id, **fields):
    """
    Update specific columns for a job. Whitelist known columns to prevent SQL injection.
    """
    allowed_columns = {
        'title', 'company', 'location', 'url', 'description', 'source',
        'posted', 'score', 'status', 'tailor_dir', 'applied_at', 'notes',
        'fit', 'fit_notes'
    }

    filtered_fields = {k: v for k, v in fields.items() if k in allowed_columns}

    if not filtered_fields:
        return

    set_clause = ', '.join([f"{col} = ?" for col in filtered_fields.keys()])
    values = list(filtered_fields.values()) + [job_id]

    conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
    conn.commit()
