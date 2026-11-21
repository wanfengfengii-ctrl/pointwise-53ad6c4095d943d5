from dataclasses import dataclass

from accounting.combine import CombinedTotals, parse_totals
from archive.receipts import create_receipt, read_receipt, store_receipt
from exchange.package import decode_package, encode_package, package_identity
from exchange.station_piece import StationPiece
from ledger_support import Conflict, StorageError, canonical_json, load_json


@dataclass(frozen=True, slots=True)
class Report:
    account_no: int
    pickup_id: str
    day: str
    east: StationPiece
    west: StationPiece
    totals: CombinedTotals

    @classmethod
    def from_package(cls, account_no, package, totals):
        return cls(account_no, package.pickup_id, package.day, package.east, package.west, totals)


def load_published(row):
    package = decode_package(row['payload'])
    totals = parse_totals(load_json(row['totals']))
    return Report.from_package(row['account_no'], package, totals)


def publish_report(archive, package, totals):
    """Commit an already admitted handoff and its first receipt together."""
    payload = encode_package(package)
    digest = package_identity(payload)
    with archive.write_transaction() as connection:
        existing = connection.execute('''
            SELECT account_no, payload, totals, package_digest FROM reports WHERE pickup_id = ?
        ''', (package.pickup_id,)).fetchone()
        if existing is not None:
            if existing['package_digest'] != digest or existing['payload'] != payload:
                raise Conflict(f'Pickup ID already signed with different content: {package.pickup_id}')
            receipt = read_receipt(connection, package.pickup_id)
            if receipt is None or receipt.account_no != existing['account_no'] or receipt.package_digest != digest:
                raise StorageError('Published report has no matching original receipt')
            return load_published(existing), receipt

        cursor = connection.execute('''
            INSERT INTO reports (pickup_id, payload, totals, package_digest) VALUES (?, ?, ?, ?)
        ''', (package.pickup_id, payload, canonical_json(totals.as_dict()), digest))
        account_no = cursor.lastrowid
        receipt = create_receipt(account_no, package.pickup_id, digest)
        store_receipt(connection, receipt)
        return Report.from_package(account_no, package, totals), receipt
