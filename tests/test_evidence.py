import json
from dataclasses import replace

from exchange.package import freeze_package
from exchange.station_piece import parse_station_piece, piece_digest
from exchange.witness import pickup_seal
from ledger import (
    CaptureRetry,
    InvalidData,
    admit,
    apply,
    encode_package,
    read_report,
)
from tests.fixtures import DAY, LedgerFixture, submission


def _sealed(pickup_id, east, west, issuer_id, issuer):
    seal = pickup_seal(issuer, pickup_id, DAY, piece_digest(east), piece_digest(west))
    evidence = json.dumps({'seal': seal}).encode('utf-8')
    return freeze_package(pickup_id, DAY, issuer_id, east, west, evidence)


class EvidenceTests(LedgerFixture):
    def test_west_side_change_between_reads_is_retried_then_30_litres(self):
        # Symmetric counterpart of the incident's east-first crossing: the west
        # station commits between the two west reads of the same call.
        east_one, west_one = self.activate_pair()
        events = []

        def after_read(role, view):
            events.append((role, view.revision))
            if len(events) == 2 and role == 'west':
                apply(self.east, submission('east', 'E2', [13], day=DAY))
                apply(self.west, submission('west', 'W2', [17], day=DAY))

        with self.assertRaises(CaptureRetry):
            self.pickup('west-crossed', after_read=after_read)
        with self.assertRaises(Exception):
            self.issued.read_issued('west-crossed')
        self.assert_archive_counts(0, 0)

        stable_events = []
        stable = self.pickup('west-crossed', after_read=lambda role, view: stable_events.append((role, view.revision)))
        self.assertEqual((stable.east.revision, stable.west.revision), (2, 2))
        report, receipt = admit(self.archive, encode_package(stable), self.config)
        self.assertEqual(report.totals.as_dict(),
                         {'east_litres': 13, 'west_litres': 17, 'total_litres': 30})
        self.assertEqual((report.east.revision, report.west.revision), (2, 2))
        # Each attempt's callbacks only observe its two candidate reads.
        self.assertEqual(events, [('east', 1), ('west', 1)])
        self.assertEqual(stable_events, [('east', 2), ('west', 2)])
        reloaded = read_report(self.archive, receipt.account_no)
        self.assertEqual(reloaded, report)

    def test_missing_evidence_is_rejected_without_ledger_rows(self):
        self.activate_pair()
        first = self.pickup('first')
        bare = freeze_package('no-evidence', DAY, self.issuer.issuer_id,
                              first.east, first.west, None)
        with self.assertRaises(InvalidData):
            admit(self.archive, encode_package(bare), self.config)
        self.assert_archive_counts(0, 0)

    def test_forged_or_stolen_seal_is_rejected_without_ledger_rows(self):
        east, west = self.activate_pair()
        original = self.pickup('sealed')
        forged = json.loads(encode_package(original))
        forged['evidence'] = {'seal': '00' * 32}
        with self.assertRaises(InvalidData):
            admit(self.archive, json.dumps(forged), self.config)

        # A seal generated for another pickup ID cannot be transferred.
        foreign = _sealed('other-pickup', original.east, original.west,
                          self.issuer.issuer_id, self.issuer)
        relabelled = replace(foreign, pickup_id=original.pickup_id)
        with self.assertRaises(InvalidData):
            admit(self.archive, encode_package(relabelled), self.config)
        self.assert_archive_counts(0, 0)

    def test_seal_binds_exact_revision_rows_and_origins(self):
        self.activate_pair()
        original = self.pickup('bound')

        # Same reading and origin, but a fresh revision of the east station day.
        replacement = apply(self.east, submission('east', 'E2', [7], register='E1'))
        self.assertNotEqual(replacement.revision, original.east.revision)
        later = self.pickup('later')
        self.assertEqual(later.east.rows, original.east.rows)
        same_body_splice = replace(original, east=later.east)
        with self.assertRaises(InvalidData):
            admit(self.archive, encode_package(same_body_splice), self.config)

        # Rewriting a row value while keeping the declared subtotal consistent.
        east_dict = original.east.as_dict()
        east_dict['rows'] = [{'litres': 6, 'origin': {'register': 'E1', 'line': 1}}]
        east_dict['total_litres'] = 6
        tampered_east = parse_station_piece(east_dict)
        retotaled = replace(original, east=tampered_east)
        retotaled = replace(retotaled, totals=replace(
            retotaled.totals, east_litres=6, total_litres=17))
        with self.assertRaises(InvalidData):
            admit(self.archive, encode_package(retotaled), self.config)

        # Rewriting an origin line must break the piece digest as well.
        origin_dict = original.east.as_dict()
        origin_dict['rows'] = [{'litres': 7, 'origin': {'register': 'E1', 'line': 9}}]
        shifted_origin = parse_station_piece(origin_dict)
        with self.assertRaises(InvalidData):
            admit(self.archive, encode_package(replace(original, east=shifted_origin)), self.config)
        self.assert_archive_counts(0, 0)

        # The untouched original still admits and replays to the same account.
        report, receipt = admit(self.archive, encode_package(original), self.config)
        self.assertEqual(admit(self.archive, encode_package(original), self.config),
                         (report, receipt))
        self.assert_archive_counts(1, 1)
