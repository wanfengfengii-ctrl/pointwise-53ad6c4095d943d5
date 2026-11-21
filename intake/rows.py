from dataclasses import dataclass

from accounting.measures import validate_reading
from intake.origins import SourceOrigin, parse_origin
from ledger_support import InvalidData, require_fields


@dataclass(frozen=True, slots=True)
class ObservationRow:
    litres: int | None
    origin: SourceOrigin

    def as_dict(self):
        return {'litres': self.litres, 'origin': self.origin.as_dict()}


def parse_rows(value):
    if not isinstance(value, (list, tuple)):
        raise InvalidData('Rows must be an ordered sequence')
    rows = []
    for position, raw in enumerate(value, 1):
        try:
            fields = require_fields(raw, ('litres', 'origin'), 'observation row')
            litres = validate_reading(fields['litres'])
            origin = parse_origin(fields['origin'])
        except InvalidData as error:
            raise InvalidData(f'Row {position}: {error}') from error
        rows.append(ObservationRow(litres, origin))
    return tuple(rows)
