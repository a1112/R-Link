"""Desktop updates must never put mutable data in their version directory."""
import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class ReleasePathsTests(unittest.TestCase):
    def test_desktop_root_moves_mutable_paths_but_keeps_builtin_resources(self):
        from core import paths
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"R_LINK_USER_ROOT": directory}):
                paths = importlib.reload(paths)
                self.assertEqual(paths.CONFIG_DIR, Path(directory) / "config")
                self.assertEqual(paths.PLUGINS_DIR, Path(directory) / "plugins")
                self.assertEqual(paths.LOGS_DIR, Path(directory) / "logs")
                self.assertEqual(paths.BUILTIN_DIR, paths.SERVER_DIR / "builtin")
        importlib.reload(paths)


if __name__ == "__main__":
    unittest.main()
