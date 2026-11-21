from dataclasses import dataclass, field

from ledger_support import InvalidData, require_text


@dataclass(frozen=True, slots=True)
class TrustedIssuer:
    issuer_id: str
    key: bytes = field(repr=False)
    east_station: str
    west_station: str

    def __post_init__(self):
        require_text(self.issuer_id, 'issuer ID')
        require_text(self.east_station, 'east station')
        require_text(self.west_station, 'west station')
        if self.east_station == self.west_station:
            raise InvalidData('Issuer must bind two different stations')
        if type(self.key) is not bytes or len(self.key) < 32:
            raise InvalidData('Issuer key must contain at least 32 bytes')


def resolve_issuer(config, issuer_id):
    issuer = config.get(issuer_id)
    if not isinstance(issuer, TrustedIssuer) or issuer.issuer_id != issuer_id:
        raise InvalidData(f'Unknown trusted issuer {issuer_id!r}')
    return issuer
