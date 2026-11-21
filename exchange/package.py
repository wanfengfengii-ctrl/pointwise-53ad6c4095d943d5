from dataclasses import dataclass
from hashlib import sha256

from accounting.combine import CombinedTotals, combine_totals, parse_totals
from exchange.station_piece import StationPiece, parse_station_piece
from intake.submission import parse_day
from ledger_support import InvalidData, canonical_json, load_json, require_fields, require_text


@dataclass(frozen=True, slots=True)
class HandoffPackage:
    pickup_id: str
    day: str
    issuer_id: str
    east: StationPiece
    west: StationPiece
    totals: CombinedTotals
    evidence: bytes | None


def freeze_package(pickup_id, day, issuer_id, east, west, evidence):
    if east.role != 'east' or west.role != 'west' or east.station == west.station:
        raise InvalidData('A handoff requires separate east and west station pieces')
    if east.day != day or west.day != day:
        raise InvalidData('Station pieces must belong to the requested day')
    totals = combine_totals(east.total_litres, west.total_litres)
    return HandoffPackage(pickup_id, day, issuer_id, east, west, totals, evidence)


def encode_package(package):
    evidence = None if package.evidence is None else load_json(package.evidence)
    return canonical_json({
        'version': 1,
        'pickup_id': package.pickup_id,
        'day': package.day,
        'issuer_id': package.issuer_id,
        'east': package.east.as_dict(),
        'west': package.west.as_dict(),
        'totals': package.totals.as_dict(),
        'evidence': evidence,
    })


def decode_package(raw):
    fields = require_fields(load_json(raw), (
        'version', 'pickup_id', 'day', 'issuer_id', 'east', 'west', 'totals', 'evidence',
    ), 'V1 handoff envelope')
    if type(fields['version']) is not int or fields['version'] != 1:
        raise InvalidData('Unsupported handoff version')
    evidence = fields['evidence']
    if evidence is not None and type(evidence) is not dict:
        raise InvalidData('Evidence must be a JSON object or null')
    return HandoffPackage(
        require_text(fields['pickup_id'], 'pickup ID'),
        parse_day(fields['day']),
        require_text(fields['issuer_id'], 'issuer ID'),
        parse_station_piece(fields['east']),
        parse_station_piece(fields['west']),
        parse_totals(fields['totals']),
        None if evidence is None else canonical_json(evidence),
    )


def package_identity(canonical_payload):
    """Identify a complete handoff encoded by encode_package."""
    return sha256(canonical_payload).hexdigest()
