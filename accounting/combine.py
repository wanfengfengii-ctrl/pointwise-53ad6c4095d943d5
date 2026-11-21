from dataclasses import dataclass

from ledger_support import InvalidData, require_fields


@dataclass(frozen=True, slots=True)
class CombinedTotals:
    east_litres: int
    west_litres: int
    total_litres: int

    def as_dict(self):
        return {
            'east_litres': self.east_litres,
            'west_litres': self.west_litres,
            'total_litres': self.total_litres,
        }


def combine_totals(east_litres, west_litres):
    return CombinedTotals(east_litres, west_litres, east_litres + west_litres)


def parse_totals(value):
    fields = require_fields(value, ('east_litres', 'west_litres', 'total_litres'), 'combined totals')
    if any(type(amount) is not int for amount in fields.values()):
        raise InvalidData('All declared totals must be integer litres')
    return CombinedTotals(**fields)
