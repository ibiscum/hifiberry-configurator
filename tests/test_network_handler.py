#!/usr/bin/env python3
"""Regression tests for network handler module."""

import builtins
import importlib
import unittest
from unittest.mock import patch

import configurator.handlers.network_handler as network_handler


class TestNetworkHandler(unittest.TestCase):
    """Tests for GET network config handler behavior."""

    def setUp(self):
        self.handler = network_handler.NetworkHandler()

    @patch("configurator.handlers.network_handler.get_network_config")
    @patch("configurator.handlers.network_handler.jsonify")
    def test_handle_get_network_config_success(self, mock_jsonify, mock_get_network_config):
        """Should return success payload when network data retrieval succeeds."""
        config = {
            "hostname": "hifiberry",
            "interfaces": [{"name": "eth0", "ipv4": "192.168.1.10"}],
        }
        mock_get_network_config.return_value = config
        mock_jsonify.side_effect = lambda payload: payload

        result = self.handler.handle_get_network_config()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], config)
        mock_get_network_config.assert_called_once()

    @patch("configurator.handlers.network_handler.get_network_config")
    @patch("configurator.handlers.network_handler.jsonify")
    def test_handle_get_network_config_error(self, mock_jsonify, mock_get_network_config):
        """Should return structured 500 payload when retrieval raises."""
        mock_get_network_config.side_effect = RuntimeError("network unavailable")
        mock_jsonify.side_effect = lambda payload: payload

        payload, status = self.handler.handle_get_network_config()

        self.assertEqual(status, 500)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "network_config_failed")
        self.assertEqual(payload["message"], "Failed to retrieve network configuration")
        self.assertEqual(payload["data"]["system_error"], "network unavailable")


class TestNetworkHandlerImportFallback(unittest.TestCase):
    """Tests for module-level Flask import fallback behavior."""

    def test_jsonify_stub_raises_when_flask_is_unavailable(self):
        """Fallback jsonify stub should raise a clear runtime error."""
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "flask":
                raise ImportError("flask unavailable")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            reloaded = importlib.reload(network_handler)

        with self.assertRaises(RuntimeError) as exc:
            reloaded.jsonify({"status": "success"})

        self.assertIn("Flask is not installed", str(exc.exception))

        # Restore normal module state for downstream tests.
        importlib.reload(network_handler)


if __name__ == "__main__":
    unittest.main()
