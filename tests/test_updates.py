import unittest

from astralix._updates import Updates


class UpdatesTest(unittest.TestCase):
    def test_disk_update_does_not_mask_stale_running_release(self):
        report = {
            "current": "old",
            "checkout": "new",
            "target": "new",
            "branch": "dev",
            "running_branch": "dev",
        }
        self.assertFalse(Updates.is_current(report, "dev"))
        report["current"] = "new"
        self.assertTrue(Updates.is_current(report, "dev"))


if __name__ == "__main__":
    unittest.main()
