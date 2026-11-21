from intake.origins import SourceOrigin
from intake.rows import ObservationRow
from intake.submission import Submission
from ledger_support import InvalidData


def ensure_inbox_schema(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            submission_id TEXT PRIMARY KEY NOT NULL,
            day TEXT NOT NULL,
            UNIQUE (submission_id, day)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS submission_rows (
            submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
            position INTEGER NOT NULL,
            litres TEXT,
            register TEXT NOT NULL,
            register_line TEXT NOT NULL,
            PRIMARY KEY (submission_id, position)
        )
    ''')


def find_submission(connection, station, submission_id):
    entry = connection.execute(
        'SELECT day FROM submissions WHERE submission_id = ?', (submission_id,)
    ).fetchone()
    if entry is None:
        return None
    records = connection.execute('''
        SELECT litres, register, register_line FROM submission_rows
        WHERE submission_id = ? ORDER BY position
    ''', (submission_id,))
    rows = tuple(
        ObservationRow(
            None if record['litres'] is None else int(record['litres']),
            SourceOrigin(record['register'], int(record['register_line'])),
        )
        for record in records
    )
    return Submission(station, entry['day'], submission_id, rows)


def record_submission(connection, submission):
    connection.execute(
        'INSERT INTO submissions (submission_id, day) VALUES (?, ?)',
        (submission.submission_id, submission.day),
    )
    records = []
    try:
        for position, row in enumerate(submission.rows, 1):
            litres = None if row.litres is None else str(row.litres)
            records.append((submission.submission_id, position, litres,
                            row.origin.register, str(row.origin.line)))
    except ValueError as error:
        raise InvalidData('An integer exceeds the configured decimal conversion limit') from error
    connection.executemany('''
        INSERT INTO submission_rows (submission_id, position, litres, register, register_line)
        VALUES (?, ?, ?, ?, ?)
    ''', records)


def matches_submission(existing, incoming):
    return existing == incoming
