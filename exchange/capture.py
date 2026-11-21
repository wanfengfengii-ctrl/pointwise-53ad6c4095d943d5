from exchange.package import freeze_package
from exchange.station_piece import make_station_piece, piece_digest
from exchange.witness import pickup_seal
from intake.submission import parse_day
from ledger_support import (
    CaptureRetry,
    IdentityError,
    NotFound,
    canonical_json,
    require_text,
)
from revisions.current import read_site


def _read_piece(store, role, day, after_read):
    view = read_site(store, day)
    if after_read is not None:
        after_read(role, view)
    return make_station_piece(role, view)


def _confirm(store, day, candidate):
    """Re-read a station without callbacks and ensure the candidate still holds.

    A revision pointer only advances, never moves back. If the second read of
    the same station day returns the candidate revision, that revision was the
    current one at both reads, so it was active while the other side was read.
    A change means this call cannot prove a jointly active pair and must retry.
    """
    view = read_site(store, day)
    if view.revision != candidate.revision:
        raise CaptureRetry(
            f'Station {store.station} changed revision during the pickup; retry the same pickup ID'
        )
    return make_station_piece(candidate.role, view)


def capture(issued, issuer, pickup_id, day, east_store, west_store, *, after_read=None):
    "Issue the current station returns as a fixed pickup."
    pickup_id = require_text(pickup_id, "pickup ID")
    day = parse_day(day)
    if (east_store.station, west_store.station) != (issuer.east_station, issuer.west_station):
        raise IdentityError("Site roles do not match the issuer configuration")
    try:
        east = _read_piece(east_store, "east", day, after_read)
        west = _read_piece(west_store, "west", day, after_read)
        # Second pass in the same order proves both candidate revisions were
        # jointly active during this call before anything is fixed.
        east = _confirm(east_store, day, east)
        west = _confirm(west_store, day, west)
    except NotFound as error:
        raise CaptureRetry(f"Pickup {pickup_id} lacks a current station day") from error
    seal = pickup_seal(issuer, pickup_id, day, piece_digest(east), piece_digest(west))
    evidence = canonical_json({"seal": seal})
    package = freeze_package(pickup_id, day, issuer.issuer_id, east, west, evidence)
    issued.save_issued(package)
    return package
