import unittest

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


if __name__ == '__main__':
    unittest.main()
