#!/usr/bin/env python3
"""Regression tests for i2c handler behavior without Flask installed."""

import importlib
import sys
import unittest
from unittest.mock import patch


_MISSING = object()


class TestI2CHandlerNoFlask(unittest.TestCase):
    """Ensure handler fallback path works when Flask import is unavailable."""

    @classmethod
    def setUpClass(cls):
        cls._orig_flask = sys.modules.get('flask', _MISSING)
        # Force `import flask` to fail even when Flask is installed.
        sys.modules['flask'] = None  # type: ignore[assignment]
        cls._orig_i2c_handler = sys.modules.pop('configurator.handlers.i2c_handler', None)
        cls.module = importlib.import_module('configurator.handlers.i2c_handler')

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop('configurator.handlers.i2c_handler', None)
        if cls._orig_i2c_handler is not None:
            sys.modules['configurator.handlers.i2c_handler'] = cls._orig_i2c_handler
        if cls._orig_flask is _MISSING:
            sys.modules.pop('flask', None)
        else:
            sys.modules['flask'] = cls._orig_flask

    def test_handle_get_i2c_devices_success_returns_dict(self):
        """Without Flask, successful responses should be plain dictionaries."""
        handler = self.module.I2CHandler()

        with patch.object(self.module, 'get_i2c_info', return_value={'bus_number': 1}):
            response = handler.handle_get_i2c_devices()

        self.assertIsInstance(response, dict)
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['data']['bus_number'], 1)

    def test_handle_get_i2c_devices_validation_error_returns_tuple(self):
        """Validation errors should still carry HTTP status via tuple fallback."""
        handler = self.module.I2CHandler()

        with patch.object(self.module.request.args, 'get', return_value=99):
            response, status_code = handler.handle_get_i2c_devices()

        self.assertEqual(status_code, 400)
        self.assertIsInstance(response, dict)
        self.assertEqual(response['status'], 'error')
        self.assertEqual(response['error'], 'invalid_bus_number')


if __name__ == '__main__':
    unittest.main()
