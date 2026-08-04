#!/usr/bin/env python3
"""Regression tests for wifi module."""

from argparse import Namespace
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
import logging
import subprocess

import unittest

from configurator import wifi


def _cp(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    """Create a minimal subprocess result object for tests."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class TestNmcliParsingRegression(unittest.TestCase):
    """Regression tests for robust nmcli parsing."""

    def test_split_nmcli_terse_line_with_escaped_colons(self):
        fields = wifi._split_nmcli_terse_line(
            "My\\:SSID:70:WPA2:11:AA\\:BB\\:CC\\:DD\\:EE\\:FF:▂▄▆_"
        )
        self.assertEqual(fields[0], "My:SSID")
        self.assertEqual(fields[1], "70")
        self.assertEqual(fields[4], "AA:BB:CC:DD:EE:FF")

    @patch("configurator.wifi.time.sleep", return_value=None)
    @patch("configurator.wifi.subprocess.run")
    def test_scan_with_networkmanager_parses_escaped_fields(self, mock_run, _mock_sleep):
        mock_run.side_effect = [
            _cp(0, "", ""),
            _cp(
                0,
                "My\\:SSID:70:WPA2:11:AA\\:BB\\:CC\\:DD\\:EE\\:FF:▂▄▆_\n",
                "",
            ),
        ]

        networks = wifi.scan_with_networkmanager("wlan0", timeout=1)

        self.assertEqual(len(networks), 1)
        self.assertEqual(networks[0]["ssid"], "My:SSID")
        self.assertEqual(networks[0]["bssid"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(networks[0]["signal"], 70)


class TestWifiMainRegression(unittest.TestCase):
    """Regression tests for main() exit codes and quiet mode output."""

    @patch("configurator.wifi.scan_wifi_networks")
    @patch("configurator.wifi.parse_arguments")
    def test_main_list_networks_quiet_suppresses_stdout(self, mock_parse, mock_scan):
        mock_parse.return_value = Namespace(
            list_networks=True,
            connect=None,
            show_current=False,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=True,
        )
        mock_scan.return_value = [{"ssid": "A", "signal": 50, "security": "Open"}]

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            code = wifi.main()

        self.assertEqual(code, 0)
        self.assertEqual(fake_stdout.getvalue(), "")

    @patch("configurator.wifi.scan_wifi_networks", return_value=[])
    @patch("configurator.wifi.parse_arguments")
    def test_main_list_networks_empty_returns_failure(self, mock_parse, _mock_scan):
        mock_parse.return_value = Namespace(
            list_networks=True,
            connect=None,
            show_current=False,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=False,
        )

        code = wifi.main()

        self.assertEqual(code, 1)

    @patch("configurator.wifi.get_current_connection")
    @patch("configurator.wifi.parse_arguments")
    def test_main_show_current_quiet_suppresses_stdout(self, mock_parse, mock_current):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect=None,
            show_current=True,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=True,
        )
        mock_current.return_value = {
            "ssid": "MyNet",
            "device": "wlan0",
            "ip": "192.168.1.2",
            "security": "wpa-psk",
        }

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            code = wifi.main()

        self.assertEqual(code, 0)
        self.assertEqual(fake_stdout.getvalue(), "")

    @patch("configurator.wifi.connect_to_wifi", return_value=True)
    @patch("configurator.wifi.parse_arguments")
    def test_main_connect_success_returns_zero(self, mock_parse, _mock_connect):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect="MyNet",
            show_current=False,
            timeout=10,
            passphrase="secret",
            revert_when_fail=True,
            long=False,
            verbose=False,
            quiet=False,
        )

        code = wifi.main()

        self.assertEqual(code, 0)

    @patch("configurator.wifi.connect_to_wifi", return_value=False)
    @patch("configurator.wifi.parse_arguments")
    def test_main_connect_failure_returns_one(self, mock_parse, _mock_connect):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect="MyNet",
            show_current=False,
            timeout=10,
            passphrase="secret",
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=False,
        )

        code = wifi.main()

        self.assertEqual(code, 1)


class TestWifiConnectionRegression(unittest.TestCase):
    """Regression tests for WiFi connection helpers."""

    @patch("configurator.wifi.subprocess.run")
    def test_scan_with_iw_maps_2484_to_channel_14(self, mock_run):
        mock_run.return_value = _cp(
            0,
            "\n".join(
                [
                    "BSS 00:11:22:33:44:55(on wlan0)",
                    "\tfreq: 2484",
                    "\tsignal: -45.00 dBm",
                    "\tSSID: ch14-net",
                ]
            ),
            "",
        )

        networks = wifi.scan_with_iw("wlan0", timeout=1)

        self.assertEqual(len(networks), 1)
        self.assertEqual(networks[0]["channel"], "14")

    @patch("configurator.wifi.subprocess.run")
    def test_save_current_connection_accepts_80211_wireless_type(self, mock_run):
        mock_run.side_effect = [
            _cp(0, "ProfileX:wlan0:802-11-wireless\n", ""),
            _cp(0, "802-11-wireless.ssid:HomeNet\n", ""),
        ]

        connection = wifi.save_current_connection()

        self.assertIsNotNone(connection)
        self.assertEqual(connection["name"], "ProfileX")
        self.assertEqual(connection["ssid"], "HomeNet")

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run")
    def test_connect_uses_existing_profile_with_escaped_colon_name(self, mock_run, _mock_interfaces):
        ssid = "Cafe:Net"
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "Cafe\\:Net\n", ""),
            _cp(0, "", ""),
            _cp(0, "Cafe\\:Net:wifi\n", ""),
            _cp(0, "802-11-wireless.ssid:Cafe:Net\n", ""),
        ]

        result = wifi.connect_to_wifi(ssid)

        self.assertTrue(result)
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(["nmcli", "connection", "up", "Cafe:Net"], commands)

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run")
    def test_connect_fails_when_device_connected_to_different_network(self, mock_run, _mock_interfaces):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "Target\n", ""),
            _cp(0, "", ""),
            _cp(0, "OtherConn:wifi\n", ""),
            _cp(0, "802-11-wireless.ssid:OtherSSID\n", ""),
            _cp(0, "GENERAL.CONNECTION:OtherConn\n", ""),
            _cp(0, "802-11-wireless.ssid:OtherSSID\n", ""),
        ]

        result = wifi.connect_to_wifi("Target")

        self.assertFalse(result)


class TestWifiAdditionalCoverage(unittest.TestCase):
    """Additional branch-focused tests for wifi module."""

    @patch("configurator.wifi.logging.StreamHandler")
    @patch("configurator.wifi.logging.getLogger")
    @patch("configurator.wifi.logging.Formatter")
    def test_setup_logging_quiet_uses_warning_and_plain_format(self, mock_formatter, mock_get_logger, mock_handler):
        root = unittest.mock.MagicMock()
        root.handlers = [unittest.mock.MagicMock()]
        mock_get_logger.return_value = root

        wifi.setup_logging(verbose=False, quiet=True)

        root.setLevel.assert_called_once_with(logging.WARNING)
        mock_handler.return_value.setLevel.assert_called_once_with(logging.WARNING)
        mock_formatter.assert_called_once_with('%(message)s')

    @patch("configurator.wifi.logging.StreamHandler")
    @patch("configurator.wifi.logging.getLogger")
    @patch("configurator.wifi.logging.Formatter")
    def test_setup_logging_verbose_uses_debug_format(self, mock_formatter, mock_get_logger, mock_handler):
        root = unittest.mock.MagicMock()
        root.handlers = []
        mock_get_logger.return_value = root

        wifi.setup_logging(verbose=True, quiet=False)

        root.setLevel.assert_called_once_with(logging.DEBUG)
        mock_handler.return_value.setLevel.assert_called_once_with(logging.DEBUG)
        mock_formatter.assert_called_once_with('%(levelname)s: %(message)s')

    @patch("sys.argv", ["config-wifi", "--list-networks", "--timeout", "15", "--long", "--quiet"])
    def test_parse_arguments_list_networks(self):
        args = wifi.parse_arguments()
        self.assertTrue(args.list_networks)
        self.assertEqual(args.timeout, 15)
        self.assertTrue(args.long)
        self.assertTrue(args.quiet)

    @patch("sys.argv", ["config-wifi", "--connect", "Home", "--passphrase", "pw", "--revert-when-fail", "--verbose"])
    def test_parse_arguments_connect(self):
        args = wifi.parse_arguments()
        self.assertEqual(args.connect, "Home")
        self.assertEqual(args.passphrase, "pw")
        self.assertTrue(args.revert_when_fail)
        self.assertTrue(args.verbose)

    @patch("configurator.wifi.subprocess.run", return_value=_cp(0, "802-11-wireless.ssid:CafeNet\n", ""))
    def test_get_connection_ssid_success(self, _mock_run):
        self.assertEqual(wifi._get_connection_ssid("profile"), "CafeNet")

    @patch("configurator.wifi.subprocess.run", return_value=_cp(1, "", "err"))
    def test_get_connection_ssid_nonzero_returns_none(self, _mock_run):
        self.assertIsNone(wifi._get_connection_ssid("profile"))

    @patch("configurator.wifi.subprocess.run", side_effect=FileNotFoundError())
    def test_get_connection_ssid_handles_missing_nmcli(self, _mock_run):
        self.assertIsNone(wifi._get_connection_ssid("profile"))

    @patch("configurator.wifi.subprocess.run")
    def test_find_wireless_interfaces_from_iw(self, mock_run):
        mock_run.return_value = _cp(0, "phy#0\n\tInterface wlan0\n", "")
        self.assertEqual(wifi.find_wireless_interfaces(), ["wlan0"])

    @patch("configurator.wifi.subprocess.run")
    def test_find_wireless_interfaces_fallback_nmcli(self, mock_run):
        mock_run.side_effect = [
            _cp(1, "", ""),
            _cp(0, "eth0:ethernet\nwlan0:wifi\n", ""),
        ]
        self.assertEqual(wifi.find_wireless_interfaces(), ["wlan0"])

    @patch("configurator.wifi.os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="Inter-| sta\n face |\n wlan1: 0000. 0. 0.\n")
    @patch("configurator.wifi.subprocess.run", side_effect=[_cp(1, "", ""), _cp(1, "", "")])
    def test_find_wireless_interfaces_fallback_proc_net(self, _mock_run, _mock_open, _mock_exists):
        self.assertEqual(wifi.find_wireless_interfaces(), ["wlan1"])

    @patch("configurator.wifi.find_wireless_interfaces", return_value=[])
    def test_scan_wifi_networks_no_interfaces(self, _mock_find):
        self.assertEqual(wifi.scan_wifi_networks(timeout=1), [])

    @patch("configurator.wifi.scan_with_networkmanager")
    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run", return_value=_cp(0, "active\n", ""))
    def test_scan_wifi_networks_uses_networkmanager_and_sorts(self, _mock_run, _mock_find, mock_scan_nm):
        mock_scan_nm.return_value = [
            {"ssid": "weak", "signal": 10},
            {"ssid": "strong", "signal": 90},
        ]
        result = wifi.scan_wifi_networks(timeout=1)
        self.assertEqual([n["ssid"] for n in result], ["strong", "weak"])

    @patch("configurator.wifi.scan_with_iw")
    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run", return_value=_cp(1, "", ""))
    def test_scan_wifi_networks_uses_iw_when_nm_inactive(self, _mock_run, _mock_find, mock_scan_iw):
        mock_scan_iw.return_value = [{"ssid": "x", "signal": 50}]
        result = wifi.scan_wifi_networks(timeout=1)
        self.assertEqual(result[0]["ssid"], "x")

    @patch("configurator.wifi.time.sleep", return_value=None)
    @patch("configurator.wifi.subprocess.run")
    def test_scan_with_networkmanager_skips_empty_ssid_and_defaults(self, mock_run, _mock_sleep):
        mock_run.side_effect = [
            _cp(0, "", ""),
            _cp(0, ":notnum::11:AA:bars\nNet:42::6:BB:bars\n", ""),
        ]
        result = wifi.scan_with_networkmanager("wlan0", timeout=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ssid"], "Net")
        self.assertEqual(result[0]["security"], "Open")

    @patch("configurator.wifi.subprocess.run", side_effect=subprocess.SubprocessError("iw failed"))
    def test_scan_with_iw_subprocess_error_returns_empty(self, _mock_run):
        self.assertEqual(wifi.scan_with_iw("wlan0", timeout=1), [])

    @patch("configurator.wifi.subprocess.run")
    def test_scan_with_iw_parsing_variants(self, mock_run):
        mock_run.return_value = _cp(
            0,
            "\n".join([
                "BSS 00:11:22:33:44:55(on wlan0)",
                "\tfreq: 2412",
                "\tsignal: -50.00 dBm",
                "\tSSID: Home",
                "\tcapability: Privacy",
                "\tRSN: something",
            ]),
            "",
        )
        result = wifi.scan_with_iw("wlan0", timeout=1)
        self.assertEqual(result[0]["channel"], "1")
        self.assertEqual(result[0]["security"], "WPA")

    @patch("configurator.wifi.subprocess.run")
    def test_get_current_connection_primary_success(self, mock_run):
        mock_run.side_effect = [
            _cp(0, "Conn:wlan0:wifi:yes\n", ""),
            _cp(0, "802-11-wireless.ssid:MyNet\n802-11-wireless-security.key-mgmt:wpa-psk\n", ""),
            _cp(0, "IP4.ADDRESS[1]:192.168.1.9/24\n", ""),
        ]
        result = wifi.get_current_connection()
        self.assertIsNotNone(result)
        self.assertEqual(result["ssid"], "MyNet")
        self.assertEqual(result["security"], "wpa-psk")
        self.assertEqual(result["ip"], "192.168.1.9")

    @patch("configurator.wifi.subprocess.run")
    def test_get_current_connection_uses_iwconfig_fallback(self, mock_run):
        mock_run.side_effect = [
            _cp(0, "Conn:wlan0:wifi:yes\n", ""),
            _cp(0, "802-11-wireless-security.key-mgmt:wpa-psk\n", ""),
            _cp(1, "", ""),
            _cp(0, "wlan0     IEEE 802.11  ESSID:\"Cafe\"\n", ""),
        ]
        result = wifi.get_current_connection()
        self.assertIsNotNone(result)
        self.assertEqual(result["ssid"], "Cafe")

    @patch("configurator.wifi.subprocess.run", side_effect=FileNotFoundError())
    def test_get_current_connection_handles_missing_nmcli(self, _mock_run):
        self.assertIsNone(wifi.get_current_connection())

    @patch("configurator.wifi.subprocess.run", return_value=_cp(1, "inactive\n", ""))
    def test_connect_to_wifi_fails_when_nm_inactive(self, _mock_run):
        self.assertFalse(wifi.connect_to_wifi("Target"))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=[])
    @patch("configurator.wifi.subprocess.run", return_value=_cp(0, "active\n", ""))
    def test_connect_to_wifi_fails_with_no_interfaces(self, _mock_run, _mock_interfaces):
        self.assertFalse(wifi.connect_to_wifi("Target"))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run")
    def test_connect_to_wifi_open_network_success(self, mock_run, _mock_interfaces):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "", ""),
            _cp(0, "", ""),
            _cp(0, "Target:wifi\n", ""),
            _cp(0, "802-11-wireless.ssid:Target\n", ""),
        ]
        self.assertTrue(wifi.connect_to_wifi("Target"))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi._get_connection_ssid", return_value="Target")
    @patch("configurator.wifi.subprocess.run")
    def test_connect_to_wifi_device_fallback_success(self, mock_run, _mock_get_ssid, _mock_interfaces):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "", ""),
            _cp(0, "", ""),
            _cp(0, "Conn:wifi\n", ""),
            _cp(0, "802-11-wireless.ssid:Other\n", ""),
            _cp(0, "GENERAL.CONNECTION:Conn\n", ""),
        ]
        self.assertTrue(wifi.connect_to_wifi("Target"))

    @patch("configurator.wifi.subprocess.run")
    def test_handle_connection_failure_revert_paths(self, mock_run):
        mock_run.return_value = _cp(0, "", "")
        self.assertFalse(wifi._handle_connection_failure({"name": "Old"}, True))
        self.assertFalse(wifi._handle_connection_failure(None, True))

    @patch("configurator.wifi.subprocess.run", side_effect=FileNotFoundError())
    def test_handle_connection_failure_revert_exception(self, _mock_run):
        self.assertFalse(wifi._handle_connection_failure({"name": "Old"}, True))

    @patch("configurator.wifi.get_current_connection", return_value=None)
    @patch("configurator.wifi.parse_arguments")
    def test_main_show_current_not_connected_returns_one(self, mock_parse, _mock_current):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect=None,
            show_current=True,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=False,
        )
        self.assertEqual(wifi.main(), 1)

    @patch("configurator.wifi.get_current_connection")
    @patch("configurator.wifi.parse_arguments")
    def test_main_show_current_long_prints_detailed(self, mock_parse, mock_current):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect=None,
            show_current=True,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=True,
            verbose=False,
            quiet=False,
        )
        mock_current.return_value = {
            "ssid": "MyNet",
            "device": "wlan0",
            "ip": "192.168.1.2",
            "security": "wpa-psk",
        }

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            code = wifi.main()

        self.assertEqual(code, 0)
        self.assertIn("MyNet|wlan0|192.168.1.2|wpa-psk", fake_stdout.getvalue())

    @patch("configurator.wifi.parse_arguments")
    def test_main_default_fallback_returns_one(self, mock_parse):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect=None,
            show_current=False,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=False,
        )
        self.assertEqual(wifi.main(), 1)


class TestWifiSecondPassCoverage(unittest.TestCase):
    """Second-pass tests to close remaining branch gaps."""

    @patch("configurator.wifi.subprocess.run")
    def test_scan_with_networkmanager_timeout_no_results(self, mock_run):
        mock_run.side_effect = [
            _cp(0, "", ""),
            _cp(1, "", ""),
        ]
        with patch("configurator.wifi.time.time", side_effect=[0, 0.5, 2]), \
            patch("configurator.wifi.time.sleep", return_value=None):
            result = wifi.scan_with_networkmanager("wlan0", timeout=1)
        self.assertEqual(result, [])

    @patch("configurator.wifi.subprocess.run", side_effect=subprocess.SubprocessError("nm fail"))
    def test_scan_with_networkmanager_subprocess_error(self, _mock_run):
        self.assertEqual(wifi.scan_with_networkmanager("wlan0", timeout=1), [])

    @patch("configurator.wifi.subprocess.run")
    def test_scan_with_iw_handles_invalid_signal_and_frequency(self, mock_run):
        mock_run.return_value = _cp(
            0,
            "\n".join([
                "BSS 00:11:22:33:44:55(on wlan0)",
                "\tfreq: invalid",
                "\tsignal: bad dBm",
                "\tSSID: edge",
                "\tcapability: ESS",
            ]),
            "",
        )
        result = wifi.scan_with_iw("wlan0", timeout=1)
        self.assertEqual(result[0]["signal"], 0)
        self.assertEqual(result[0]["channel"], "")
        self.assertEqual(result[0]["security"], "Open")

    @patch("configurator.wifi.subprocess.run")
    def test_scan_with_iw_channel_for_5ghz(self, mock_run):
        mock_run.return_value = _cp(
            0,
            "\n".join([
                "BSS 66:77:88:99:AA:BB(on wlan0)",
                "\tfreq: 5180",
                "\tsignal: -40.00 dBm",
                "\tSSID: fiveg",
            ]),
            "",
        )
        result = wifi.scan_with_iw("wlan0", timeout=1)
        self.assertEqual(result[0]["channel"], "36")

    @patch("configurator.wifi.subprocess.run")
    def test_save_current_connection_returns_none_when_no_active_wifi(self, mock_run):
        mock_run.return_value = _cp(0, "Wired:eth0:ethernet\n", "")
        self.assertIsNone(wifi.save_current_connection())

    @patch("configurator.wifi.subprocess.run")
    def test_save_current_connection_details_nonzero(self, mock_run):
        mock_run.side_effect = [
            _cp(0, "ProfileX:wlan0:wifi\n", ""),
            _cp(1, "", ""),
        ]
        self.assertIsNone(wifi.save_current_connection())

    @patch("configurator.wifi.subprocess.run")
    def test_connect_to_wifi_existing_profile_up_fails_with_revert(self, mock_run):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "Old:wlan0:wifi\n", ""),
            _cp(0, "802-11-wireless.ssid:OldNet\n", ""),
            _cp(0, "Target\n", ""),
            _cp(1, "", "failed"),
            _cp(0, "", ""),
        ]
        with patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"]):
            self.assertFalse(wifi.connect_to_wifi("Target", revert_on_failure=True))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run", side_effect=[_cp(0, "active\n", ""), subprocess.SubprocessError("scan fail")])
    def test_scan_wifi_networks_handles_nm_status_exception_and_uses_iw(self, mock_run, _mock_if):
        with patch("configurator.wifi.scan_with_iw", return_value=[{"ssid": "x", "signal": 1}]):
            result = wifi.scan_wifi_networks(timeout=1)
        self.assertEqual(result, [])

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run")
    def test_connect_to_wifi_passphrase_success(self, mock_run, _mock_if):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "", ""),
            _cp(0, "", ""),
            _cp(0, "Target:wifi\n", ""),
            _cp(0, "802-11-wireless.ssid:Target\n", ""),
        ]
        self.assertTrue(wifi.connect_to_wifi("Target", passphrase="secret"))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run")
    def test_connect_to_wifi_passphrase_connection_command_fails(self, mock_run, _mock_if):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "", ""),
            _cp(1, "", "wrong password"),
        ]
        self.assertFalse(wifi.connect_to_wifi("Target", passphrase="secret"))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run")
    def test_connect_to_wifi_verify_active_connections_command_fails(self, mock_run, _mock_if):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "", ""),
            _cp(0, "", ""),
            _cp(1, "", "verify failed"),
        ]
        self.assertFalse(wifi.connect_to_wifi("Target"))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run")
    def test_connect_to_wifi_no_active_wifi_after_verify(self, mock_run, _mock_if):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "", ""),
            _cp(0, "", ""),
            _cp(0, "Wired:ethernet\n", ""),
        ]
        self.assertFalse(wifi.connect_to_wifi("Target"))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run")
    def test_connect_to_wifi_active_wifi_but_missing_ssid_lines(self, mock_run, _mock_if):
        mock_run.side_effect = [
            _cp(0, "active\n", ""),
            _cp(0, "", ""),
            _cp(0, "", ""),
            _cp(0, "Conn:wifi\n", ""),
            _cp(0, "connection.id:Conn\n", ""),
            _cp(0, "GENERAL.CONNECTION:\n", ""),
        ]
        self.assertFalse(wifi.connect_to_wifi("Target"))

    @patch("configurator.wifi.find_wireless_interfaces", return_value=["wlan0"])
    @patch("configurator.wifi.subprocess.run", side_effect=subprocess.SubprocessError("connect exception"))
    def test_connect_to_wifi_subprocess_exception_path(self, _mock_run, _mock_if):
        self.assertFalse(wifi.connect_to_wifi("Target"))

    @patch("configurator.wifi.subprocess.run", return_value=_cp(1, "", "revert failed"))
    def test_handle_connection_failure_revert_nonzero(self, _mock_run):
        self.assertFalse(wifi._handle_connection_failure({"name": "Old"}, True))

    @patch("configurator.wifi.scan_wifi_networks")
    @patch("configurator.wifi.parse_arguments")
    def test_main_list_networks_short_print(self, mock_parse, mock_scan):
        mock_parse.return_value = Namespace(
            list_networks=True,
            connect=None,
            show_current=False,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=False,
        )
        mock_scan.return_value = [{"ssid": "A", "signal": 50, "security": "Open"}]
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            code = wifi.main()
        self.assertEqual(code, 0)
        self.assertIn("A|50|Open", fake_stdout.getvalue())

    @patch("configurator.wifi.scan_wifi_networks")
    @patch("configurator.wifi.parse_arguments")
    def test_main_list_networks_long_print(self, mock_parse, mock_scan):
        mock_parse.return_value = Namespace(
            list_networks=True,
            connect=None,
            show_current=False,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=True,
            verbose=False,
            quiet=False,
        )
        mock_scan.return_value = [{"ssid": "A", "signal": 50, "security": "Open", "channel": "1", "bssid": "AA"}]
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            code = wifi.main()
        self.assertEqual(code, 0)
        self.assertIn("A|50|Open|1|AA", fake_stdout.getvalue())

    @patch("configurator.wifi.get_current_connection")
    @patch("configurator.wifi.parse_arguments")
    def test_main_show_current_short_print(self, mock_parse, mock_current):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect=None,
            show_current=True,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=False,
        )
        mock_current.return_value = {
            "ssid": "MyNet",
            "device": "wlan0",
            "ip": "192.168.1.2",
            "security": "wpa-psk",
        }
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            code = wifi.main()
        self.assertEqual(code, 0)
        self.assertIn("MyNet|192.168.1.2", fake_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
