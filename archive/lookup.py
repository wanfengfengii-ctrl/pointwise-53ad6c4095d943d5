from archive.publication import load_published
from ledger_support import MAX_ROW_ID, NotFound, require_positive_int


def read_report(archive, account_no):
    account_no = require_positive_int(account_no, 'account number')
    if account_no > MAX_ROW_ID:
        raise NotFound(f'Unknown account {account_no}')
    with archive.read_transaction() as connection:
        row = connection.execute('''
            SELECT account_no, payload, totals FROM reports WHERE account_no = ?
        ''', (account_no,)).fetchone()
    if row is None:
        raise NotFound(f'Unknown account {account_no}')
    return load_published(row)
