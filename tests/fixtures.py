import sqlite3
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from ledger import IssuedStore, TrustedIssuer, apply, capture, init, open_archive


DAY = '2030-04-09'
OTHER_DAY = '2030-04-10'


def submission(station, name, values, *, day=DAY, register=None):
    register = name if register is None else register
    return {
        'station': station,
        'day': day,
        'submission_id': name,
        'rows': [
            {'litres': value, 'origin': {'register': register, 'line': index}}
            for index, value in enumerate(values, 1)
        ],
    }


@contextmanager
def reject_next_commit(path, table):
    if table not in {'revisions', 'receipts'}:
        raise ValueError('Unknown fixture target')
    with closing(sqlite3.connect(path, isolation_level=None)) as database:
        database.execute('CREATE TABLE fixture_parent (id INTEGER PRIMARY KEY)')
        database.execute('''
            CREATE TABLE fixture_guard (
                id INTEGER REFERENCES fixture_parent(id) DEFERRABLE INITIALLY DEFERRED
            )
        ''')
        database.execute(f'''
            CREATE TRIGGER fixture_reject AFTER INSERT ON {table}
            BEGIN
                INSERT INTO fixture_guard (id) VALUES (1);
            END
        ''')
        try:
            yield
        finally:
            database.execute('DROP TRIGGER fixture_reject')
            database.execute('DROP TABLE fixture_guard')
            database.execute('DROP TABLE fixture_parent')


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(TemporaryDirectory(prefix='ledger-tests-'))
        self.folder = Path(folder)


class LedgerFixture(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.east = init(self.folder / 'east.sqlite', 'east')
        self.west = init(self.folder / 'west.sqlite', 'west')
        self.issued = IssuedStore(self.folder / 'issued.sqlite')
        self.archive = open_archive(self.folder / 'archive.sqlite')
        self.issuer = TrustedIssuer('shift-issuer', b'test key for deterministic ledger fixtures', 'east', 'west')
        self.config = {self.issuer.issuer_id: self.issuer}

    def activate_pair(self, east_values=(7,), west_values=(11,)):
        east = apply(self.east, submission('east', 'E1', east_values))
        west = apply(self.west, submission('west', 'W1', west_values))
        return east, west

    def pickup(self, name, **options):
        return capture(self.issued, self.issuer, name, DAY, self.east, self.west, **options)

    def take_sources_offline(self):
        for site in (self.east, self.west):
            site.path.rename(site.path.with_suffix('.offline'))
            self.assertFalse(site.path.exists())

    def assert_archive_counts(self, reports, receipts):
        with self.archive.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM reports').fetchone()[0], reports)
            self.assertEqual(connection.execute('SELECT count(*) FROM receipts').fetchone()[0], receipts)
