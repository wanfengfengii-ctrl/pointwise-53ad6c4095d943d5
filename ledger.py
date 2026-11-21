import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.admission import admit as admit
from archive.lookup import read_report as read_report
from archive.store import open_archive as open_archive
from archive.trust import TrustedIssuer as TrustedIssuer
from exchange.capture import capture as capture
from exchange.issued import IssuedStore as IssuedStore
from exchange.package import decode_package as decode_package
from exchange.package import encode_package as encode_package
from intake.apply import apply as apply
from ledger_support import CaptureRetry as CaptureRetry
from ledger_support import Conflict as Conflict
from ledger_support import IdentityError as IdentityError
from ledger_support import InvalidData as InvalidData
from ledger_support import LedgerError as LedgerError
from ledger_support import NotFound as NotFound
from ledger_support import StorageError as StorageError
from revisions.current import read_site as read_site
from revisions.site_store import init as init


def _read_sample(station):
    path = Path(__file__).with_name('samples') / f'{station}.json'
    return json.loads(path.read_text(encoding='utf-8'))


def run_demo(directory):
    east_initial, east_correction, east_next = _read_sample('east')
    west_initial, west_next = _read_sample('west')
    day = east_initial['day']
    east = init(directory / 'east.sqlite', 'east')
    west = init(directory / 'west.sqlite', 'west')
    first_east = apply(east, east_initial)
    apply(west, west_initial)
    initial = (read_site(east, day).total_litres, read_site(west, day).total_litres)
    apply(east, east_correction)
    east = init(east.path, 'east')
    historical = read_site(east, day, first_east.revision)
    current = read_site(east, day)
    if (initial, historical.total_litres, current.total_litres) != ((5, 11), 5, 7):
        raise AssertionError('Initial, historical and corrected station totals disagree with the sample')

    issuer = TrustedIssuer('demo-night-issuer', b'fixed demonstration key for local sample only', 'east', 'west')
    issued = IssuedStore(directory / 'issued.sqlite')
    pickup = capture(issued, issuer, 'night-001', day, east, west)
    apply(east, east_next)
    apply(west, west_next)
    if (read_site(east, day).total_litres, read_site(west, day).total_litres) != (13, 17):
        raise AssertionError('Sample source revisions did not advance')
    for site in (east, west):
        site.path.rename(site.path.with_suffix('.offline'))
    wire = encode_package(IssuedStore(issued.path).read_issued(pickup.pickup_id))

    archive = open_archive(directory / 'archive.sqlite')
    config = {issuer.issuer_id: issuer}
    report, receipt = admit(archive, wire, config)
    reopened = open_archive(archive.path)
    delivered = read_report(reopened, receipt.account_no)
    replayed = admit(reopened, wire, config)
    expected = {'east_litres': 7, 'west_litres': 11, 'total_litres': 18}
    downstream_expected = {
        'account_no': 1,
        'revisions': {'east': 2, 'west': 1},
        'east_rows': east_correction['rows'],
        'west_rows': west_initial['rows'],
        'totals': expected,
        'original_receipt': True,
    }
    downstream_actual = {
        'account_no': delivered.account_no,
        'revisions': {'east': delivered.east.revision, 'west': delivered.west.revision},
        'east_rows': [row.as_dict() for row in delivered.east.rows],
        'west_rows': [row.as_dict() for row in delivered.west.rows],
        'totals': delivered.totals.as_dict(),
        'original_receipt': replayed == (report, receipt) and delivered == report,
    }
    actual = pickup.totals.as_dict()
    if actual != expected or downstream_actual != downstream_expected:
        raise AssertionError('Captured or offline ledger disagrees with the sample calculation')
    return {
        'case_id': 'T6.exact_totals',
        'input': {'east': east_correction, 'west': west_initial, 'source_paths_offline': True},
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': ['accounting/site_totals.py', 'exchange/capture.py', 'archive/admission.py',
                       'archive/publication.py', 'archive/lookup.py'],
        'oracle': 'Hand sum east 7 + 0 + 0 and west 11. Compare revision numbers from submission order and rows from the two sample slips.',
    }


def main():
    parser = argparse.ArgumentParser(description='Regional observation day ledger')
    parser.add_argument('command', choices=('demo',))
    parser.parse_args()
    with TemporaryDirectory(prefix='regional-ledger-') as directory:
        result = run_demo(Path(directory))
    print('POINTWISE_SCENARIO ' + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
