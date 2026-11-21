import hmac

from ledger_support import canonical_json


def pickup_seal(issuer, pickup_id, day):
    scope = ["regional-ledger/pickup/1", issuer.issuer_id, pickup_id, day]
    return hmac.digest(issuer.key, canonical_json(scope), "sha256").hex()
