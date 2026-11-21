import copy

from intake.inbox import find_submission
from ledger import Conflict, IdentityError, InvalidData, NotFound, StorageError, apply, init, read_site
from tests.fixtures import DAY, OTHER_DAY, WorkspaceTest, reject_next_commit, submission


class SiteTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.path = self.folder / 'east.sqlite'
        self.site = init(self.path, 'east')

    def test_order_and_missing(self):
        raw = submission('east', 'E1', [7, None, 4])
        for row, source in zip(raw['rows'], ('A', 'B', 'C'), strict=True):
            row['origin']['register'] = source
        revision = apply(self.site, raw)
        reopened = init(self.path, 'east')
        with self.assertRaises(IdentityError):
            init(self.path, 'west')
        view = read_site(reopened, DAY)
        self.assertEqual(view.revision, revision.revision)
        self.assertEqual([(r.litres, r.origin.register, r.origin.line) for r in view.rows],
                         [(7, 'A', 1), (None, 'B', 2), (4, 'C', 3)])
        self.assertEqual(view.total_litres, 11)
        self.assertEqual(read_site(init(self.path, 'east'), DAY), view)

    def test_revision_readback(self):
        initial = apply(self.site, submission('east', 'E1', [7], register='original'))
        corrected = apply(self.site, submission('east', 'E2', [13], register='correction'))
        same_body = apply(self.site, submission('east', 'E3', [13], register='correction'))
        empty = apply(self.site, submission('east', 'E-empty', [], day=OTHER_DAY))
        reopened = init(self.path, 'east')
        self.assertEqual(corrected.previous_revision, initial.revision)
        self.assertEqual(same_body.previous_revision, corrected.revision)
        self.assertNotEqual(same_body.revision, corrected.revision)
        old_view = read_site(reopened, DAY, initial.revision)
        corrected_view = read_site(reopened, DAY, corrected.revision)
        same_body_view = read_site(reopened, DAY, same_body.revision)
        self.assertEqual((old_view.total_litres, old_view.rows[0].origin.register), (7, 'original'))
        self.assertEqual((corrected_view.total_litres, corrected_view.rows[0].origin.register),
                         (13, 'correction'))
        self.assertEqual((same_body_view.rows, same_body_view.total_litres), (corrected_view.rows, 13))
        self.assertEqual(read_site(reopened, DAY).revision, same_body.revision)
        self.assertEqual(read_site(reopened, OTHER_DAY).revision, empty.revision)
        self.assertEqual((read_site(reopened, OTHER_DAY).rows, read_site(reopened, OTHER_DAY).total_litres),
                         ((), 0))
        with self.assertRaises(NotFound):
            read_site(reopened, '2030-04-11')
        with self.assertRaises(NotFound):
            read_site(reopened, DAY, empty.revision)

    def test_submission_conflict(self):
        first = submission('east', 'E1', [7], register='original')
        original = apply(self.site, first)
        changed_origin = copy.deepcopy(first)
        changed_origin['rows'][0]['origin']['register'] = 'another book'
        with self.assertRaises(Conflict):
            apply(self.site, changed_origin)
        with self.assertRaises(Conflict):
            apply(self.site, submission('east', 'E1', [8], register='original'))
        with self.assertRaises(Conflict):
            apply(self.site, submission('east', 'E1', [7], day=OTHER_DAY, register='original'))
        self.assertEqual(read_site(self.site, DAY).revision, original.revision)
        self.assertEqual(read_site(self.site, DAY).rows[0].origin.register, 'original')
        later = apply(self.site, submission('east', 'E2', [13]))
        self.assertEqual(apply(init(self.path, 'east'), first), original)
        self.assertEqual(read_site(self.site, DAY).revision, later.revision)
        self.assertEqual(read_site(self.site, DAY, original.revision).rows[0].origin.register, 'original')

    def test_atomic_apply(self):
        for has_prior in (False, True):
            with self.subTest(has_prior=has_prior):
                path = self.folder / f'atomic-{has_prior}.sqlite'
                site = init(path, 'east')
                prior = apply(site, submission('east', 'prior', [7])) if has_prior else None
                attempted = submission('east', 'attempt', [13, None])
                with reject_next_commit(path, 'revisions'):
                    with self.assertRaisesRegex(StorageError, 'FOREIGN KEY constraint failed'):
                        apply(site, attempted)
                    reopened = init(path, 'east')
                    with reopened.read_transaction() as connection:
                        self.assertIsNone(find_submission(connection, 'east', 'attempt'))
                        self.assertEqual(connection.execute('SELECT count(*) FROM revisions').fetchone()[0],
                                         int(has_prior))
                        self.assertEqual(connection.execute('SELECT count(*) FROM submission_rows').fetchone()[0],
                                         int(has_prior))
                    if prior is None:
                        with self.assertRaises(NotFound):
                            read_site(reopened, DAY)
                    else:
                        self.assertEqual(read_site(reopened, DAY).revision, prior.revision)
                        self.assertEqual(read_site(reopened, DAY).total_litres, 7)
                applied = apply(reopened, attempted)
                self.assertEqual(read_site(reopened, DAY).revision, applied.revision)
                self.assertEqual(read_site(reopened, DAY).total_litres, 13)

    def test_invalid_submission_is_rejected_before_registration(self):
        valid = submission('east', 'E1', [7])
        bad_day = dict(valid, day='2030-02-30')
        no_origin = dict(valid, rows=[{'litres': 7}])
        for raw in (bad_day, no_origin, submission('east', 'E1', [True]),
                    submission('east', 'E1', [7.0]), submission('west', 'E1', [7])):
            with self.subTest(raw=raw), self.assertRaises(InvalidData):
                apply(self.site, raw)
        with self.assertRaises(NotFound):
            read_site(self.site, DAY)
        self.assertEqual(apply(self.site, valid).revision, 1)
