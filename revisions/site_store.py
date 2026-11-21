from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from intake.inbox import ensure_inbox_schema
from ledger_support import IdentityError, StorageError, require_text, transaction
from revisions.current import ensure_current_schema
from revisions.history import ensure_revision_schema


def _check_identity(connection, station):
    identity = connection.execute('SELECT station FROM site_identity WHERE slot = 1').fetchone()
    if identity is None:
        raise StorageError('Site database has no identity')
    if identity['station'] != station:
        raise IdentityError(f'Site database belongs to {identity["station"]!r}, expected {station!r}')


@dataclass(frozen=True, slots=True)
class SiteStore:
    path: Path
    station: str

    @contextmanager
    def read_transaction(self):
        with transaction(self.path) as connection:
            _check_identity(connection, self.station)
            yield connection

    @contextmanager
    def write_transaction(self):
        with transaction(self.path, write=True) as connection:
            _check_identity(connection, self.station)
            yield connection


def init(path, station):
    station = require_text(station, 'station')
    path = Path(path).absolute()
    with transaction(path, write=True, create=True) as connection:
        connection.execute('''
            CREATE TABLE IF NOT EXISTS site_identity (
                slot INTEGER PRIMARY KEY CHECK (slot = 1),
                station TEXT NOT NULL
            )
        ''')
        connection.execute('''
            INSERT INTO site_identity (slot, station) VALUES (1, ?)
            ON CONFLICT(slot) DO NOTHING
        ''', (station,))
        _check_identity(connection, station)
        ensure_inbox_schema(connection)
        ensure_revision_schema(connection)
        ensure_current_schema(connection)
    return SiteStore(path, station)
