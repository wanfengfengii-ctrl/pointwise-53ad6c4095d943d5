import hmac

from ledger_support import canonical_json


def pickup_seal(issuer, pickup_id, day, east_digest, west_digest):
    """Seal the joint activation, binding the two exact frozen station pieces.

    The digests are computed from the canonical station piece payloads, so the
    seal covers each side's role, station, day, revision, submission ID,
    original-order rows (readings and line-by-line origins) and subtotal.
    A spliced piece or a same-body replacement revision therefore cannot reuse
    a seal issued for another pair.
    """
    scope = [
        'regional-ledger/pickup/1',
        issuer.issuer_id,
        pickup_id,
        day,
        {'east': east_digest, 'west': west_digest},
    ]
    return hmac.digest(issuer.key, canonical_json(scope), 'sha256').hex()
