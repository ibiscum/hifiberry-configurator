"""
Comprehensive regression test suite for src/systeminfo module

Tests all system information collection functions including caching,
error handling, and data formatting.
"""

import unittest
import argparse
from unittest.mock import patch, MagicMock, mock_open

from configurator.systeminfo import SystemInfo


class TestSystemInfoInitialization(unittest.TestCase):
    """Tests for SystemInfo initialization"""

    def test_initialization(self):
        """Test SystemInfo object initialization"""
        info = SystemInfo()

        self.assertIsNone(info._pi_model)
        self.assertIsNone(info._hat_info)
        self.assertIsNone(info._system_uuid)
        self.assertIsNone(info._soundcard)
        self.assertIsNotNone(info.logger)

    def test_logger_name(self):
        """Test logger is correctly named"""
        info = SystemInfo()

        self.assertEqual(info.logger.name, "configurator.systeminfo")


class TestGetPiModelName(unittest.TestCase):
    """Tests for get_pi_model_name method"""

    @patch('configurator.systeminfo.PiModel')
    def test_get_pi_model_name_success(self, mock_pi_model_class):
        """Test successful Pi model name retrieval"""
        mock_instance = MagicMock()
        mock_instance.get_model_name.return_value = "Raspberry Pi 4 Model B\x00"
        mock_pi_model_class.return_value = mock_instance

        info = SystemInfo()
        result = info.get_pi_model_name()

        self.assertEqual(result, "Raspberry Pi 4 Model B")

    @patch('configurator.systeminfo.PiModel')
    def test_get_pi_model_name_error(self, mock_pi_model_class):
        """Test Pi model name retrieval error handling"""
        mock_pi_model_class.side_effect = Exception("PiModel error")

        info = SystemInfo()
        result = info.get_pi_model_name()

        self.assertEqual(result, "unknown")

    @patch('configurator.systeminfo.PiModel')
    def test_get_pi_model_name_caching(self, mock_pi_model_class):
        """Test Pi model is cached after first call"""
        mock_instance = MagicMock()
        mock_instance.get_model_name.return_value = "Raspberry Pi 3 Model B"
        mock_pi_model_class.return_value = mock_instance

        info = SystemInfo()
        result1 = info.get_pi_model_name()
        result2 = info.get_pi_model_name()

        self.assertEqual(result1, "Raspberry Pi 3 Model B")
        self.assertEqual(result2, "Raspberry Pi 3 Model B")
        mock_pi_model_class.assert_called_once()


class TestGetHatVendorCard(unittest.TestCase):
    """Tests for get_hat_vendor_card method"""

    @patch('configurator.systeminfo.get_hat_info')
    def test_get_hat_vendor_card_success(self, mock_get_hat):
        """Test successful HAT vendor card retrieval"""
        mock_get_hat.return_value = {
            'vendor': 'HiFiBerry',
            'product': 'DAC+ Standard'
        }

        info = SystemInfo()
        result = info.get_hat_vendor_card()

        self.assertEqual(result, "HiFiBerry:DAC+ Standard")

    @patch('configurator.systeminfo.get_hat_info')
    def test_get_hat_vendor_card_none_values(self, mock_get_hat):
        """Test HAT vendor card with None values"""
        mock_get_hat.return_value = {'vendor': None, 'product': None}

        info = SystemInfo()
        result = info.get_hat_vendor_card()

        self.assertEqual(result, "unknown:unknown")

    @patch('configurator.systeminfo.get_hat_info')
    def test_get_hat_vendor_card_missing_keys(self, mock_get_hat):
        """Test HAT vendor card with missing keys"""
        mock_get_hat.return_value = {}

        info = SystemInfo()
        result = info.get_hat_vendor_card()

        self.assertEqual(result, "unknown:unknown")

    @patch('configurator.systeminfo.get_hat_info')
    def test_get_hat_vendor_card_error(self, mock_get_hat):
        """Test HAT vendor card retrieval error handling"""
        mock_get_hat.side_effect = Exception("HAT error")

        info = SystemInfo()
        result = info.get_hat_vendor_card()

        self.assertEqual(result, "unknown:unknown")


class TestGetSystemUuid(unittest.TestCase):
    """Tests for get_system_uuid method"""

    @patch('configurator.systeminfo.open', new_callable=mock_open, read_data="12345678-1234-1234-1234-123456789012\n")
    def test_get_system_uuid_success(self, mock_file):
        """Test successful system UUID retrieval"""
        info = SystemInfo()
        result = info.get_system_uuid()

        self.assertEqual(result, "12345678-1234-1234-1234-123456789012")
        mock_file.assert_called_once_with("/etc/uuid", "r")

    @patch('configurator.systeminfo.open', side_effect=FileNotFoundError)
    def test_get_system_uuid_file_not_found(self, mock_file):
        """Test system UUID when file not found"""
        info = SystemInfo()
        result = info.get_system_uuid()

        self.assertIsNone(result)

    @patch('configurator.systeminfo.open', side_effect=PermissionError)
    def test_get_system_uuid_permission_denied(self, mock_file):
        """Test system UUID when permission denied"""
        info = SystemInfo()
        result = info.get_system_uuid()

        self.assertIsNone(result)

    @patch('configurator.systeminfo.open', new_callable=mock_open, read_data="uuid-with-spaces   \n")
    def test_get_system_uuid_strips_whitespace(self, mock_file):
        """Test system UUID whitespace stripping"""
        info = SystemInfo()
        result = info.get_system_uuid()

        self.assertEqual(result, "uuid-with-spaces")


class TestGetHostnames(unittest.TestCase):
    """Tests for get_hostnames method"""

    @patch('configurator.systeminfo.get_hostnames_with_fallback')
    def test_get_hostnames_success(self, mock_get_hostnames):
        """Test successful hostname retrieval"""
        mock_get_hostnames.return_value = ("myhost", "My Pretty Host")

        info = SystemInfo()
        result = info.get_hostnames()

        self.assertEqual(result, ("myhost", "My Pretty Host"))

    @patch('configurator.systeminfo.get_hostnames_with_fallback')
    def test_get_hostnames_none_values(self, mock_get_hostnames):
        """Test hostname retrieval with None values"""
        mock_get_hostnames.return_value = (None, None)

        info = SystemInfo()
        result = info.get_hostnames()

        self.assertEqual(result, (None, None))

    @patch('configurator.systeminfo.get_hostnames_with_fallback')
    def test_get_hostnames_error(self, mock_get_hostnames):
        """Test hostname retrieval error handling"""
        mock_get_hostnames.side_effect = Exception("Hostname error")

        info = SystemInfo()
        result = info.get_hostnames()

        self.assertEqual(result, (None, None))


class TestGetSoundcardInfo(unittest.TestCase):
    """Tests for get_soundcard_info method"""

    @patch('configurator.systeminfo.SystemInfo._is_soundcard_fixed_in_config_txt')
    @patch('configurator.systeminfo.SystemInfo._get_soundcard_pin_source')
    @patch('configurator.systeminfo.SystemInfo._get_soundcard')
    def test_get_soundcard_info_success(self, mock_get_soundcard, mock_pin_source, mock_fixed):
        """Test successful soundcard info retrieval"""
        mock_soundcard = MagicMock()
        mock_soundcard.name = "HiFiBerry DAC+"
        mock_soundcard.volume_control = "Digital"
        mock_soundcard.headphone_volume_control = None
        mock_soundcard.get_hardware_index.return_value = 0
        mock_soundcard.output_channels = 2
        mock_soundcard.input_channels = 0
        mock_soundcard.features = ["DSP"]
        mock_soundcard.hat_name = "DAC+"
        mock_soundcard.supports_dsp = True
        mock_soundcard.card_type = ["DAC", "DSP"]
        mock_get_soundcard.return_value = mock_soundcard
        mock_fixed.return_value = False
        mock_pin_source.return_value = None

        info = SystemInfo()
        result = info.get_soundcard_info()

        self.assertEqual(result['name'], "HiFiBerry DAC+")
        self.assertEqual(result['volume_control'], "Digital")
        self.assertIsNone(result['headphone_volume_control'])
        self.assertEqual(result['hardware_index'], 0)
        self.assertEqual(result['output_channels'], 2)
        self.assertFalse(result['fixedInConfigTxt'])
        self.assertIsNone(result['pinSource'])

    @patch('configurator.systeminfo.SystemInfo._get_soundcard')
    def test_get_soundcard_info_error(self, mock_get_soundcard):
        """Test soundcard info error handling"""
        mock_get_soundcard.side_effect = Exception("Soundcard error")

        info = SystemInfo()
        result = info.get_soundcard_info()

        self.assertEqual(result['name'], 'unknown')
        self.assertIsNone(result['volume_control'])
        self.assertIsNone(result['hardware_index'])
        self.assertEqual(result['output_channels'], 0)
        self.assertIn('pinSource', result)
        self.assertIsNone(result['pinSource'])


class TestSoundcardPinHelpers(unittest.TestCase):
    """Tests for config-based soundcard pin helper methods."""

    @patch('configurator.systeminfo.open', side_effect=FileNotFoundError)
    def test_is_soundcard_fixed_in_config_txt_missing_file(self, _mock_open):
        """Missing config file should be treated as no fixed pin."""
        info = SystemInfo()
        self.assertFalse(info._is_soundcard_fixed_in_config_txt())

    @patch('configurator.systeminfo.open', new_callable=mock_open, read_data="# HiFiBerry sound detection disabled\n")
    @patch('configurator.configtxt.HIFIBERRY_DETECTION_DISABLED', "# HiFiBerry sound detection disabled")
    def test_is_soundcard_fixed_in_config_txt_detects_comment(self, _mock_open):
        """Detection-disabled marker comment should be recognized."""
        info = SystemInfo()
        self.assertTrue(info._is_soundcard_fixed_in_config_txt())


class TestGetSystemInfoDict(unittest.TestCase):
    """Tests for get_system_info_dict method"""

    @patch('configurator.systeminfo.SystemInfo._get_memory_info')
    @patch('configurator.systeminfo.SystemInfo._get_hostname_info')
    @patch('configurator.systeminfo.SystemInfo.get_soundcard_info')
    @patch('configurator.systeminfo.SystemInfo._get_system_uuid')
    @patch('configurator.systeminfo.SystemInfo._get_hat_info')
    @patch('configurator.systeminfo.SystemInfo._get_pi_model')
    def test_get_system_info_dict_success(self, mock_pi, mock_hat, mock_uuid,
                                          mock_soundcard, mock_hostname, mock_memory):
        """Test successful system info dict retrieval"""
        mock_pi.return_value = MagicMock(get_model_name=lambda: "Pi 4\x00", version="1.2")
        mock_hat.return_value = {'vendor': 'HiFiBerry', 'product': 'DAC+', 'uuid': 'hat-uuid'}
        mock_uuid.return_value = "sys-uuid-123"
        mock_soundcard.return_value = {'name': 'DAC+', 'volume_control': 'Digital'}
        mock_hostname.return_value = ('myhost', 'My Host')
        mock_memory.return_value = {'total_gb': 4, 'total_mb': 4096, 'total_kb': 4194304}

        info = SystemInfo()
        result = info.get_system_info_dict()

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['pi_model']['name'], 'Pi 4')
        self.assertEqual(result['hat_info']['vendor'], 'HiFiBerry')
        self.assertEqual(result['system']['uuid'], 'sys-uuid-123')
        self.assertEqual(result['soundcard']['name'], 'DAC+')

    @patch('configurator.systeminfo.SystemInfo._get_pi_model')
    def test_get_system_info_dict_error(self, mock_pi):
        """Test system info dict error handling"""
        mock_pi.side_effect = Exception("Error")

        info = SystemInfo()
        result = info.get_system_info_dict()

        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)
        self.assertIn('headphone_volume_control', result['soundcard'])
        self.assertIn('fixedInConfigTxt', result['soundcard'])
        self.assertIn('pinSource', result['soundcard'])


class TestGetFlatInfoDict(unittest.TestCase):
    """Tests for get_flat_info_dict method"""

    @patch('configurator.systeminfo.SystemInfo._get_memory_info')
    @patch('configurator.systeminfo.SystemInfo._get_hostname_info')
    @patch('configurator.systeminfo.SystemInfo.get_soundcard_info')
    @patch('configurator.systeminfo.SystemInfo._get_system_uuid')
    @patch('configurator.systeminfo.SystemInfo._get_hat_info')
    @patch('configurator.systeminfo.SystemInfo._get_pi_model')
    def test_get_flat_info_dict_success(self, mock_pi, mock_hat, mock_uuid,
                                        mock_soundcard, mock_hostname, mock_memory):
        """Test successful flat info dict retrieval"""
        mock_pi.return_value = MagicMock(get_model_name=lambda: "Pi 4\x00", version="1.2")
        mock_hat.return_value = {'vendor': 'HiFiBerry', 'product': 'DAC+'}
        mock_uuid.return_value = "sys-uuid-123"
        mock_soundcard.return_value = {'name': 'DAC+'}
        mock_hostname.return_value = ('myhost', 'My Host')
        mock_memory.return_value = {'total_gb': 4, 'total_mb': 4096}

        info = SystemInfo()
        result = info.get_flat_info_dict()

        self.assertEqual(result['Pi Model'], 'Pi 4 1.2')
        self.assertEqual(result['Memory'], '4 GB (4096 MB)')
        self.assertEqual(result['HAT'], 'HiFiBerry DAC+')
        self.assertEqual(result['Sound Card'], 'DAC+')
        self.assertEqual(result['UUID'], 'sys-uuid-123')
        self.assertEqual(result['Hostname'], 'myhost')

    @patch('configurator.systeminfo.SystemInfo._get_memory_info')
    @patch('configurator.systeminfo.SystemInfo._get_hostname_info')
    @patch('configurator.systeminfo.SystemInfo.get_soundcard_info')
    @patch('configurator.systeminfo.SystemInfo._get_system_uuid')
    @patch('configurator.systeminfo.SystemInfo._get_hat_info')
    @patch('configurator.systeminfo.SystemInfo._get_pi_model')
    def test_get_flat_info_dict_with_none_values(self, mock_pi, mock_hat, mock_uuid,
                                                   mock_soundcard, mock_hostname, mock_memory):
        """Test flat info dict with None values"""
        mock_pi.return_value = MagicMock(get_model_name=lambda: "Pi 4", version='unknown')
        mock_hat.return_value = {'vendor': None, 'product': None}
        mock_uuid.return_value = None
        mock_soundcard.return_value = {'name': 'unknown'}
        mock_hostname.return_value = (None, None)
        mock_memory.return_value = {}

        info = SystemInfo()
        result = info.get_flat_info_dict()

        self.assertEqual(result['Pi Model'], 'Pi 4')
        self.assertEqual(result['Memory'], 'unknown')
        self.assertEqual(result['HAT'], 'unknown unknown')
        self.assertEqual(result['UUID'], 'unknown')
        self.assertEqual(result['Hostname'], 'unknown')

    @patch('configurator.systeminfo.SystemInfo._get_pi_model')
    def test_get_flat_info_dict_error(self, mock_pi):
        """Test flat info dict error handling"""
        mock_pi.side_effect = Exception("Error")

        info = SystemInfo()
        result = info.get_flat_info_dict()

        self.assertEqual(result['Pi Model'], 'unknown')
        self.assertEqual(result['Sound Card'], 'unknown')


class TestGetSimpleOutput(unittest.TestCase):
    """Tests for get_simple_output method"""

    @patch('configurator.systeminfo.SystemInfo.get_system_uuid')
    @patch('configurator.systeminfo.SystemInfo.get_soundcard_info')
    @patch('configurator.systeminfo.SystemInfo.get_hat_vendor_card')
    @patch('configurator.systeminfo.SystemInfo.get_pi_model_name')
    def test_get_simple_output_with_uuid(self, mock_pi_name, mock_hat,
                                         mock_soundcard, mock_uuid):
        """Test simple output with all fields"""
        mock_pi_name.return_value = "Raspberry Pi 4 Model B"
        mock_hat.return_value = "HiFiBerry:DAC+"
        mock_soundcard.return_value = {'name': 'HiFiBerry DAC+'}
        mock_uuid.return_value = "12345678-1234-1234-1234-123456789012"

        info = SystemInfo()
        result = info.get_simple_output()

        self.assertIn("Pi Model: Raspberry Pi 4 Model B", result)
        self.assertIn("Hat info: HiFiBerry:DAC+", result)
        self.assertIn("Sound Card: HiFiBerry DAC+", result)
        self.assertIn("System UUID: 12345678-1234-1234-1234-123456789012", result)

    @patch('configurator.systeminfo.SystemInfo.get_system_uuid')
    @patch('configurator.systeminfo.SystemInfo.get_soundcard_info')
    @patch('configurator.systeminfo.SystemInfo.get_hat_vendor_card')
    @patch('configurator.systeminfo.SystemInfo.get_pi_model_name')
    def test_get_simple_output_without_uuid(self, mock_pi_name, mock_hat,
                                            mock_soundcard, mock_uuid):
        """Test simple output without UUID"""
        mock_pi_name.return_value = "Raspberry Pi 3 Model B"
        mock_hat.return_value = "unknown:unknown"
        mock_soundcard.return_value = {'name': 'unknown'}
        mock_uuid.return_value = None

        info = SystemInfo()
        result = info.get_simple_output()

        self.assertIn("Pi Model: Raspberry Pi 3 Model B", result)
        self.assertNotIn("System UUID:", result)


class TestPrintSimpleOutput(unittest.TestCase):
    """Tests for print_simple_output method"""

    @patch('builtins.print')
    @patch('configurator.systeminfo.SystemInfo.get_simple_output')
    def test_print_simple_output(self, mock_get_output, mock_print):
        """Test print simple output"""
        mock_get_output.return_value = "Test output"

        info = SystemInfo()
        info.print_simple_output()

        mock_print.assert_called_once_with("Test output")


class TestCaching(unittest.TestCase):
    """Tests for caching behavior"""

    @patch('configurator.systeminfo.PiModel')
    def test_pi_model_caching(self, mock_pi_model_class):
        """Test Pi model caching across calls"""
        mock_instance = MagicMock()
        mock_pi_model_class.return_value = mock_instance

        info = SystemInfo()
        result1 = info._get_pi_model()
        result2 = info._get_pi_model()

        self.assertIs(result1, result2)
        mock_pi_model_class.assert_called_once()

    @patch('configurator.systeminfo.get_hat_info')
    def test_hat_info_caching(self, mock_get_hat):
        """Test HAT info caching across calls"""
        mock_get_hat.return_value = {'vendor': 'HiFiBerry'}

        info = SystemInfo()
        result1 = info._get_hat_info()
        result2 = info._get_hat_info()

        self.assertEqual(result1, result2)
        mock_get_hat.assert_called_once()

    @patch('configurator.systeminfo.open', new_callable=mock_open, read_data="uuid-123\n")
    def test_uuid_caching(self, mock_file):
        """Test UUID caching across calls"""
        info = SystemInfo()
        result1 = info._get_system_uuid()
        result2 = info._get_system_uuid()

        self.assertEqual(result1, result2)
        mock_file.assert_called_once()

    @patch('configurator.systeminfo.Soundcard')
    def test_soundcard_caching(self, mock_soundcard_class):
        """Test soundcard caching across calls"""
        mock_instance = MagicMock()
        mock_soundcard_class.return_value = mock_instance

        info = SystemInfo()
        result1 = info._get_soundcard()
        result2 = info._get_soundcard()

        self.assertIs(result1, result2)
        mock_soundcard_class.assert_called_once()

    @patch('configurator.systeminfo.Soundcard')
    def test_soundcard_no_cache_when_prioritize_aplay(self, mock_soundcard_class):
        """Test soundcard caching is bypassed when prioritize_aplay is True"""
        mock_instance = MagicMock()
        mock_soundcard_class.return_value = mock_instance

        info = SystemInfo()
        info._get_soundcard(prioritize_aplay=False)
        info._get_soundcard(prioritize_aplay=True)

        # Should create a new instance due to prioritize_aplay=True
        self.assertEqual(mock_soundcard_class.call_count, 2)


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling across methods"""

    @patch('configurator.systeminfo.SystemInfo._get_pi_model')
    @patch('configurator.systeminfo.SystemInfo._get_hat_info')
    @patch('configurator.systeminfo.SystemInfo._get_system_uuid')
    def test_graceful_error_in_system_info(self, mock_uuid, mock_hat, mock_pi):
        """Test graceful error handling in system info collection"""
        mock_pi.side_effect = Exception("PI error")
        mock_hat.return_value = {'vendor': 'Test'}
        mock_uuid.return_value = None

        info = SystemInfo()
        result = info.get_system_info_dict()

        # Should still return a dict with error status
        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)


class TestMemoryInfo(unittest.TestCase):
    """Tests for _get_memory_info parsing and error handling."""

    @patch('configurator.systeminfo.open', new_callable=mock_open,
           read_data="MemTotal:       1572864 kB\nMemFree:          1024 kB\n")
    def test_get_memory_info_parses_memtotal(self, _mock_file):
        info = SystemInfo()
        result = info._get_memory_info()

        self.assertEqual(result['total_kb'], 1572864)
        self.assertEqual(result['total_mb'], 1536)
        self.assertEqual(result['total_gb'], 2)

    @patch('configurator.systeminfo.open', new_callable=mock_open,
           read_data="MemFree: 1234 kB\n")
    def test_get_memory_info_without_memtotal_returns_empty_dict(self, _mock_file):
        info = SystemInfo()
        result = info._get_memory_info()

        self.assertEqual(result, {})

    @patch('configurator.systeminfo.open', side_effect=OSError("cannot read"))
    def test_get_memory_info_exception_returns_unknowns(self, _mock_file):
        info = SystemInfo()
        result = info._get_memory_info()

        self.assertEqual(result['total_kb'], None)
        self.assertEqual(result['total_mb'], None)
        self.assertEqual(result['total_gb'], None)


class TestSoundcardPinSource(unittest.TestCase):
    """Tests for _get_soundcard_pin_source helper branching."""

    @patch('configurator.configdb.ConfigDB')
    def test_get_soundcard_pin_source_prefers_configdb(self, mock_configdb):
        mock_configdb.return_value.get.return_value = "DAC2 Pro"

        info = SystemInfo()
        result = info._get_soundcard_pin_source()

        self.assertEqual(result, 'configdb')

    @patch('configurator.soundcard_detector.SoundcardDetector')
    @patch('configurator.configdb.ConfigDB')
    def test_get_soundcard_pin_source_uses_config_txt_when_db_empty(self, mock_configdb, mock_detector):
        mock_configdb.return_value.get.return_value = None
        mock_detector.return_value.detect_from_config_txt_comment.return_value = True

        info = SystemInfo()
        result = info._get_soundcard_pin_source()

        self.assertEqual(result, 'config.txt')

    @patch('configurator.soundcard_detector.SoundcardDetector')
    @patch('configurator.configdb.ConfigDB', side_effect=Exception("db unavailable"))
    def test_get_soundcard_pin_source_returns_none_when_no_pin_found(self, _mock_db, mock_detector):
        mock_detector.return_value.detect_from_config_txt_comment.return_value = False

        info = SystemInfo()
        result = info._get_soundcard_pin_source()

        self.assertIsNone(result)

    @patch('configurator.soundcard_detector.SoundcardDetector', side_effect=Exception("detector unavailable"))
    @patch('configurator.configdb.ConfigDB', side_effect=Exception("db unavailable"))
    def test_get_soundcard_pin_source_handles_both_sources_failing(self, _mock_db, _mock_detector):
        info = SystemInfo()
        result = info._get_soundcard_pin_source()

        self.assertIsNone(result)


class TestDetectionDisabledMarkerEdgeCases(unittest.TestCase):
    """Additional tests for config.txt marker checks."""

    @patch('configurator.systeminfo.open', new_callable=mock_open, read_data="# not the marker\n")
    @patch('configurator.configtxt.HIFIBERRY_DETECTION_DISABLED', "# HiFiBerry sound detection disabled")
    def test_is_soundcard_fixed_in_config_txt_false_without_marker(self, _mock_open):
        info = SystemInfo()
        self.assertFalse(info._is_soundcard_fixed_in_config_txt())

    @patch('configurator.systeminfo.open', side_effect=OSError("cannot read config"))
    def test_is_soundcard_fixed_in_config_txt_generic_exception(self, _mock_open):
        info = SystemInfo()
        self.assertFalse(info._is_soundcard_fixed_in_config_txt())


class TestSystemInfoCLI(unittest.TestCase):
    """Tests for CLI helpers and main entrypoint."""

    def test_parse_arguments_defaults(self):
        with patch('sys.argv', ['systeminfo']):
            args = __import__('configurator.systeminfo', fromlist=['parse_arguments']).parse_arguments()

        self.assertFalse(args.verbose)
        self.assertFalse(args.json)

    def test_parse_arguments_verbose_and_json(self):
        with patch('sys.argv', ['systeminfo', '--verbose', '--json']):
            args = __import__('configurator.systeminfo', fromlist=['parse_arguments']).parse_arguments()

        self.assertTrue(args.verbose)
        self.assertTrue(args.json)

    def test_setup_logging_uses_stderr_stream(self):
        module = __import__('configurator.systeminfo', fromlist=['setup_logging'])

        root_logger = module.logging.getLogger()
        original_handlers = list(root_logger.handlers)
        original_level = root_logger.level

        try:
            module.setup_logging(verbose=True)

            self.assertEqual(root_logger.level, module.logging.DEBUG)
            self.assertEqual(len(root_logger.handlers), 1)
            handler = root_logger.handlers[0]
            self.assertEqual(handler.level, module.logging.DEBUG)
            self.assertIs(handler.stream, module.sys.stderr)
        finally:
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            for handler in original_handlers:
                root_logger.addHandler(handler)
            root_logger.setLevel(original_level)

    @patch('builtins.print')
    @patch('json.dumps', return_value='{"ok": true}')
    @patch('configurator.systeminfo.SystemInfo')
    @patch('configurator.systeminfo.setup_logging')
    @patch('configurator.systeminfo.parse_arguments')
    def test_main_json_mode_prints_flat_json(self, mock_parse, mock_setup, mock_info_cls, _mock_dumps, mock_print):
        mock_parse.return_value = argparse.Namespace(verbose=True, json=True)
        mock_info_cls.return_value.get_flat_info_dict.return_value = {'Pi Model': 'Pi 4'}

        module = __import__('configurator.systeminfo', fromlist=['main'])
        module.main()

        mock_setup.assert_called_once_with(True)
        mock_info_cls.return_value.get_flat_info_dict.assert_called_once()
        mock_print.assert_called_once_with('{"ok": true}')

    @patch('configurator.systeminfo.SystemInfo')
    @patch('configurator.systeminfo.setup_logging')
    @patch('configurator.systeminfo.parse_arguments')
    def test_main_text_mode_prints_simple_output(self, mock_parse, mock_setup, mock_info_cls):
        mock_parse.return_value = argparse.Namespace(verbose=False, json=False)

        module = __import__('configurator.systeminfo', fromlist=['main'])
        module.main()

        mock_setup.assert_called_once_with(False)
        mock_info_cls.return_value.print_simple_output.assert_called_once()


if __name__ == '__main__':
    unittest.main()
