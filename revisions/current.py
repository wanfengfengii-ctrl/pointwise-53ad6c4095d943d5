from dataclasses import dataclass

from accounting.site_totals import calculate_site_total
from intake.inbox import find_submission
from intake.rows import ObservationRow
from intake.submission import parse_day
from ledger_support import NotFound, StorageError, require_positive_int
from revisions.history import find_revision


@dataclass(frozen=True, slots=True)
class SiteView:
    station: str
    day: str
    revision: int
    submission_id: str
    rows: tuple[ObservationRow, ...]
    total_litres: int


def ensure_current_schema(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS current_days (
            day TEXT PRIMARY KEY NOT NULL,
            revision INTEGER NOT NULL,
            FOREIGN KEY (revision, day) REFERENCES revisions(revision, day)
        )
    ''')


def find_current_revision(connection, day):
    row = connection.execute('SELECT revision FROM current_days WHERE day = ?', (day,)).fetchone()
    return None if row is None else row['revision']


def set_current_revision(connection, day, revision):
    connection.execute('''
        INSERT INTO current_days (day, revision) VALUES (?, ?)
        ON CONFLICT(day) DO UPDATE SET revision = excluded.revision
    ''', (day, revision))


def read_site(site, day, revision=None):
    """Read the selected revision and its original rows in a single site snapshot."""
    day = parse_day(day)
    if revision is not None:
        revision = require_positive_int(revision, 'revision')
    with site.read_transaction() as connection:
        selected = revision if revision is not None else find_current_revision(connection, day)
        if selected is None:
            raise NotFound(f'No revision for {site.station} on {day}')
        record = find_revision(connection, day, selected)
        if record is None:
            raise NotFound(f'Unknown revision {selected} for {site.station} on {day}')
        submission = find_submission(connection, site.station, record.submission_id)
        if submission is None:
            raise StorageError(f'Revision {selected} is missing its original submission')
        return SiteView(site.station, day, selected, submission.submission_id,
                        submission.rows, calculate_site_total(submission.rows))
