#!/usr/bin/env python3
"""Direct tests for configurator.sambaclient."""

import ipaddress
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from configurator import sambaclient


class TestNetworkDiscoveryHelpers(unittest.TestCase):
    """Tests for netifaces-based network helper functions."""

    def test_get_broadcast_addresses_without_netifaces(self):
        """Missing netifaces should degrade gracefully."""
        with patch.object(sambaclient, "netifaces", None):
            self.assertEqual(sambaclient.get_broadcast_addresses(), [])

    def test_get_broadcast_addresses_skips_broken_interface(self):
        """A failing interface should not abort discovery."""
        fake_netifaces = MagicMock()
        fake_netifaces.AF_INET = 2
        fake_netifaces.interfaces.return_value = ["eth0", "wlan0"]

        def fake_ifaddresses(interface):
            if interface == "eth0":
                raise OSError("device error")
            return {2: [{"addr": "192.168.1.10", "broadcast": "192.168.1.255"}]}

        fake_netifaces.ifaddresses.side_effect = fake_ifaddresses

        with patch.object(sambaclient, "netifaces", fake_netifaces):
            self.assertEqual(sambaclient.get_broadcast_addresses(), ["192.168.1.255"])

    def test_get_local_networks_skips_broken_interface(self):
        """Broken interface queries should be skipped while preserving valid networks."""
        fake_netifaces = MagicMock()
        fake_netifaces.AF_INET = 2
        fake_netifaces.interfaces.return_value = ["eth0", "wlan0"]

        def fake_ifaddresses(interface):
            if interface == "eth0":
                raise ValueError("bad interface")
            return {2: [{"addr": "10.0.0.20", "netmask": "255.255.255.0"}]}

        fake_netifaces.ifaddresses.side_effect = fake_ifaddresses

        with patch.object(sambaclient, "netifaces", fake_netifaces):
            networks = sambaclient.get_local_networks()

        self.assertEqual(len(networks), 1)
        network, interface = networks[0]
        self.assertEqual(interface, "wlan0")
        self.assertEqual(network, ipaddress.IPv4Network("10.0.0.0/24"))


class TestAuthBehavior(unittest.TestCase):
    """Tests for SMB authentication command behavior."""

    @patch("configurator.sambaclient.shutil.which", return_value="/usr/bin/smbclient")
    @patch("configurator.sambaclient.subprocess.run")
    def test_check_connection_username_without_password_is_non_interactive(self, mock_run, _mock_which):
        """Username-only auth must disable password prompts via -N."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        ok, error = sambaclient.check_smb_connection("server", username="alice", password=None)

        self.assertTrue(ok)
        self.assertIsNone(error)
        cmd = mock_run.call_args.args[0]
        self.assertIn("-U", cmd)
        self.assertIn("alice", cmd)
        self.assertIn("-N", cmd)

    @patch("configurator.sambaclient.shutil.which", return_value="/usr/bin/smbclient")
    @patch("configurator.sambaclient.os.path.isfile", return_value=False)
    def test_check_connection_missing_credentials_file_returns_error(self, _mock_isfile, _mock_which):
        """Missing credentials file should return a clear error."""
        ok, error = sambaclient.check_smb_connection("server", credentials_file="/no/such/file")
        self.assertFalse(ok)
        self.assertIn("Credentials file not found", error or "")


class TestShareAndVersionFlow(unittest.TestCase):
    """Tests for list_smb_shares and detect_smb_version behavior."""

    @patch("configurator.sambaclient.shutil.which", return_value="/usr/bin/smbclient")
    @patch("configurator.sambaclient.subprocess.run")
    def test_list_shares_username_without_password_uses_non_interactive_auth(self, mock_run, _mock_which):
        """list_smb_shares should pass -N when username is provided without password."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Sharename       Type      Comment\n"
                "---------       ----      -------\n"
                "  public        Disk      Public Share\n"
            ),
            stderr="",
        )

        shares, detected = sambaclient.list_smb_shares("server", username="alice")

        self.assertEqual(detected, "SMB3")
        self.assertEqual(len(shares), 1)
        self.assertEqual(shares[0]["name"], "public")
        cmd = mock_run.call_args.args[0]
        self.assertIn("-U", cmd)
        self.assertIn("alice", cmd)
        self.assertIn("-N", cmd)

    @patch("configurator.sambaclient.shutil.which", return_value="/usr/bin/smbclient")
    @patch("configurator.sambaclient.subprocess.run")
    def test_detect_version_username_without_password_uses_non_interactive_auth(self, mock_run, _mock_which):
        """detect_smb_version should remain non-interactive for username-only auth."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        version = sambaclient.detect_smb_version("server", username="alice")

        self.assertEqual(version, "SMB3")
        cmd = mock_run.call_args.args[0]
        self.assertIn("-U", cmd)
        self.assertIn("alice", cmd)
        self.assertIn("-N", cmd)

    @patch("configurator.sambaclient.shutil.which", return_value="/usr/bin/smbclient")
    @patch("configurator.sambaclient.subprocess.run")
    def test_list_shares_missing_credentials_file_returns_unknown(self, mock_run, _mock_which):
        """Missing credentials file should skip attempts and return default values."""
        with patch("configurator.sambaclient.os.path.isfile", return_value=False):
            shares, detected = sambaclient.list_smb_shares("server", credentials_file="/missing")

        self.assertEqual(shares, [])
        self.assertEqual(detected, "Unknown")
        mock_run.assert_not_called()


class TestHostInfoShape(unittest.TestCase):
    """Tests for host info parsing output shape."""

    @patch("configurator.sambaclient.subprocess.run")
    def test_get_host_info_services_is_list(self, mock_run):
        """Host info should expose services as a list for downstream consumers."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "HOSTNAME        <00> -         UNIQUE\n"
                "WORKGROUP       <00> -         GROUP\n"
                "HOSTNAME        <20> -         ACTIVE\n"
            ),
            stderr="",
        )

        info = sambaclient.get_host_info("192.168.1.10")

        self.assertEqual(info["hostname"], "HOSTNAME")
        self.assertEqual(info["workgroup"], "WORKGROUP")
        self.assertEqual(info["services"], ["File Server"])


class TestMainValidation(unittest.TestCase):
    """CLI input validation behavior."""

    @patch("sys.argv", ["config-sambaclient", "--check-connect", "server", "--password", "secret"])
    def test_main_rejects_password_without_username(self):
        """CLI should fail fast when password is provided without username."""
        with self.assertRaises(SystemExit) as cm:
            sambaclient.main()
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
