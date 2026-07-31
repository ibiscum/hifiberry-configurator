#!/usr/bin/env python3
"""Regression tests for Pi model detection and mapping."""

import unittest
from unittest.mock import mock_open, patch

from configurator.pimodel import PiModel, _normalize_model_name


class TestPiModelNormalization(unittest.TestCase):
    """Tests for model-name normalization helpers."""

    def test_normalize_model_name_removes_nulls_and_whitespace(self):
        """Device-tree model names should be normalized before classification."""
        self.assertEqual(
            _normalize_model_name('Raspberry Pi 4 Model B Rev 1.4\x00\n'),
            'Raspberry Pi 4 Model B Rev 1.4',
        )


class TestPiModelDetection(unittest.TestCase):
    """Tests for PiModel detection and version mapping."""

    @patch('configurator.pimodel.open', new_callable=mock_open, read_data='Raspberry Pi 4 Model B Rev 1.5\x00\n')
    def test_detect_sets_model_and_version_with_null_byte_input(self, _mock_file):
        """Null-terminated model input should still classify correctly."""
        model = PiModel()
        self.assertEqual(model.get_model_name(), 'Raspberry Pi 4 Model B Rev 1.5')
        self.assertEqual(model.get_version(), '4')

    @patch('configurator.pimodel.open', side_effect=FileNotFoundError)
    def test_detect_file_not_found_keeps_unknowns(self, _mock_file):
        """Missing model file should degrade to unknown values."""
        model = PiModel()
        self.assertEqual(model.get_model_name(), 'unknown')
        self.assertEqual(model.get_version(), 'unknown')

    @patch('configurator.pimodel.open', side_effect=PermissionError('denied'))
    def test_detect_oserror_keeps_unknowns(self, _mock_file):
        """OS read errors should not raise and should keep unknown values."""
        model = PiModel()
        self.assertEqual(model.get_model_name(), 'unknown')
        self.assertEqual(model.get_version(), 'unknown')

    @patch('configurator.pimodel.open', new_callable=mock_open, read_data='Raspberry Pi Zero 2 W Rev 1.0\x00\n')
    def test_zero2_mapping(self, _mock_file):
        """Pi Zero 2 W should map to the normalized Zero-2 token."""
        model = PiModel()
        self.assertEqual(model.get_version(), '0W2')

    @patch('configurator.pimodel.open', new_callable=mock_open, read_data='Raspberry Pi Compute Module 5\x00\n')
    def test_cm5_mapping_distinct_from_pi5(self, _mock_file):
        """CM5 should remain distinct from Pi 5 in version mapping."""
        model = PiModel()
        self.assertEqual(model.get_version(), 'CM5')

    @patch('configurator.pimodel.open', new_callable=mock_open, read_data='Raspberry Pi 5 Model B Rev 1.0\x00\n')
    def test_pi5_mapping(self, _mock_file):
        """Pi 5 model should continue mapping to version token 5."""
        model = PiModel()
        self.assertEqual(model.get_version(), '5')

    @patch('configurator.pimodel.open', new_callable=mock_open, read_data='Unknown Raspberry Pi Variant\x00\n')
    def test_unknown_model_maps_to_unknown_version(self, _mock_file):
        """Unmapped model names should default to unknown version."""
        model = PiModel()
        self.assertEqual(model.get_version(), 'unknown')


if __name__ == '__main__':
    unittest.main()
