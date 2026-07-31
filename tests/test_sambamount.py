#!/usr/bin/env python3
"""Direct tests for configurator.sambamount."""

import unittest
from unittest.mock import MagicMock, patch

from configurator import sambamount


class FakeConfigDB:
    """Minimal in-memory ConfigDB test double."""

    def __init__(self, initial=None):
        self.data = dict(initial or {})
        self.deleted = []
        self.set_calls = []

    def get(self, key, default=None, secure=False):
        return self.data.get(key, default)

    def set(self, key, value, secure=False):
        self.data[key] = value
        self.set_calls.append((key, value, secure))

    def delete(self, key):
        self.deleted.append(key)
        self.data.pop(key, None)


class DummyTempCredentialsFile:
    """Context manager used to emulate NamedTemporaryFile."""

    def __init__(self, name="/tmp/sambamount-test-cred"):
        self.name = name
        self.contents = ""

    def write(self, data):
        self.contents += data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestConfigIndexHandling(unittest.TestCase):
    """Tests for sparse index handling in configdb traversal."""

    @patch("configurator.sambamount.ConfigDB")
    def test_read_mount_config_handles_sparse_indices(self, mock_db_cls):
        db = FakeConfigDB(
            {
                "smbmount.1.server": "srv1",
                "smbmount.1.share": "music",
                "smbmount.1.mountpoint": "/mnt/music",
                "smbmount.1.user": "u1",
                "smbmount.1.password": "p1",
                "smbmount.1.version": "SMB3",
                "smbmount.1.options": "",
                "smbmount.3.server": "srv3",
                "smbmount.3.share": "backup",
                "smbmount.3.mountpoint": "/mnt/backup",
                "smbmount.3.user": "u3",
                "smbmount.3.password": "p3",
                "smbmount.3.version": "SMB2",
                "smbmount.3.options": "ro",
            }
        )
        mock_db_cls.return_value = db

        mounts = sambamount.read_mount_config(secure=True)

        self.assertEqual(len(mounts), 2)
        self.assertEqual(mounts[0]["id"], 1)
        self.assertEqual(mounts[1]["id"], 3)
        self.assertEqual(mounts[1]["server"], "srv3")

    @patch("configurator.sambamount.ConfigDB")
    def test_write_mount_config_clears_sparse_existing_entries(self, mock_db_cls):
        db = FakeConfigDB(
            {
                "smbmount.1.server": "old1",
                "smbmount.1.share": "a",
                "smbmount.3.server": "old3",
                "smbmount.3.share": "c",
            }
        )
        mock_db_cls.return_value = db

        success = sambamount.write_mount_config(
            [
                {
                    "server": "new",
                    "share": "media",
                    "mountpoint": "/mnt/media",
                    "user": "",
                    "password": "",
                    "version": "",
                    "options": "",
                }
            ]
        )

        self.assertTrue(success)
        self.assertIn("smbmount.1.server", db.deleted)
        self.assertIn("smbmount.3.server", db.deleted)
        self.assertEqual(db.data.get("smbmount.1.server"), "new")


class TestMountCredentialsHandling(unittest.TestCase):
    """Tests for secure credentials handling in mount command invocation."""

    @patch("configurator.sambamount._safe_unlink")
    @patch("configurator.sambamount.subprocess.run")
    @patch("configurator.sambamount.NamedTemporaryFile")
    @patch("configurator.sambamount.is_mounted", return_value=False)
    @patch("configurator.sambamount.os.path.exists", return_value=True)
    @patch("configurator.sambamount.shutil.which", return_value="/usr/bin/mount")
    def test_mount_cifs_share_uses_credentials_file_not_password_arg(
        self,
        _mock_which,
        _mock_exists,
        _mock_is_mounted,
        mock_tempfile,
        mock_run,
        mock_safe_unlink,
    ):
        temp_file = DummyTempCredentialsFile()
        mock_tempfile.return_value = temp_file
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        success, error = sambamount.mount_cifs_share(
            "server",
            "share",
            "/mnt/share",
            username="alice",
            password="secret",
            version="SMB3",
            options="rw,nosuid",
        )

        self.assertTrue(success)
        self.assertIsNone(error)

        cmd = mock_run.call_args.args[0]
        self.assertIn("-o", cmd)
        mount_opts = cmd[cmd.index("-o") + 1]
        self.assertIn("credentials=/tmp/sambamount-test-cred", mount_opts)
        self.assertNotIn("password=secret", mount_opts)
        self.assertNotIn("username=alice", mount_opts)

        mock_safe_unlink.assert_called_once_with("/tmp/sambamount-test-cred")


if __name__ == "__main__":
    unittest.main()
