from dataclasses import dataclass
from datetime import date

from intake.rows import ObservationRow, parse_rows
from ledger_support import InvalidData, require_fields, require_text


@dataclass(frozen=True, slots=True)
class Submission:
    station: str
    day: str
    submission_id: str
    rows: tuple[ObservationRow, ...]


def parse_day(value):
    value = require_text(value, 'station day')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise InvalidData('Station day must be a real YYYY-MM-DD date') from error
    if parsed.isoformat() != value:
        raise InvalidData('Station day must use YYYY-MM-DD')
    return value


def parse_submission(value):
    fields = require_fields(value, ('station', 'day', 'submission_id', 'rows'), 'submission')
    return Submission(
        require_text(fields['station'], 'station'),
        parse_day(fields['day']),
        require_text(fields['submission_id'], 'submission ID'),
        parse_rows(fields['rows']),
    )
