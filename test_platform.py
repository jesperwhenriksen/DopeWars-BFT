"""Platform integration: data isolation, authenticated storage and distribution."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from platform_paths import data_dir


class PlatformTests(unittest.TestCase):
    def test_data_directory_override_and_platform_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {'BFT_DATA_DIR': str(root / 'override')}, clear=True):
                self.assertEqual(data_dir(), root / 'override')
            with patch('platform_paths.sys.platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': str(root)}, clear=True):
                self.assertEqual(data_dir(), root / 'BFT-DopeWars')
            with patch('platform_paths.sys.platform', 'linux'), patch.dict(os.environ, {'XDG_DATA_HOME': str(root)}, clear=True):
                self.assertEqual(data_dir(), root / 'BFT-DopeWars')

    def test_linux_credentials_roundtrip_restart_and_tamper(self):
        from lan import protect_linux
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, BFT_DATA_DIR=directory):
                first = protect_linux(b'connection')
                key = (Path(directory) / 'linux-protect.key').read_bytes()
                second = protect_linux(b'connection')
                self.assertNotEqual(first, second)
                self.assertEqual(protect_linux(first, True), b'connection')
                self.assertEqual(protect_linux(second, True), b'connection')
                self.assertEqual((Path(directory) / 'linux-protect.key').read_bytes(), key)
                for bad in (b'', first[:12], first[:-1] + bytes([first[-1] ^ 1])):
                    with self.assertRaises(OSError):
                        protect_linux(bad, True)

    def test_linux_files_present_in_distributed_source(self):
        root = Path(sys.executable).parent / 'source' if getattr(sys, 'frozen', False) else Path(__file__).parent
        for name in ('platform_paths.py', 'run-linux.sh', 'requirements-linux.txt', 'test_platform.py'):
            self.assertTrue((root / name).is_file(), name)
        script = (root / 'run-linux.sh').read_bytes()
        self.assertNotIn(b'\r\n', script, 'Linux launcher must retain LF line endings')
