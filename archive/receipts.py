from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Receipt:
    account_no: int
    pickup_id: str
    package_digest: str


def ensure_receipt_schema(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            pickup_id TEXT PRIMARY KEY NOT NULL,
            account_no INTEGER NOT NULL UNIQUE,
            package_digest TEXT NOT NULL,
            FOREIGN KEY (account_no, pickup_id) REFERENCES reports(account_no, pickup_id)
        )
    ''')


def create_receipt(account_no, pickup_id, package_digest):
    return Receipt(account_no, pickup_id, package_digest)


def store_receipt(connection, receipt):
    connection.execute('''
        INSERT INTO receipts (account_no, pickup_id, package_digest) VALUES (?, ?, ?)
    ''', (receipt.account_no, receipt.pickup_id, receipt.package_digest))


def read_receipt(connection, pickup_id):
    row = connection.execute('''
        SELECT account_no, pickup_id, package_digest FROM receipts WHERE pickup_id = ?
    ''', (pickup_id,)).fetchone()
    return None if row is None else Receipt(*row)
