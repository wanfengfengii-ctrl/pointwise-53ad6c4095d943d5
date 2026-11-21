from ledger import run_demo
from tests.fixtures import WorkspaceTest


class WorkflowTests(WorkspaceTest):
    def test_night_shift_from_sample_slips_to_reopened_archive(self):
        scenario = run_demo(self.folder)
        self.assertEqual(scenario['case_id'], 'T6.exact_totals')
        self.assertEqual(scenario['actual'], {'east_litres': 7, 'west_litres': 11, 'total_litres': 18})
        actual = scenario['downstream_actual']
        self.assertEqual(actual['account_no'], 1)
        self.assertEqual(actual['revisions'], {'east': 2, 'west': 1})
        self.assertEqual([row['litres'] for row in actual['east_rows']], [7, None, 0])
        self.assertEqual([row['origin']['register'] for row in actual['east_rows']],
                         ['东站更正簿', '东站日簿', '东站日簿'])
        self.assertEqual(actual['west_rows'], [{'litres': 11, 'origin': {'register': '西站日簿', 'line': 1}}])
        self.assertEqual(actual['totals']['total_litres'], 18)
        self.assertTrue(actual['original_receipt'])
        for name in ('east', 'west'):
            self.assertFalse((self.folder / f'{name}.sqlite').exists())
            self.assertTrue((self.folder / f'{name}.offline').exists())
