import hmac

from accounting.reconcile import reconcile_handoff
from archive.publication import publish_report
from archive.trust import resolve_issuer
from exchange.package import decode_package
from exchange.witness import pickup_seal
from ledger_support import InvalidData, load_json, require_fields


def _check_placement(package, issuer):
    for role, piece, station in (
        ("east", package.east, issuer.east_station),
        ("west", package.west, issuer.west_station),
    ):
        if (piece.role, piece.station, piece.day) != (role, station, package.day):
            raise InvalidData(f"Unexpected station, role, or day for {role} piece")


def _check_pickup_seal(package, issuer):
    if package.evidence is None:
        return
    fields = require_fields(load_json(package.evidence), ("seal",), "pickup evidence")
    seal = fields["seal"]
    expected = pickup_seal(issuer, package.pickup_id, package.day)
    if type(seal) is not str or not seal.isascii() or not hmac.compare_digest(seal, expected):
        raise InvalidData("Pickup seal does not match the configured issuer")


def admit(archive, raw, trusted_issuers):
    "Admit received bytes using the local issuer configuration."
    package = decode_package(raw)
    issuer = resolve_issuer(trusted_issuers, package.issuer_id)
    _check_placement(package, issuer)
    _check_pickup_seal(package, issuer)
    totals = reconcile_handoff(package.east.total_litres, package.west.total_litres, package.totals)
    return publish_report(archive, package, totals)
