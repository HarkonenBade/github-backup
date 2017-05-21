import unittest
from unittest import mock

import ghbackup


class TestLoggingInfoCase(unittest.TestCase):
    def test_normal(self):
        with self.assertLogs(level='INFO') as lm:
            ghbackup.info("This is a {} of {info}", 'test', info='logging')
        self.assertEqual(lm.output, ['INFO:root:This is a test of logging'])


class TestURLManipulationCase(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(ghbackup.embed_auth_in_url("https://github.com/harkonenbade/github-backup",
                                                    "harkonenbade",
                                                    "secrettoken"),
                         "https://harkonenbade:secrettoken@github.com/harkonenbade/github-backup")


class TestTokenCheckCase(unittest.TestCase):
    @mock.patch('ghbackup.sys.exit')
    def test_normal(self, mock_exit):
        ghub = mock.Mock()
        ghub.user.get.return_value = (200, mock.sentinel.ghub_user)
        ret = ghbackup.test_token(ghub)
        self.assertEqual(ret, mock.sentinel.ghub_user)
        mock_exit.assert_not_called()

    @mock.patch('ghbackup.sys.exit')
    def test_failed_auth(self, mock_exit):
        ghub = mock.Mock()
        ghub.user.get.return_value = (401, None)
        with self.assertLogs(level='ERROR'):
            ret = ghbackup.test_token(ghub)
        mock_exit.assert_called_once_with(1)
        self.assertIsNone(ret)

    @mock.patch('ghbackup.sys.exit')
    def test_rate_limited(self, mock_exit):
        ghub = mock.Mock()
        ghub.user.get.return_value = (403, None)
        with self.assertLogs(level='ERROR'):
            ret = ghbackup.test_token(ghub)
        mock_exit.assert_called_once_with(1)
        self.assertIsNone(ret)

    @mock.patch('ghbackup.sys.exit')
    def test_unknown_error(self, mock_exit: mock.Mock):
        ghub = mock.Mock()
        ghub.user.get.return_value = (128, 'marker')
        with self.assertLogs(level='ERROR') as lg:
            ret = ghbackup.test_token(ghub)
        self.assertIsNone(ret)
        mock_exit.assert_called_once_with(1)
        self.assertIn(str(128), lg.output[0])
        self.assertIn('marker', lg.output[0])


if __name__ == '__main__':
    unittest.main()
