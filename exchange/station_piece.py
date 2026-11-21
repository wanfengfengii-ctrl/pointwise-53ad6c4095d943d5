from dataclasses import dataclass
from hashlib import sha256

from accounting.reconcile import reconcile_site
from intake.rows import ObservationRow, parse_rows
from intake.submission import parse_day
from ledger_support import InvalidData, canonical_json, require_fields, require_positive_int, require_text


@dataclass(frozen=True, slots=True)
class StationPiece:
    role: str
    station: str
    day: str
    revision: int
    submission_id: str
    rows: tuple[ObservationRow, ...]
    total_litres: int

    def as_dict(self):
        return {
            'role': self.role,
            'station': self.station,
            'day': self.day,
            'revision': self.revision,
            'submission_id': self.submission_id,
            'rows': [row.as_dict() for row in self.rows],
            'total_litres': self.total_litres,
        }


def _parse_role(role):
    if role not in ('east', 'west'):
        raise InvalidData('Station piece must identify its east or west role')
    return role


def make_station_piece(role, view):
    return StationPiece(_parse_role(role), view.station, view.day, view.revision,
                        view.submission_id, view.rows, view.total_litres)


def parse_station_piece(value):
    fields = require_fields(value, (
        'role', 'station', 'day', 'revision', 'submission_id', 'rows', 'total_litres',
    ), 'station piece')
    rows = parse_rows(fields['rows'])
    return StationPiece(
        _parse_role(fields['role']),
        require_text(fields['station'], 'station'),
        parse_day(fields['day']),
        require_positive_int(fields['revision'], 'revision'),
        require_text(fields['submission_id'], 'submission ID'),
        rows,
        reconcile_site(rows, fields['total_litres']),
    )


def piece_digest(piece):
    return sha256(canonical_json(piece.as_dict())).hexdigest()
