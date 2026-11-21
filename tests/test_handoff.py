import json

from ledger import CaptureRetry, Conflict, IssuedStore, InvalidData, NotFound, admit, apply, encode_package
from tests.fixtures import DAY, LedgerFixture, submission


class HandoffTests(LedgerFixture):
    def test_stable_pair(self):
        east, west = self.activate_pair()
        package = self.pickup('stable')
        self.assertEqual((east.revision, west.revision), (1, 1))
        self.assertEqual((package.east.role, package.east.station, package.east.revision), ('east', 'east', 1))
        self.assertEqual((package.west.role, package.west.station, package.west.revision), ('west', 'west', 1))
        self.assertEqual(package.totals.as_dict(), {'east_litres': 7, 'west_litres': 11, 'total_litres': 18})
        self.assertEqual((package.east.rows[0].origin.register, package.west.rows[0].origin.register),
                         ('E1', 'W1'))
        apply(self.east, submission('east', 'E2', [13]))
        apply(self.west, submission('west', 'W2', [17]))
        reopened = IssuedStore(self.issued.path)
        self.assertEqual(reopened.read_issued('stable'), package)
        with self.assertRaises(Conflict):
            self.pickup('stable')
        self.assertEqual(reopened.read_issued('stable'), package)
        report, _ = admit(self.archive, encode_package(package), self.config)
        self.assertEqual((report.east.rows[0].litres, report.west.rows[0].litres, report.totals.total_litres),
                         (7, 11, 18))

    def test_crossed_activation(self):
        east_one, west_one = self.activate_pair()
        active_pairs = [(east_one.revision, west_one.revision)]
        events = []

        def after_read(role, view):
            events.append([role, view.revision, view.total_litres])
            if len(events) == 1 and role == 'east':
                east_two = apply(self.east, submission('east', 'E2', [13], day=DAY))
                events.append(['east commit', east_two.revision, 13])
                active_pairs.append((east_two.revision, west_one.revision))
                west_two = apply(self.west, submission('west', 'W2', [17], day=DAY))
                events.append(['west commit', west_two.revision, 17])
                active_pairs.append((east_two.revision, west_two.revision))

        try:
            package = self.pickup('crossed', after_read=after_read)
        except CaptureRetry:
            with self.assertRaises(NotFound):
                self.issued.read_issued('crossed')
            self.assert_archive_counts(0, 0)
            stable_id = 'crossed'
        else:
            pair = (package.east.revision, package.west.revision)
            if pair not in active_pairs:
                try:
                    wrong, _ = admit(self.archive, encode_package(package), self.config)
                except InvalidData as error:
                    self.fail(f'MIXED_ACTIVE_REVISIONS issued {pair}; archive rejected: {error}')
                self.fail(f'MIXED_ACTIVE_REVISIONS issued {pair}; signed {wrong.totals.total_litres} L; events={events}')
            valid, _ = admit(self.archive, encode_package(package), self.config)
            self.assertEqual((valid.east.revision, valid.west.revision), pair)
            stable_id = 'stable-after-crossed'

        self.assertEqual(events[:4], [['east', 1, 7], ['east commit', 2, 13],
                                      ['west commit', 2, 17], ['west', 2, 17]])
        stable = self.pickup(stable_id)
        self.assertEqual((stable.east.revision, stable.west.revision), (2, 2))
        received, _ = admit(self.archive, encode_package(stable), self.config)
        actual = stable.totals.as_dict()
        expected = {'east_litres': 13, 'west_litres': 17, 'total_litres': 30}
        self.assertEqual(actual, expected)
        self.assertEqual(received.totals.as_dict(), expected)
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'T5.stable_retry',
            'input': {'events': events, 'active_pairs': active_pairs},
            'expected': expected,
            'actual': actual,
            'downstream_expected': expected,
            'downstream_actual': received.totals.as_dict(),
            'code_paths': ['exchange/capture.py', 'exchange/witness.py', 'archive/admission.py'],
            'oracle': 'Track pairs between the two real commits. After both commits add 13 and 17.',
        }, sort_keys=True))

    def test_missing_station_day_can_be_retried(self):
        apply(self.east, submission('east', 'E1', [7]))
        with self.assertRaises(CaptureRetry):
            self.pickup('waiting')
        with self.assertRaises(NotFound):
            self.issued.read_issued('waiting')
        apply(self.west, submission('west', 'W1', []))
        package = self.pickup('waiting')
        self.assertEqual(package.west.rows, ())
        report, _ = admit(self.archive, encode_package(package), self.config)
        self.assertEqual((report.west.total_litres, report.totals.total_litres), (0, 7))
