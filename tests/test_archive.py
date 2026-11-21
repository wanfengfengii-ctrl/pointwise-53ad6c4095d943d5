import json
from dataclasses import replace

from archive.receipts import read_receipt
from exchange.package import freeze_package
from ledger import (Conflict, InvalidData, IssuedStore, NotFound, StorageError, TrustedIssuer,
                    admit, apply, capture, encode_package, open_archive, read_report)
from tests.fixtures import DAY, LedgerFixture, reject_next_commit, submission


class ArchiveTests(LedgerFixture):
    def test_offline_readback(self):
        east, west = self.activate_pair((7, None, 0, 0), (11,))
        raw = encode_package(self.pickup('offline'))
        apply(self.east, submission('east', 'E2', [13]))
        apply(self.west, submission('west', 'W2', [17]))
        self.take_sources_offline()
        report, receipt = admit(self.archive, raw, self.config)
        loaded = read_report(open_archive(self.archive.path), receipt.account_no)
        self.assertEqual(loaded, report)
        self.assertEqual((loaded.east.revision, loaded.west.revision), (east.revision, west.revision))
        self.assertEqual(loaded.day, DAY)
        self.assertEqual(loaded.totals.as_dict(), {'east_litres': 7, 'west_litres': 11, 'total_litres': 18})
        self.assertEqual([(r.litres, r.origin.register, r.origin.line) for r in loaded.east.rows],
                         [(7, 'E1', 1), (None, 'E1', 2), (0, 'E1', 3), (0, 'E1', 4)])
        self.assertEqual([(r.litres, r.origin.register, r.origin.line) for r in loaded.west.rows],
                         [(11, 'W1', 1)])
        self.assert_archive_counts(1, 1)
        with self.assertRaises(NotFound):
            read_report(self.archive, receipt.account_no + 1)

    def test_spliced_pair(self):
        east, _ = self.activate_pair()
        original = self.pickup('original')
        replacement = apply(self.east, submission('east', 'E2', [7], register='E1'))
        later = self.pickup('later')
        self.assertEqual(later.east.rows, original.east.rows)
        self.assertNotEqual(replacement.revision, east.revision)
        splice = replace(original, east=later.east)
        self.take_sources_offline()
        with self.assertRaises(InvalidData):
            admit(self.archive, encode_package(splice), self.config)
        self.assert_archive_counts(0, 0)
        report, receipt = admit(self.archive, encode_package(original), self.config)
        self.assertEqual((report.east.revision, report.east.rows[0].origin.register), (east.revision, 'E1'))
        self.assertEqual(receipt.pickup_id, 'original')
        later_report, _ = admit(self.archive, encode_package(later), self.config)
        self.assertEqual(later_report.east.revision, replacement.revision)
        self.assert_archive_counts(2, 2)

    def test_independent_pieces(self):
        self.activate_pair()
        earlier = self.pickup('earlier')
        apply(self.east, submission('east', 'E2', [13]))
        apply(self.west, submission('west', 'W2', [17]))
        later = self.pickup('later')
        spliced = freeze_package('two-site-pieces', DAY, self.issuer.issuer_id,
                                 earlier.east, later.west, None)
        self.assertEqual(spliced.totals.total_litres, 24)
        self.take_sources_offline()
        with self.assertRaises(InvalidData):
            admit(self.archive, encode_package(spliced), self.config)
        self.assert_archive_counts(0, 0)
        original, _ = admit(self.archive, encode_package(earlier), self.config)
        final, _ = admit(self.archive, encode_package(later), self.config)
        self.assertEqual((original.totals.total_litres, final.totals.total_litres), (18, 30))
        self.assert_archive_counts(2, 2)

    def test_publish_retry(self):
        self.activate_pair()
        original = self.pickup('retry')
        raw = encode_package(original)
        apply(self.east, submission('east', 'E2', [13]))
        alternate_issued = IssuedStore(self.folder / 'second-issuer-log.sqlite')
        alternate = capture(alternate_issued, self.issuer, 'retry', DAY, self.east, self.west)
        self.take_sources_offline()
        with reject_next_commit(self.archive.path, 'receipts'):
            with self.assertRaisesRegex(StorageError, 'FOREIGN KEY constraint failed'):
                admit(self.archive, raw, self.config)
            self.archive = open_archive(self.archive.path)
            with self.assertRaises(NotFound):
                read_report(self.archive, 1)
            with self.archive.read_transaction() as connection:
                self.assertIsNone(read_receipt(connection, 'retry'))
            self.assert_archive_counts(0, 0)
        report, receipt = admit(self.archive, raw, self.config)
        self.archive = open_archive(self.archive.path)
        formatted = json.dumps(json.loads(raw), indent=2)
        self.assertEqual(admit(self.archive, raw, self.config), (report, receipt))
        self.assertEqual(admit(self.archive, formatted, self.config), (report, receipt))
        with self.assertRaises(Conflict):
            admit(self.archive, encode_package(alternate), self.config)
        self.assert_archive_counts(1, 1)
        self.assertEqual(read_report(self.archive, receipt.account_no), report)
        self.assertEqual(report.totals.total_litres, 18)
        with self.archive.read_transaction() as connection:
            self.assertEqual(read_receipt(connection, 'retry'), receipt)

    def test_wrong_claims_and_untrusted_issuer_leave_no_report(self):
        self.activate_pair()
        raw = encode_package(self.pickup('verified'))
        wrong_key = TrustedIssuer(self.issuer.issuer_id, b'j' * 32, 'east', 'west')
        wrong_roles = TrustedIssuer(self.issuer.issuer_id, self.issuer.key, 'west', 'east')
        for config in ({}, {wrong_key.issuer_id: wrong_key}, {wrong_roles.issuer_id: wrong_roles}):
            with self.assertRaises(InvalidData):
                admit(self.archive, raw, config)
        for field, wrong in (('pickup_id', 'renamed'), ('day', '2030-04-10'), ('version', True)):
            malformed = json.loads(raw)
            malformed[field] = wrong
            with self.assertRaises(InvalidData):
                admit(self.archive, json.dumps(malformed), self.config)
        malformed = json.loads(raw)
        malformed['totals']['total_litres'] = 11
        with self.assertRaises(InvalidData):
            admit(self.archive, json.dumps(malformed), self.config)
        malformed = json.loads(raw)
        malformed['east']['total_litres'] = 11
        with self.assertRaises(InvalidData):
            admit(self.archive, json.dumps(malformed), self.config)
        with self.assertRaises(InvalidData):
            admit(self.archive, b'{"version":1,' + raw[1:], self.config)
        self.assert_archive_counts(0, 0)
        admit(self.archive, raw, self.config)
        self.assert_archive_counts(1, 1)

    def test_integer_precision_survives_offline_publication(self):
        self.activate_pair((9223372036854775808, None, 7), (11,))
        package = self.pickup('large')
        self.take_sources_offline()
        _, receipt = admit(self.archive, encode_package(package), self.config)
        archived = read_report(open_archive(self.archive.path), receipt.account_no)
        self.assertEqual(archived.east.total_litres, 9223372036854775815)
        self.assertEqual(archived.totals.total_litres, 9223372036854775826)
        self.assertIsNone(archived.east.rows[1].litres)
