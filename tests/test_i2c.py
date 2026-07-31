#!/usr/bin/env python3
"""Regression tests for i2c module internals."""

import unittest
from unittest.mock import MagicMock, patch

from configurator import i2c as i2c_module


class TestScanI2CBus(unittest.TestCase):
    """Tests for scan_i2c_bus."""

    @patch('configurator.i2c.smbus2')
    def test_scan_i2c_bus_closes_bus_on_unexpected_exception(self, mock_smbus2):
        """Bus handle must be closed even when scan loop raises unexpectedly."""
        mock_bus = MagicMock()

        def read_side_effect(addr):
            if addr == 0x10:
                raise RuntimeError('unexpected read failure')
            raise OSError('no device')

        mock_bus.read_byte.side_effect = read_side_effect
        mock_smbus2.SMBus.return_value = mock_bus

        with self.assertRaises(RuntimeError):
            i2c_module.scan_i2c_bus(1)

        mock_bus.close.assert_called_once()

    @patch('configurator.i2c.os.listdir')
    @patch('configurator.i2c.os.path.exists')
    @patch('configurator.i2c.smbus2')
    def test_scan_i2c_bus_skips_malformed_kernel_entries(self, mock_smbus2, mock_exists, mock_listdir):
        """Malformed sysfs entries should not prevent collecting valid addresses."""
        mock_bus = MagicMock()
        mock_bus.read_byte.side_effect = OSError('no device')
        mock_smbus2.SMBus.return_value = mock_bus

        def exists_side_effect(path):
            return path == '/sys/bus/i2c/devices/i2c-1'

        mock_exists.side_effect = exists_side_effect
        mock_listdir.return_value = ['1-0048', '1-zzzz', '1-0050']

        result = i2c_module.scan_i2c_bus(1)

        self.assertEqual(result['kernel_used'], ['0x48', '0x50'])
        self.assertEqual(result['detected_devices'], [])


class TestGetI2CInfo(unittest.TestCase):
    """Tests for get_i2c_info."""

    @patch('configurator.i2c.os.path.exists')
    def test_get_i2c_info_bus_missing(self, mock_exists):
        """Missing /dev bus should return structured error payload."""
        mock_exists.return_value = False

        result = i2c_module.get_i2c_info(1)

        self.assertEqual(result['bus_exists'], False)
        self.assertIn('error', result)

    @patch('configurator.i2c.os.path.exists')
    def test_get_i2c_info_smbus_unavailable(self, mock_exists):
        """When smbus2 is unavailable and bus exists, payload includes module error."""
        mock_exists.return_value = True

        with patch('configurator.i2c.smbus2', None):
            result = i2c_module.get_i2c_info(1)

        self.assertTrue(result['bus_exists'])
        self.assertFalse(result['smbus2_available'])
        self.assertIn('smbus2 module not available', result['error'])

    @patch('configurator.i2c.smbus2', new=MagicMock())
    @patch('configurator.i2c.scan_i2c_bus')
    @patch('configurator.i2c.os.path.exists')
    def test_get_i2c_info_merges_scan_result(self, mock_exists, mock_scan):
        """Successful scans should be merged into base metadata payload."""
        mock_exists.return_value = True
        mock_scan.return_value = {
            'bus_number': 1,
            'detected_devices': ['0x48'],
            'kernel_used': ['0x48'],
            'scan_range': '0x03-0x77',
        }

        result = i2c_module.get_i2c_info(1)

        self.assertEqual(result['bus_number'], 1)
        self.assertEqual(result['detected_devices'], ['0x48'])
        self.assertEqual(result['kernel_used'], ['0x48'])
        self.assertNotIn('error', result)


if __name__ == '__main__':
    unittest.main()
