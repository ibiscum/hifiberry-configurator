#!/usr/bin/env python3
"""Tests for configurator.pipewire utility module."""

import subprocess
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

from configurator.pipewire import (
    _run_pw_cli,
    get_volume,
    get_volume_controls,
    main,
    set_volume,
)


class TestRunPwCli(unittest.TestCase):
    """Tests for low-level pw-cli command execution."""

    @patch("configurator.pipewire.subprocess.run")
    def test_run_pw_cli_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok\n")

        result = _run_pw_cli(["list", "Node"])

        self.assertEqual(result, "ok\n")
        mock_run.assert_called_once()

    @patch("configurator.pipewire.subprocess.run", side_effect=FileNotFoundError)
    def test_run_pw_cli_not_found(self, _mock_run):
        self.assertIsNone(_run_pw_cli(["list", "Node"]))

    @patch("configurator.pipewire.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pw-cli", timeout=5.0))
    def test_run_pw_cli_timeout(self, _mock_run):
        self.assertIsNone(_run_pw_cli(["list", "Node"]))

    @patch(
        "configurator.pipewire.subprocess.run",
        side_effect=subprocess.CalledProcessError(returncode=1, cmd=["pw-cli"], stderr="boom"),
    )
    def test_run_pw_cli_called_process_error(self, _mock_run):
        self.assertIsNone(_run_pw_cli(["list", "Node"]))


class TestGetVolumeControls(unittest.TestCase):
    """Tests for parsing control names from pw-cli output."""

    @patch("configurator.pipewire._run_pw_cli")
    def test_get_volume_controls_parses_name_lines_only(self, mock_run_cli):
        mock_run_cli.return_value = "\n".join(
            [
                '    name = "alsa_output.main"',
                '    nick = "Main"',
                '    object.serial = "22"',
                '    node.name = "not-this"',
            ]
        )

        result = get_volume_controls()

        self.assertEqual(result, ["alsa_output.main"])

    @patch("configurator.pipewire._run_pw_cli", return_value=None)
    def test_get_volume_controls_no_output(self, _mock_run_cli):
        self.assertEqual(get_volume_controls(), [])


class TestGetVolume(unittest.TestCase):
    """Tests for reading a control volume."""

    @patch("configurator.pipewire._run_pw_cli")
    def test_get_volume_success(self, mock_run_cli):
        mock_run_cli.return_value = "\n".join(
            [
                "\tid = 42",
                "\tvolume = 0.75",
            ]
        )

        self.assertEqual(get_volume("alsa_output.main"), 0.75)

    @patch("configurator.pipewire._run_pw_cli")
    def test_get_volume_ignores_non_volume_lines(self, mock_run_cli):
        mock_run_cli.return_value = "\n".join(
            [
                "\tvolume.base = 1.0",
                "\tvolumeStep = 0.01",
            ]
        )

        self.assertIsNone(get_volume("alsa_output.main"))

    @patch("configurator.pipewire._run_pw_cli", return_value=None)
    def test_get_volume_no_output(self, _mock_run_cli):
        self.assertIsNone(get_volume("alsa_output.main"))


class TestSetVolume(unittest.TestCase):
    """Tests for setting a control volume."""

    @patch("configurator.pipewire.subprocess.run")
    def test_set_volume_success(self, mock_run):
        self.assertTrue(set_volume("alsa_output.main", 0.42))
        mock_run.assert_called_once()

    @patch("configurator.pipewire.subprocess.run")
    def test_set_volume_rejects_out_of_range(self, mock_run):
        self.assertFalse(set_volume("alsa_output.main", 1.5))
        self.assertFalse(set_volume("alsa_output.main", -0.1))
        mock_run.assert_not_called()

    @patch("configurator.pipewire.subprocess.run")
    def test_set_volume_rejects_non_finite(self, mock_run):
        self.assertFalse(set_volume("alsa_output.main", float("nan")))
        self.assertFalse(set_volume("alsa_output.main", float("inf")))
        mock_run.assert_not_called()

    @patch("configurator.pipewire.subprocess.run", side_effect=subprocess.CalledProcessError(returncode=1, cmd=["pw-cli"], stderr="denied"))
    def test_set_volume_subprocess_error(self, _mock_run):
        self.assertFalse(set_volume("alsa_output.main", 0.5))


class TestMain(unittest.TestCase):
    """CLI behavior tests."""

    @patch("configurator.pipewire.get_volume_controls", return_value=["a", "b"])
    @patch("sys.argv", ["config-pipewire", "list"])
    def test_main_list(self, _mock_controls):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            main()
        self.assertEqual(mock_stdout.getvalue().strip().splitlines(), ["a", "b"])

    @patch("configurator.pipewire.get_volume", return_value=0.5)
    @patch("sys.argv", ["config-pipewire", "get", "Master"])
    def test_main_get_success(self, _mock_get):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            main()
        self.assertEqual(mock_stdout.getvalue().strip(), "0.5")

    @patch("sys.argv", ["config-pipewire", "set", "Master", "1.2"])
    def test_main_set_invalid_range_exits_3(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 3)
        self.assertIn("Volume must be a float between 0.0 and 1.0", mock_stdout.getvalue())

    @patch("sys.argv", ["config-pipewire"])
    def test_main_usage_mentions_config_pipewire(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)
        output = mock_stdout.getvalue()
        self.assertIn("config-pipewire list", output)
        self.assertIn("config-pipewire get <control_name>", output)
        self.assertIn("config-pipewire set <control_name> <volume>", output)


if __name__ == "__main__":
    unittest.main()
