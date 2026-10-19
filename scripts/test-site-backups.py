import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('backup', Path(__file__).with_name('backup-site-data.py'))
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class RetentionTests(unittest.TestCase):
    def test_keep_fourteen_distinct_days(self):
        records = [(f'hhh-sites-202610{day:02d}T033000Z.tar.gz.gpg', str(day))
                   for day in range(1, 21)]
        self.assertEqual(backup.retained_daily_ids(records, 14), {str(day) for day in range(7, 21)})

    def test_rerun_does_not_evict_previous_day(self):
        records = [('hhh-sites-20261019T033000Z.tar.gz.gpg', 'early'),
                   ('hhh-sites-20261019T043000Z.tar.gz.gpg', 'late'),
                   ('hhh-sites-20261018T033000Z.tar.gz.gpg', 'yesterday')]
        self.assertEqual(backup.retained_daily_ids(records, 2), {'late', 'yesterday'})

    def test_foreign_files_are_never_rotation_candidates(self):
        listing = ('safe|hhh-sites-20261019T033000Z.tar.gz.gpg|regular|100\n'
                   'foreign|database.sql|regular|100\n'
                   'partial|hhh-sites-20261019T033000Z.tar.gz.gpg.partial|regular|100\n')
        self.assertEqual(backup.parse_backup_listing(listing),
                         [('hhh-sites-20261019T033000Z.tar.gz.gpg', 'safe')])


if __name__ == '__main__':
    unittest.main()
