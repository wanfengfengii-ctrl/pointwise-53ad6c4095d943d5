from dataclasses import dataclass

from ledger_support import MAX_ROW_ID


@dataclass(frozen=True, slots=True)
class RevisionRecord:
    revision: int
    day: str
    submission_id: str
    previous_revision: int | None


def ensure_revision_schema(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS revisions (
            revision INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            submission_id TEXT NOT NULL UNIQUE,
            previous_revision INTEGER,
            UNIQUE (revision, day),
            FOREIGN KEY (submission_id, day) REFERENCES submissions(submission_id, day),
            FOREIGN KEY (previous_revision, day) REFERENCES revisions(revision, day)
        )
    ''')


def append_revision(connection, day, submission_id, previous_revision=None):
    cursor = connection.execute('''
        INSERT INTO revisions (day, submission_id, previous_revision) VALUES (?, ?, ?)
    ''', (day, submission_id, previous_revision))
    return RevisionRecord(cursor.lastrowid, day, submission_id, previous_revision)


def find_revision(connection, day, revision):
    if revision > MAX_ROW_ID:
        return None
    row = connection.execute('''
        SELECT revision, day, submission_id, previous_revision
        FROM revisions WHERE day = ? AND revision = ?
    ''', (day, revision)).fetchone()
    return None if row is None else RevisionRecord(*row)


def find_revision_for_submission(connection, submission_id):
    row = connection.execute('''
        SELECT revision, day, submission_id, previous_revision
        FROM revisions WHERE submission_id = ?
    ''', (submission_id,)).fetchone()
    return None if row is None else RevisionRecord(*row)
