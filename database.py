import sqlite3
import os
from datetime import datetime
from email_parser import _JUNK_TITLE_PHRASES

DB_PATH = os.path.join(os.path.dirname(__file__), 'jobs.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


_CLEANUP_VERSION = 2


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            job_title TEXT NOT NULL,
            location TEXT DEFAULT 'Not specified',
            status TEXT DEFAULT 'Applied',
            applied_at TEXT,
            email_id TEXT UNIQUE,
            resume_folder TEXT,
            job_url TEXT,
            notes TEXT,
            source TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at TEXT DEFAULT (datetime('now')),
            emails_processed INTEGER DEFAULT 0,
            new_applications INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS db_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cleanup_version INTEGER NOT NULL DEFAULT 0
        )
    ''')
    # Ensure indexes exist for common query patterns
    conn.execute('CREATE INDEX IF NOT EXISTS idx_applied_at ON applications(applied_at DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_status ON applications(status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_company ON applications(company)')
    conn.commit()

    # One-time cleanup: only runs once per schema version
    row = conn.execute('SELECT cleanup_version FROM db_version WHERE id = 1').fetchone()
    current_version = row['cleanup_version'] if row else 0
    if current_version < _CLEANUP_VERSION:
        _cleanup_data(conn)
        conn.execute('''
            INSERT INTO db_version (id, cleanup_version) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET cleanup_version = excluded.cleanup_version
        ''', (_CLEANUP_VERSION,))
        conn.commit()
    conn.close()


def _cleanup_data(conn):
    """Fix existing DB data: strip leading * from titles, replace junk titles, title-case all-lowercase companies."""
    import re as _re
    rows = conn.execute('SELECT id, job_title, company FROM applications').fetchall()
    for row in rows:
        updates = {}
        title = row['job_title'] or ''
        company = row['company'] or ''

        # Strip leading asterisks/bullets and articles from job title
        cleaned_title = _re.sub(r'^[*•\-–—\s]+', '', title).strip()
        cleaned_title = _re.sub(r'^(?:in the|in a|for the|for a|the|a)\s+', '', cleaned_title, flags=_re.I).strip()
        # Always update if cleaned differs from original
        if cleaned_title != title.strip():
            updates['job_title'] = cleaned_title or 'Unknown Position'

        # Replace junk titles with Unknown Position
        check_title = updates.get('job_title', title).lower().strip()
        if any(phrase in check_title for phrase in _JUNK_TITLE_PHRASES):
            updates['job_title'] = 'Unknown Position'
        elif len(check_title.split()) < 2 and check_title not in ('', 'unknown position'):
            updates['job_title'] = 'Unknown Position'

        # Fix all-lowercase company names
        if company and company == company.lower() and company not in ('Unknown Company', ''):
            updates['company'] = company.title()

        if updates:
            fields = ', '.join(f'{k}=?' for k in updates)
            conn.execute(f'UPDATE applications SET {fields} WHERE id=?',
                         list(updates.values()) + [row['id']])
    conn.commit()


def get_applications(filters=None):
    conn = get_db()
    query = 'SELECT * FROM applications WHERE 1=1'
    params = []

    if filters:
        if filters.get('status'):
            query += ' AND status = ?'
            params.append(filters['status'])
        if filters.get('search'):
            query += ' AND (company LIKE ? OR job_title LIKE ? OR location LIKE ?)'
            s = f'%{filters["search"]}%'
            params.extend([s, s, s])
        if filters.get('date_from'):
            query += ' AND applied_at >= ?'
            params.append(filters['date_from'])
        if filters.get('date_to'):
            query += ' AND applied_at <= ?'
            params.append(filters['date_to'] + 'T23:59:59')
        if filters.get('source'):
            query += ' AND source = ?'
            params.append(filters['source'])

    query += ' ORDER BY applied_at DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_application(data):
    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO applications
                (company, job_title, location, status, applied_at, email_id, resume_folder, job_url, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['company'],
            data['job_title'],
            data.get('location', 'Not specified'),
            data.get('status', 'Applied'),
            data.get('applied_at'),
            data.get('email_id'),
            data.get('resume_folder'),
            data.get('job_url'),
            data.get('source'),
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate email_id
    finally:
        conn.close()


def update_application(app_id, data):
    conn = get_db()
    allowed = ['status', 'resume_folder', 'notes', 'location', 'job_title', 'company', 'job_url']
    fields, params = [], []
    for field in allowed:
        if field in data:
            fields.append(f'{field} = ?')
            params.append(data[field])
    if not fields:
        conn.close()
        return False
    fields.append('updated_at = ?')
    params.append(datetime.now().isoformat())
    params.append(app_id)
    conn.execute(f'UPDATE applications SET {", ".join(fields)} WHERE id = ?', params)
    conn.commit()
    conn.close()
    return True


def delete_application(app_id):
    conn = get_db()
    conn.execute('DELETE FROM applications WHERE id = ?', (app_id,))
    conn.commit()
    conn.close()


def get_analytics():
    conn = get_db()

    daily = conn.execute('''
        SELECT DATE(applied_at) as date, COUNT(*) as count
        FROM applications
        WHERE applied_at >= DATE('now', '-30 days')
        GROUP BY DATE(applied_at)
        ORDER BY date
    ''').fetchall()

    status_breakdown = conn.execute('''
        SELECT status, COUNT(*) as count
        FROM applications
        GROUP BY status
        ORDER BY count DESC
    ''').fetchall()

    sources = conn.execute('''
        SELECT COALESCE(source, 'Unknown') as source, COUNT(*) as count
        FROM applications
        GROUP BY source
        ORDER BY count DESC
    ''').fetchall()

    locations = conn.execute('''
        SELECT location, COUNT(*) as count
        FROM applications
        WHERE location != 'Not specified' AND location IS NOT NULL AND location != ''
        GROUP BY location
        ORDER BY count DESC
        LIMIT 10
    ''').fetchall()

    stats = conn.execute('''
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN DATE(applied_at) = DATE('now') THEN 1 END) as today,
            COUNT(CASE WHEN status IN ('Phone Screen','Technical Interview','Final Interview','Offer') THEN 1 END) as responses,
            COUNT(CASE WHEN status = 'Applied' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'Rejected' THEN 1 END) as rejected,
            COUNT(CASE WHEN status = 'Offer' THEN 1 END) as offers
        FROM applications
    ''').fetchone()

    weekly = conn.execute('''
        SELECT DATE(applied_at) as date, COUNT(*) as count
        FROM applications
        WHERE applied_at >= DATE('now', '-7 days')
        GROUP BY DATE(applied_at)
        ORDER BY date
    ''').fetchall()

    heatmap = conn.execute('''
        SELECT DATE(applied_at) as date, COUNT(*) as count
        FROM applications
        WHERE applied_at >= DATE('now', '-364 days')
        GROUP BY DATE(applied_at)
        ORDER BY date
    ''').fetchall()

    conn.close()
    return {
        'daily': [dict(r) for r in daily],
        'weekly': [dict(r) for r in weekly],
        'status': [dict(r) for r in status_breakdown],
        'sources': [dict(r) for r in sources],
        'locations': [dict(r) for r in locations],
        'stats': dict(stats),
        'heatmap': [dict(r) for r in heatmap],
    }


def _is_junk_title_db(title):
    """Check if a stored title is junk and should be replaced."""
    if not title or title in _JUNK_TITLES:
        return True
    t = title.lower().strip()
    if any(phrase in t for phrase in _JUNK_TITLE_PHRASES):
        return True
    words = title.split()
    if len(words) < 2:
        return True
    return False


def upsert_application(data):
    """Insert new application or update Unknown/junk fields on existing one."""
    conn = get_db()
    try:
        existing = conn.execute(
            'SELECT id, company, job_title FROM applications WHERE email_id = ?',
            (data.get('email_id'),)
        ).fetchone()

        if not existing:
            conn.execute('''
                INSERT INTO applications
                    (company, job_title, location, status, applied_at, email_id, resume_folder, job_url, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['company'], data['job_title'],
                data.get('location', 'Not specified'),
                data.get('status', 'Applied'),
                data.get('applied_at'), data.get('email_id'),
                data.get('resume_folder'), data.get('job_url'), data.get('source'),
            ))
            conn.commit()
            conn.close()
            return 'inserted'

        # Update if existing value is Unknown or junk
        updates = {}
        if existing['company'] in _JUNK_COMPANIES and data['company'] not in _JUNK_COMPANIES:
            updates['company'] = data['company']
        if _is_junk_title_db(existing['job_title']) and data['job_title'] not in _JUNK_TITLES:
            updates['job_title'] = data['job_title']

        if updates:
            fields = ', '.join(f'{k}=?' for k in updates)
            conn.execute(f'UPDATE applications SET {fields} WHERE id=?',
                         list(updates.values()) + [existing['id']])
            conn.commit()
            conn.close()
            return 'updated'

        conn.close()
        return 'skipped'
    except Exception as e:
        conn.close()
        raise e


def update_title_by_company(company: str, job_title: str) -> int:
    """Update job_title for any application matching company, regardless of status."""
    if not company or not job_title:
        return 0
    conn = get_db()
    row = conn.execute('''
        SELECT id, job_title FROM applications
        WHERE (LOWER(company) LIKE LOWER(?) OR LOWER(?) LIKE LOWER('%' || company || '%'))
        ORDER BY applied_at DESC
        LIMIT 1
    ''', (f'%{company}%', company)).fetchone()
    if row and _is_junk_title_db(row['job_title']):
        conn.execute(
            'UPDATE applications SET job_title=?, updated_at=? WHERE id=?',
            (job_title, datetime.now().isoformat(), row['id'])
        )
        conn.commit()
        conn.close()
        return row['id']
    conn.close()
    return 0


def update_status_by_company(company: str, new_status: str, job_title: str = None) -> int:
    """
    Find the most recent application matching the company name and update its status.
    Also updates job_title if provided and existing title is Unknown/junk.
    Returns the id if updated, else 0.
    """
    if not company:
        return 0
    conn = get_db()
    row = conn.execute('''
        SELECT id, job_title FROM applications
        WHERE (LOWER(company) LIKE LOWER(?) OR LOWER(?) LIKE LOWER('%' || company || '%'))
          AND status NOT IN ('Rejected', 'Withdrawn', 'Offer')
        ORDER BY applied_at DESC
        LIMIT 1
    ''', (f'%{company}%', company)).fetchone()

    if row:
        fields = ['status=?', 'updated_at=?']
        params = [new_status, datetime.now().isoformat()]
        # Update job_title only if existing is junk and we have a better one
        if job_title and _is_junk_title_db(row['job_title']):
            fields.append('job_title=?')
            params.append(job_title)
        params.append(row['id'])
        conn.execute(f'UPDATE applications SET {", ".join(fields)} WHERE id=?', params)
        conn.commit()
        conn.close()
        return row['id']
    conn.close()
    return 0


def get_last_sync():
    conn = get_db()
    row = conn.execute('SELECT * FROM sync_log ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()
    return dict(row) if row else None


def log_sync(emails_processed, new_applications):
    conn = get_db()
    conn.execute(
        'INSERT INTO sync_log (emails_processed, new_applications) VALUES (?, ?)',
        (emails_processed, new_applications),
    )
    conn.commit()
    conn.close()
