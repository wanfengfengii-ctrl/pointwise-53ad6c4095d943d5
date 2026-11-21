from pathlib import Path

from exchange.package import decode_package, encode_package
from ledger_support import Conflict, NotFound, require_text, transaction


class IssuedStore:
    def __init__(self, path):
        self.path = Path(path).absolute()
        with transaction(self.path, write=True, create=True) as connection:
            connection.execute('''
                CREATE TABLE IF NOT EXISTS issued (
                    pickup_id TEXT PRIMARY KEY NOT NULL,
                    payload BLOB NOT NULL
                )
            ''')

    def save_issued(self, package):
        payload = encode_package(package)
        with transaction(self.path, write=True) as connection:
            cursor = connection.execute('''
                INSERT INTO issued (pickup_id, payload) VALUES (?, ?)
                ON CONFLICT(pickup_id) DO NOTHING
            ''', (package.pickup_id, payload))
            if cursor.rowcount == 0:
                raise Conflict(f'Pickup ID already issued: {package.pickup_id}')

    def read_issued(self, pickup_id):
        pickup_id = require_text(pickup_id, 'pickup ID')
        with transaction(self.path) as connection:
            row = connection.execute('SELECT payload FROM issued WHERE pickup_id = ?',
                                     (pickup_id,)).fetchone()
        if row is None:
            raise NotFound(f'Unknown issued pickup {pickup_id}')
        return decode_package(row['payload'])
