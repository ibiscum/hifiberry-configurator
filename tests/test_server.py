#!/usr/bin/env python3
"""Direct tests for configurator.server."""

import importlib
import sys
import unittest
from argparse import Namespace
from contextlib import ExitStack
from unittest.mock import MagicMock, patch


def _load_server_module_with_real_flask():
    """Import/reload server with the real Flask module, not test doubles."""
    mocked_flask = sys.modules.pop("flask", None)
    try:
        real_flask = importlib.import_module("flask")
        real_flask_testing = importlib.import_module("flask.testing")
    finally:
        # Keep any prior mock isolated from this module import path.
        if mocked_flask is not None and "flask" not in sys.modules:
            sys.modules["flask"] = mocked_flask

    with patch.dict(sys.modules, {"flask": real_flask, "flask.testing": real_flask_testing}):
        module = importlib.import_module("configurator.server")
        return importlib.reload(module), real_flask, real_flask_testing


server, REAL_FLASK, REAL_FLASK_TESTING = _load_server_module_with_real_flask()


class FakeSettingsManager:
    """Small settings manager test double with registration tracking."""

    def __init__(self, _configdb):
        self.registered = {}

    def register_setting(self, name, save_callback, restore_callback):
        self.registered[name] = {
            "save": save_callback,
            "restore": restore_callback,
        }

    def restore_all_settings(self):
        return {"ok": True}

    def save_all_settings(self):
        return {"ok": True}

    def list_registered_settings(self):
        return list(self.registered.keys())

    def list_saved_settings(self):
        return {}


def build_server_under_test(systeminfo_side_effect=None):
    """Construct ConfigAPIServer with handler dependencies mocked out."""
    stack = ExitStack()

    def _patch_attr(name, value):
        return stack.enter_context(patch.object(server, name, value))

    mock_configdb_cls = _patch_attr("ConfigDB", MagicMock())
    configdb_instance = MagicMock()
    mock_configdb_cls.return_value = configdb_instance
    configdb_instance.get.return_value = None

    mock_systeminfo_cls = _patch_attr("SystemInfo", MagicMock())
    systeminfo_instance = MagicMock()
    mock_systeminfo_cls.return_value = systeminfo_instance
    if systeminfo_side_effect is not None:
        systeminfo_instance.get_system_info_dict.side_effect = systeminfo_side_effect
    else:
        systeminfo_instance.get_system_info_dict.return_value = {"status": "success", "data": {}}

    for handler_symbol in [
        "SystemdHandler",
        "SMBHandler",
        "HostnameHandler",
        "SoundcardHandler",
        "SystemHandler",
        "FilesystemHandler",
        "ScriptHandler",
        "NetworkHandler",
        "I2CHandler",
        "VolumeHandler",
        "BluetoothHandler",
        "BLEProvisioningHandler",
    ]:
        _patch_attr(handler_symbol, MagicMock(return_value=MagicMock()))

    _patch_attr("PlayerRegistryHandler", MagicMock(return_value=MagicMock()))
    _patch_attr("SettingsManager", FakeSettingsManager)

    api_server = server.ConfigAPIServer(debug=False)
    return stack, api_server


class TestServerNormalizer(unittest.TestCase):
    """Tests for API error envelope normalization."""

    def test_systeminfo_error_is_normalized(self):
        stack, api_server = build_server_under_test(systeminfo_side_effect=RuntimeError("boom failure"))
        with stack:
            with patch.dict(sys.modules, {"flask": REAL_FLASK, "flask.testing": REAL_FLASK_TESTING}):
                client = api_server.app.test_client()
                response = client.get("/api/v1/systeminfo")

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "internal_error")
        self.assertIn("data", payload)
        self.assertIn("system_error", payload["data"])
        self.assertIn("boom failure", payload["data"]["system_error"])


class TestServerSettingsRegistration(unittest.TestCase):
    """Tests for module setting registration behavior."""

    def test_registers_setup_completed_setting(self):
        stack, api_server = build_server_under_test()
        with stack:
            registered = api_server.settings_manager.registered

        self.assertIn("system.setup_completed", registered)


class TestServerMain(unittest.TestCase):
    """Tests for startup and restore control flow in main()."""

    def test_main_restore_settings_returns_zero(self):
        with patch.object(server, "setup_logging"), \
             patch.object(server, "ConfigAPIServer") as mock_server_cls, \
             patch.object(server, "parse_arguments") as mock_parse:
            mock_parse.return_value = Namespace(
                host="0.0.0.0",
                port=1081,
                debug=False,
                verbose=False,
                restore_settings=True,
                auto_restore_settings=False,
                no_waitress=False,
            )

            server_instance = MagicMock()
            server_instance.restore_settings.return_value = {"a": True, "b": False}
            mock_server_cls.return_value = server_instance

            rc = server.main()

        self.assertEqual(rc, 0)
        server_instance.restore_settings.assert_called_once()
        server_instance.run.assert_not_called()

    def test_main_auto_restore_failure_continues_to_run(self):
        with patch.object(server, "setup_logging"), \
             patch.object(server, "ConfigAPIServer") as mock_server_cls, \
             patch.object(server, "parse_arguments") as mock_parse:
            mock_parse.return_value = Namespace(
                host="0.0.0.0",
                port=1081,
                debug=False,
                verbose=False,
                restore_settings=False,
                auto_restore_settings=True,
                no_waitress=False,
            )

            server_instance = MagicMock()
            server_instance.restore_settings.side_effect = RuntimeError("restore failed")
            mock_server_cls.return_value = server_instance

            rc = server.main()

        self.assertEqual(rc, 0)
        server_instance.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
