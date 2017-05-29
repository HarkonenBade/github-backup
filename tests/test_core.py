import unittest
from unittest import mock

import ghbackup


class TestLoggingInfoCase(unittest.TestCase):
    def test_normal(self):
        with self.assertLogs(level='INFO') as lm:
            ghbackup.info("This is a {} of {info}", 'test', info='logging')
        self.assertEqual(lm.output, ['INFO:root:This is a test of logging'])


class TestGitHubAuth(unittest.TestCase):
    def setUp(self):
        self.auth = ghbackup.GitHubAuth("secrettoken")
        self.auth.ghub = mock.Mock()

    def test_embed_url(self):
        self.auth.user = "harkonenbade"
        self.assertEqual(self.auth.embed_auth_in_url("https://github.com/harkonenbade/github-backup"),
                         "https://harkonenbade:secrettoken@github.com/harkonenbade/github-backup")

    def test_test_token_normal(self):
        self.auth.ghub.user.get.return_value = (200, {'login': mock.sentinel.ghub_user})
        self.assertTrue(self.auth.test_token())
        self.assertEqual(self.auth.user, mock.sentinel.ghub_user)

    def test_test_token_failed_auth(self):
        self.auth.ghub.user.get.return_value = (401, 'marker')
        with self.assertLogs(level='ERROR'):
            self.assertFalse(self.auth.test_token())
        self.assertIsNone(self.auth.user)

    def test_test_token_rate_limited(self):
        self.auth.ghub.user.get.return_value = (403, 'marker')
        with self.assertLogs(level='ERROR'):
            self.assertFalse(self.auth.test_token())
        self.assertIsNone(self.auth.user)

    def test_test_token_unknown_error(self):
        self.auth.ghub.user.get.return_value = (128, 'marker')
        with self.assertLogs(level='ERROR') as lg:
            self.assertFalse(self.auth.test_token())
        self.assertIsNone(self.auth.user)
        self.assertIn(str(128), lg.output[0])
        self.assertIn('marker', lg.output[0])


if __name__ == '__main__':
    unittest.main()
