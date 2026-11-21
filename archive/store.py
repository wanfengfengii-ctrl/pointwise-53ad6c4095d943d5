from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from archive.receipts import ensure_receipt_schema
from ledger_support import transaction


@dataclass(frozen=True, slots=True)
class ArchiveStore:
    path: Path

    @contextmanager
    def read_transaction(self):
        with transaction(self.path) as connection:
            yield connection

    @contextmanager
    def write_transaction(self):
        with transaction(self.path, write=True) as connection:
            yield connection


def open_archive(path):
    path = Path(path).absolute()
    with transaction(path, write=True, create=True) as connection:
        connection.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                account_no INTEGER PRIMARY KEY,
                pickup_id TEXT NOT NULL UNIQUE,
                payload BLOB NOT NULL,
                totals BLOB NOT NULL,
                package_digest TEXT NOT NULL,
                UNIQUE (account_no, pickup_id)
            )
        ''')
        ensure_receipt_schema(connection)
    return ArchiveStore(path)
