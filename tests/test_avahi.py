#!/usr/bin/env python3
"""
Regression tests for avahi module

Tests the Avahi configuration functionality for:
- Configuration parsing and modification
- Interface configuration detection
- File I/O operations with backup creation
- Service restart handling
- Root privilege checks
- CLI argument parsing
"""

import os
from unittest.mock import patch, MagicMock, mock_open
import sys

# Add src directory to path for imports
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from configurator.avahi import (
    ALLOW_INTERFACES_LINE,
    _check_only_result,
    _ensure_allow_interfaces,
    _filter_server_interface_rules,
    _restart_or_start_avahi,
    check_root_privileges,
    configure_avahi_interfaces,
    main,
    setup_logging,
)


class TestConfigureAvahiInterfaces:
    """Test cases for configure_avahi_interfaces function"""

    @patch('configurator.avahi.subprocess.run')
    @patch('configurator.avahi.os.path.exists')
    def test_avahi_not_installed(self, mock_exists, mock_subprocess):
        """Test behavior when Avahi is not installed"""
        mock_exists.return_value = False

        result = configure_avahi_interfaces()

        assert result is True
        mock_subprocess.assert_not_called()

    @patch('configurator.avahi.subprocess.run')
    @patch('configurator.avahi.os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="[server]\nallow-interfaces=eth0,wlan0\n")
    def test_configuration_already_correct(self, mock_file, mock_exists, mock_subprocess):
        """Test when configuration is already correct"""
        mock_exists.return_value = True

        result = configure_avahi_interfaces()

        assert result is True

    @patch('configurator.avahi.subprocess.run')
    @patch('configurator.avahi.shutil.copy2')
    @patch('configurator.avahi.os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="[server]\n# comment\n")
    def test_adds_allow_interfaces_to_server_section(self, mock_file, mock_exists,
                                                      mock_copy2, mock_subprocess):
        """Test that allow-interfaces is added to [server] section"""
        mock_exists.return_value = True
        mock_subprocess.return_value.returncode = 0

        result = configure_avahi_interfaces()

        assert result is True

    @patch('configurator.avahi.subprocess.run')
    @patch('configurator.avahi.shutil.copy2')
    @patch('configurator.avahi.os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="[server]\ndeny-interfaces=docker0\n")
    def test_removes_existing_deny_interfaces(self, mock_file, mock_exists,
                                               mock_copy2, mock_subprocess):
        """Test that existing deny-interfaces lines are removed"""
        mock_exists.return_value = True
        mock_subprocess.return_value.returncode = 0

        result = configure_avahi_interfaces()

        assert result is True

    @patch('configurator.avahi.subprocess.run')
    @patch('configurator.avahi.shutil.copy2')
    @patch('configurator.avahi.os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="[server]\n# comment\n")
    def test_service_restart_when_active(self, mock_file, mock_exists,
                                          mock_copy2, mock_subprocess):
        """Test that service is restarted when active"""
        mock_exists.return_value = True
        # First call returns 0 (service is active), second call succeeds
        mock_subprocess.return_value.returncode = 0

        result = configure_avahi_interfaces()

        assert result is True
        # Should check if service is active and then restart it
        assert mock_subprocess.call_count >= 2

    @patch('configurator.avahi.subprocess.run')
    @patch('configurator.avahi.shutil.copy2')
    @patch('configurator.avahi.os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="[server]\n# comment\n")
    def test_service_start_when_inactive(self, mock_file, mock_exists,
                                          mock_copy2, mock_subprocess):
        """Test that service is started when not active"""
        mock_exists.return_value = True

        # First call returns non-zero (service is inactive), second call succeeds
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.returncode = 1  # Service is inactive
            else:
                result.returncode = 0  # Start succeeds
            return result

        mock_subprocess.side_effect = side_effect

        result = configure_avahi_interfaces()

        assert result is True

    @patch('configurator.avahi.subprocess.run')
    @patch('configurator.avahi.shutil.copy2')
    @patch('configurator.avahi.os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="[server]\n# comment\n")
    def test_restart_failure_returns_false(self, mock_file, mock_exists,
                                            mock_copy2, mock_subprocess):
        """Test that restart failure is handled appropriately"""
        mock_exists.return_value = True

        # Service is active but restart fails
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.returncode = 0  # Service is active
            else:
                result.returncode = 1  # Restart fails
                result.stderr = "error message"
            return result

        mock_subprocess.side_effect = side_effect

        result = configure_avahi_interfaces()

        assert result is False

    @patch('configurator.avahi.subprocess.run')
    @patch('configurator.avahi.os.path.exists')
    @patch('builtins.open', side_effect=IOError("Cannot read file"))
    def test_read_error_handling(self, mock_open_error, mock_exists, mock_subprocess):
        """Test that read errors are handled gracefully"""
        mock_exists.return_value = True

        result = configure_avahi_interfaces()

        assert result is False



class TestCheckRootPrivileges:
    """Test cases for check_root_privileges function"""

    @patch('configurator.avahi.os.geteuid')
    def test_running_as_root(self, mock_geteuid):
        """Test when running as root"""
        mock_geteuid.return_value = 0

        result = check_root_privileges()

        assert result is True

    @patch('configurator.avahi.os.geteuid')
    def test_not_running_as_root(self, mock_geteuid):
        """Test when not running as root"""
        mock_geteuid.return_value = 1000

        result = check_root_privileges()

        assert result is False


class TestSetupLogging:
    """Test cases for setup_logging function"""

    @patch('configurator.avahi.logging.basicConfig')
    def test_setup_logging_normal(self, mock_logging):
        """Test logging setup with normal verbosity"""
        setup_logging(verbose=False)

        mock_logging.assert_called_once()
        call_kwargs = mock_logging.call_args[1]
        assert call_kwargs['level'] == 20  # logging.INFO

    @patch('configurator.avahi.logging.basicConfig')
    def test_setup_logging_verbose(self, mock_logging):
        """Test logging setup with verbose flag"""
        setup_logging(verbose=True)

        mock_logging.assert_called_once()
        call_kwargs = mock_logging.call_args[1]
        assert call_kwargs['level'] == 10  # logging.DEBUG


class TestAvahiHelperFunctions:
    """Targeted branch tests for avahi helper functions."""

    def test_filter_removes_commented_allow_and_deny_in_server_section(self):
        """Commented allow/deny rules should be removed only within [server]."""
        lines = [
            "[server]\n",
            "#allow-interfaces=eth1\n",
            "#deny-interfaces=docker0\n",
            "[reflector]\n",
            "#allow-interfaces=lo\n",
        ]

        new_lines, modified, found_allow, in_server = _filter_server_interface_rules(lines)

        assert modified is True
        assert found_allow is True
        assert in_server is False
        assert "#allow-interfaces=eth1\n" not in new_lines
        assert "#deny-interfaces=docker0\n" not in new_lines
        assert "#allow-interfaces=lo\n" in new_lines

    def test_filter_reports_server_section_open_at_eof(self):
        """When file ends inside [server], helper should report in_server_section=True."""
        lines = ["[server]\n", "host-name=test\n"]

        _, modified, found_allow, in_server = _filter_server_interface_rules(lines)

        assert modified is False
        assert found_allow is False
        assert in_server is True

    def test_ensure_inserts_before_next_section(self):
        """Allow rule should be inserted when leaving [server] for another section."""
        lines = ["[server]\n", "use-ipv4=yes\n", "[publish]\n", "publish-hinfo=yes\n"]

        final_lines, modified = _ensure_allow_interfaces(lines)

        assert modified is True
        assert final_lines == [
            "[server]\n",
            "use-ipv4=yes\n",
            ALLOW_INTERFACES_LINE,
            "[publish]\n",
            "publish-hinfo=yes\n",
        ]

    def test_ensure_inserts_when_server_is_last_section(self):
        """Allow rule should be appended when [server] is the last section in file."""
        lines = ["[server]\n", "use-ipv4=yes\n"]

        final_lines, modified = _ensure_allow_interfaces(lines)

        assert modified is True
        assert final_lines[-1] == ALLOW_INTERFACES_LINE

    @patch('configurator.avahi.subprocess.run')
    def test_restart_or_start_start_failure_still_returns_true(self, mock_run):
        """Start failure should still return True after config was updated."""
        active_result = MagicMock(returncode=1, stderr="")
        start_result = MagicMock(returncode=1, stderr="failed start")
        mock_run.side_effect = [active_result, start_result]

        assert _restart_or_start_avahi() is True

    @patch('configurator.avahi.subprocess.run', side_effect=OSError("systemctl missing"))
    def test_restart_or_start_subprocess_exception_returns_true(self, _mock_run):
        """Systemctl invocation errors should be tolerated after config write."""
        assert _restart_or_start_avahi() is True


class TestCheckOnlyAndMain:
    """Coverage for check-only and CLI dispatch paths."""

    @patch('configurator.avahi.os.path.exists', return_value=False)
    @patch('builtins.print')
    def test_check_only_not_installed(self, mock_print, _mock_exists):
        """check-only should return success when Avahi config is absent."""
        assert _check_only_result() == 0
        mock_print.assert_called_once_with("Avahi daemon not installed")

    @patch('configurator.avahi.os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='[server]\nallow-interfaces=eth0,wlan0\n')
    @patch('builtins.print')
    def test_check_only_already_correct(self, mock_print, _mock_file, _mock_exists):
        """check-only should report configured state when allow rule is present."""
        assert _check_only_result() == 0
        mock_print.assert_called_once_with(
            "Avahi configuration is correct - only advertising on physical interfaces"
        )

    @patch('configurator.avahi.os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='[server]\nuse-ipv4=yes\n')
    @patch('builtins.print')
    def test_check_only_needs_update(self, mock_print, _mock_file, _mock_exists):
        """check-only should return 1 when allow rule is missing."""
        assert _check_only_result() == 1
        mock_print.assert_called_once_with("Avahi configuration needs updating")

    @patch('configurator.avahi.os.path.exists', return_value=True)
    @patch('builtins.open', side_effect=OSError("read failed"))
    def test_check_only_read_error(self, _mock_file, _mock_exists):
        """check-only should return 1 on file read error."""
        assert _check_only_result() == 1

    @patch('configurator.avahi.setup_logging')
    @patch('configurator.avahi._check_only_result', return_value=0)
    def test_main_check_only_path(self, mock_check_only, mock_setup_logging):
        """main should dispatch to check-only without root check."""
        with patch('sys.argv', ['config-avahi', '--check-only']):
            result = main()

        assert result == 0
        mock_setup_logging.assert_called_once_with(False)
        mock_check_only.assert_called_once()

    @patch('configurator.avahi.setup_logging')
    @patch('configurator.avahi.check_root_privileges', return_value=False)
    def test_main_non_root_returns_error(self, mock_check_root, mock_setup_logging):
        """main should fail in apply mode when not running as root."""
        with patch('sys.argv', ['config-avahi']):
            result = main()

        assert result == 1
        mock_setup_logging.assert_called_once_with(False)
        mock_check_root.assert_called_once()

    @patch('configurator.avahi.setup_logging')
    @patch('configurator.avahi.check_root_privileges', return_value=True)
    @patch('configurator.avahi.configure_avahi_interfaces', return_value=False)
    def test_main_apply_failure_returns_error(self, mock_configure, mock_check_root, mock_setup_logging):
        """main should return 1 when configuration apply fails."""
        with patch('sys.argv', ['config-avahi']):
            result = main()

        assert result == 1
        mock_setup_logging.assert_called_once_with(False)
        mock_check_root.assert_called_once()
        mock_configure.assert_called_once()

    @patch('configurator.avahi.setup_logging')
    @patch('configurator.avahi.check_root_privileges', return_value=True)
    @patch('configurator.avahi.configure_avahi_interfaces', return_value=True)
    def test_main_apply_success_returns_zero(self, mock_configure, mock_check_root, mock_setup_logging):
        """main should return 0 when apply mode succeeds."""
        with patch('sys.argv', ['config-avahi']):
            result = main()

        assert result == 0
        mock_setup_logging.assert_called_once_with(False)
        mock_check_root.assert_called_once()
        mock_configure.assert_called_once()

    @patch('configurator.avahi.setup_logging')
    @patch('configurator.avahi._check_only_result', return_value=0)
    def test_main_passes_verbose_flag(self, mock_check_only, mock_setup_logging):
        """Verbose CLI flag should be forwarded to logging setup."""
        with patch('sys.argv', ['config-avahi', '--check-only', '-v']):
            result = main()

        assert result == 0
        mock_setup_logging.assert_called_once_with(True)
        mock_check_only.assert_called_once()
