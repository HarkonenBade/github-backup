import unittest
from unittest import mock

import ghbackup


class TestLoggingInfoCase(unittest.TestCase):
    def test_normal(self):
        with self.assertLogs(level='INFO') as lm:
            ghbackup.info("This is a {} of {info}", 'test', info='logging')
        self.assertEqual(lm.output, ['INFO:root:Info: This is a test of logging'])


class TestURLManipulationCase(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(ghbackup.embed_auth_in_url("https://github.com/harkonenbade/github-backup",
                                                    "harkonenbade",
                                                    "secrettoken"),
                         "https://harkonenbade:secrettoken@github.com/harkonenbade/github-backup")


class TestTokenCheckCase(unittest.TestCase):
    def setUp(self):
        self.ghub = mock.Mock()

    def test_normal(self):
        self.ghub.user.get.return_value = (200, mock.sentinel.ghub_user)
        ret = ghbackup.test_token(self.ghub)
        self.assertEqual(ret, mock.sentinel.ghub_user)

    def test_failed_auth(self):
        self.ghub.user.get.return_value = (401, 'marker')
        with self.assertLogs(level='ERROR'):
            ret = ghbackup.test_token(self.ghub)
        self.assertIsNone(ret)

    def test_rate_limited(self):
        self.ghub.user.get.return_value = (403, 'marker')
        with self.assertLogs(level='ERROR'):
            ret = ghbackup.test_token(self.ghub)
        self.assertIsNone(ret)

    def test_unknown_error(self):
        self.ghub.user.get.return_value = (128, 'marker')
        with self.assertLogs(level='ERROR') as lg:
            ret = ghbackup.test_token(self.ghub)
        self.assertIsNone(ret)
        self.assertIn(str(128), lg.output[0])
        self.assertIn('marker', lg.output[0])


if __name__ == '__main__':
    unittest.main()
