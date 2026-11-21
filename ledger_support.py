import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


class LedgerError(Exception):
    """Base class for errors reported by the ledger API."""


class InvalidData(LedgerError):
    pass


class IdentityError(InvalidData):
    pass


class NotFound(LedgerError):
    pass


class Conflict(LedgerError):
    pass


class CaptureRetry(LedgerError):
    pass


class StorageError(LedgerError):
    pass


MAX_ROW_ID = (1 << 63) - 1


def require_fields(value, fields, label):
    if type(value) is not dict or value.keys() != set(fields):
        raise InvalidData(f'Invalid fields for {label}')
    return value


def require_text(value, label):
    if type(value) is not str or not value.strip():
        raise InvalidData(f'{label} must be nonblank text')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise InvalidData(f'{label} must be valid Unicode') from error
    return value


def require_positive_int(value, label):
    if type(value) is not int or value < 1:
        raise InvalidData(f'{label} must be a positive integer')
    return value


def canonical_json(value):
    try:
        return json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False
        ).encode('ascii')
    except (TypeError, ValueError, RecursionError) as error:
        raise InvalidData('Value cannot be encoded as ledger JSON') from error


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidData(f'Duplicate JSON field {key!r}')
        result[key] = value
    return result


def _reject_constant(value):
    raise InvalidData(f'Invalid JSON number {value!r}')


def load_json(raw):
    if not isinstance(raw, (str, bytes)):
        raise InvalidData('Expected UTF-8 JSON bytes or text')
    try:
        text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        return json.loads(text, object_pairs_hook=_unique_fields, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise InvalidData('Invalid UTF-8 ledger JSON') from error


@contextmanager
def transaction(path, *, write=False, create=False):
    mode = 'rwc' if create else ('rw' if write else 'ro')
    uri = f'{Path(path).absolute().as_uri()}?mode={mode}'
    try:
        with closing(sqlite3.connect(uri, uri=True, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys = ON')
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield connection
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise
    except sqlite3.Error as error:
        raise StorageError(f'SQLite transaction failed for {Path(path).name}: {error}') from error
