#!/usr/bin/env python3
"""Direct tests for configurator.settings_manager."""

import unittest

from configurator.settings_manager import SettingsManager


class FakeConfigDB:
    """Minimal in-memory ConfigDB double."""

    def __init__(self):
        self.store = {}
        self.deleted = []

    def set(self, key, value):
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def get_all(self, prefix=None):
        if prefix is None:
            return dict(self.store)
        return {k: v for k, v in self.store.items() if k.startswith(prefix)}

    def delete(self, key):
        self.deleted.append(key)
        self.store.pop(key, None)
        return True


class TestSettingsManagerRegistration(unittest.TestCase):
    """Registration behavior tests."""

    def setUp(self):
        self.db = FakeConfigDB()
        self.manager = SettingsManager(self.db)

    def test_register_replaces_existing_callback(self):
        """Duplicate registration should replace callback mapping."""
        self.manager.register_setting("alpha", lambda: "v1", lambda _v: None)
        self.manager.register_setting("alpha", lambda: "v2", lambda _v: None)

        self.assertEqual(self.manager.list_registered_settings(), ["alpha"])
        self.assertTrue(self.manager.save_setting("alpha"))
        self.assertEqual(self.db.store["saved-setting.alpha"], "v2")


class TestSettingsManagerSaveRestore(unittest.TestCase):
    """Save and restore path tests."""

    def setUp(self):
        self.db = FakeConfigDB()
        self.manager = SettingsManager(self.db)

    def test_save_setting_serializes_non_string_value(self):
        """Save callback values are serialized before storage."""
        self.manager.register_setting("num", lambda: 123, lambda _v: None)

        self.assertTrue(self.manager.save_setting("num"))
        self.assertEqual(self.db.store["saved-setting.num"], "123")

    def test_save_setting_none_value_returns_false(self):
        """None callback result should not be stored."""
        self.manager.register_setting("empty", lambda: None, lambda _v: None)

        self.assertFalse(self.manager.save_setting("empty"))
        self.assertNotIn("saved-setting.empty", self.db.store)

    def test_restore_setting_passes_string_to_callback(self):
        """Restore callback should receive stored string values."""
        observed = []
        self.db.store["saved-setting.mode"] = 7
        self.manager.register_setting("mode", lambda: "x", lambda v: observed.append(v))

        self.assertTrue(self.manager.restore_setting("mode"))
        self.assertEqual(observed, ["7"])

    def test_restore_setting_callback_exception_returns_false(self):
        """Restore callback errors should be handled and reported as failure."""
        self.db.store["saved-setting.bad"] = "value"

        def explode(_value):
            raise RuntimeError("boom")

        self.manager.register_setting("bad", lambda: "ok", explode)
        self.assertFalse(self.manager.restore_setting("bad"))

    def test_unregistered_setting_returns_false(self):
        """Save/restore should fail on unknown registration."""
        self.assertFalse(self.manager.save_setting("missing"))
        self.assertFalse(self.manager.restore_setting("missing"))


class TestSettingsManagerListingAndDelete(unittest.TestCase):
    """Tests for listing and delete helper methods."""

    def setUp(self):
        self.db = FakeConfigDB()
        self.manager = SettingsManager(self.db)

    def test_list_saved_settings_skips_empty_suffix(self):
        """Malformed prefix-only keys should be ignored."""
        self.db.store["saved-setting."] = "oops"
        self.db.store["saved-setting.good"] = "value"

        saved = self.manager.list_saved_settings()

        self.assertEqual(saved, {"good": "value"})

    def test_delete_saved_setting_rejects_empty_name(self):
        """Delete should reject empty setting names."""
        self.assertFalse(self.manager.delete_saved_setting(""))

    def test_delete_saved_setting_success(self):
        """Delete should remove expected prefixed key."""
        self.assertTrue(self.manager.delete_saved_setting("alpha"))
        self.assertIn("saved-setting.alpha", self.db.deleted)


if __name__ == "__main__":
    unittest.main()
