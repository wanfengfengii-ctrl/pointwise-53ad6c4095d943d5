from exchange.package import freeze_package
from exchange.station_piece import make_station_piece
from exchange.witness import pickup_seal
from intake.submission import parse_day
from ledger_support import CaptureRetry, IdentityError, NotFound, canonical_json, require_text
from revisions.current import read_site


def _observe(store, role, day, after_read):
    view = read_site(store, day)
    if after_read is not None:
        after_read(role, view)
    return make_station_piece(role, view)


def capture(issued, issuer, pickup_id, day, east_store, west_store, *, after_read=None):
    "Issue the current station returns as a fixed pickup."
    pickup_id = require_text(pickup_id, "pickup ID")
    day = parse_day(day)
    if (east_store.station, west_store.station) != (issuer.east_station, issuer.west_station):
        raise IdentityError("Site roles do not match the issuer configuration")
    try:
        east = _observe(east_store, "east", day, after_read)
        west = _observe(west_store, "west", day, after_read)
    except NotFound as error:
        raise CaptureRetry(f"Pickup {pickup_id} lacks a current station day") from error
    evidence = canonical_json({"seal": pickup_seal(issuer, pickup_id, day)})
    package = freeze_package(pickup_id, day, issuer.issuer_id, east, west, evidence)
    issued.save_issued(package)
    return package
