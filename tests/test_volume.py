"""
Comprehensive regression test suite for src/volume module

Tests all volume utility functions including subprocess fallback,
configuration storage/retrieval, and caching.
"""

import unittest
from unittest.mock import patch, MagicMock
from subprocess import CalledProcessError
from io import StringIO

from configurator.volume import (
    get_cached_card_index,
    get_current_volume,
    set_volume,
    store_volume,
    restore_volume,
    is_pipewire_available,
    get_pipewire_volume,
    set_pipewire_volume,
    get_available_headphone_controls,
    get_headphone_volume,
    set_headphone_volume,
    store_headphone_volume,
    restore_headphone_volume,
    list_available_controls,
    main,
)


class TestCachedCardIndex(unittest.TestCase):
    """Tests for get_cached_card_index function"""

    def setUp(self):
        """Reset cache before each test"""
        import configurator.volume as volume_module
        volume_module._cached_card_index = None
        volume_module._cached_soundcard = None

    @patch('configurator.volume.Soundcard')
    def test_cache_initialization(self, mock_soundcard_class):
        """Test cache is initialized on first call"""
        mock_instance = MagicMock()
        mock_instance.get_hardware_index.return_value = 0
        mock_soundcard_class.return_value = mock_instance

        result = get_cached_card_index()

        self.assertEqual(result, 0)
        mock_soundcard_class.assert_called_once()
        mock_instance.get_hardware_index.assert_called_once()

    @patch('configurator.volume.Soundcard')
    def test_cache_reused(self, mock_soundcard_class):
        """Test cached value is reused on second call"""
        mock_instance = MagicMock()
        mock_instance.get_hardware_index.return_value = 1
        mock_soundcard_class.return_value = mock_instance

        result1 = get_cached_card_index()
        result2 = get_cached_card_index()

        self.assertEqual(result1, 1)
        self.assertEqual(result2, 1)
        mock_soundcard_class.assert_called_once()

    @patch('configurator.volume.Soundcard')
    def test_cache_returns_none(self, mock_soundcard_class):
        """Test when no sound card is detected"""
        mock_instance = MagicMock()
        mock_instance.get_hardware_index.return_value = None
        mock_soundcard_class.return_value = mock_instance

        result = get_cached_card_index()

        self.assertIsNone(result)


class TestGetCurrentVolume(unittest.TestCase):
    """Tests for get_current_volume function"""

    def test_get_volume_none_parameters(self):
        """Test with None parameters"""
        result = get_current_volume(None, 'Headphone')
        self.assertIsNone(result)

        result = get_current_volume(0, None)
        self.assertIsNone(result)

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_get_volume_subprocess_percentage(self, mock_subprocess):
        """Test volume retrieval via subprocess with percentage"""
        mock_subprocess.return_value = "Simple mixer control 'Headphone' [75%]"

        result = get_current_volume(0, 'Headphone')

        self.assertEqual(result, '75')

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_get_volume_subprocess_db(self, mock_subprocess):
        """Test volume retrieval via subprocess with dB"""
        mock_subprocess.return_value = "Simple mixer control 'Master' [-5.00dB]"

        result = get_current_volume(0, 'Master')

        self.assertEqual(result, '-5.00')

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_get_volume_subprocess_error(self, mock_subprocess):
        """Test subprocess error handling"""
        mock_subprocess.side_effect = CalledProcessError(1, 'amixer')

        result = get_current_volume(0, 'Headphone')

        self.assertIsNone(result)

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_get_volume_subprocess_no_match(self, mock_subprocess):
        """Test when output doesn't contain percentage or dB"""
        mock_subprocess.return_value = "unparseable output"

        result = get_current_volume(0, 'Headphone')

        self.assertIsNone(result)


class TestSetVolume(unittest.TestCase):
    """Tests for set_volume function"""

    def test_set_volume_none_parameters(self):
        """Test with None parameters"""
        result = set_volume(None, 'Headphone', '50')
        self.assertFalse(result)

        result = set_volume(0, None, '50')
        self.assertFalse(result)

    def test_set_volume_invalid_value(self):
        """Test invalid volume value"""
        result = set_volume(0, 'Headphone', 'invalid')
        self.assertFalse(result)

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_set_volume_subprocess_percentage(self, mock_subprocess):
        """Test volume setting via subprocess with percentage"""
        result = set_volume(0, 'Headphone', '75')

        self.assertTrue(result)
        mock_subprocess.assert_called_once()
        call_cmd = mock_subprocess.call_args[0][0]
        self.assertEqual(call_cmd[:4], ['amixer', '-c', '0', 'set'])
        self.assertEqual(call_cmd[-1], '75%')

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_set_volume_subprocess_db(self, mock_subprocess):
        """Test volume setting via subprocess with dB value"""
        result = set_volume(0, 'Master', '5.5')

        self.assertTrue(result)
        call_cmd = mock_subprocess.call_args[0][0]
        self.assertEqual(call_cmd[:4], ['amixer', '-c', '0', 'set'])
        self.assertEqual(call_cmd[-1], '5.5dB')

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_set_volume_subprocess_error(self, mock_subprocess):
        """Test subprocess error handling"""
        mock_subprocess.side_effect = CalledProcessError(1, 'amixer')

        result = set_volume(0, 'Headphone', '50')

        self.assertFalse(result)


class TestPipeWireAvailable(unittest.TestCase):
    """Tests for is_pipewire_available function"""

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_pipewire_available_subprocess_success(self, mock_subprocess):
        """Test PipeWire availability via subprocess"""
        mock_subprocess.return_value = "Simple mixer control 'Master'"

        result = is_pipewire_available()

        self.assertTrue(result)

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_pipewire_available_subprocess_not_found(self, mock_subprocess):
        """Test PipeWire unavailable via subprocess"""
        mock_subprocess.side_effect = CalledProcessError(1, 'amixer')

        result = is_pipewire_available()

        self.assertFalse(result)


class TestGetPipeWireVolume(unittest.TestCase):
    """Tests for get_pipewire_volume function"""

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_get_pipewire_volume_success(self, mock_subprocess):
        """Test getting PipeWire volume via subprocess"""
        mock_subprocess.return_value = "Simple mixer control 'Master' [65%]"

        result = get_pipewire_volume('Master')

        self.assertEqual(result, '65')

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_get_pipewire_volume_error(self, mock_subprocess):
        """Test PipeWire volume error handling"""
        mock_subprocess.side_effect = CalledProcessError(1, 'amixer')

        result = get_pipewire_volume('Master')

        self.assertIsNone(result)


class TestSetPipeWireVolume(unittest.TestCase):
    """Tests for set_pipewire_volume function"""

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_set_pipewire_volume_success(self, mock_subprocess):
        """Test setting PipeWire volume via subprocess"""
        result = set_pipewire_volume('Master', '70')

        self.assertTrue(result)
        mock_subprocess.assert_called_once()

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_set_pipewire_volume_error(self, mock_subprocess):
        """Test PipeWire volume error handling"""
        mock_subprocess.side_effect = CalledProcessError(1, 'amixer')

        result = set_pipewire_volume('Master', '50')

        self.assertFalse(result)


class TestHeadphoneControls(unittest.TestCase):
    """Tests for headphone control functions"""

    @patch('configurator.volume.list_available_controls')
    def test_get_available_headphone_controls_found(self, mock_list_controls):
        """Test finding available headphone controls"""
        mock_list_controls.return_value = ['Master', 'Headphone', 'Speaker']

        result = get_available_headphone_controls()

        self.assertEqual(result, ['Headphone'])

    @patch('configurator.volume.list_available_controls')
    def test_get_available_headphone_controls_not_found(self, mock_list_controls):
        """Test when headphone control not found"""
        mock_list_controls.return_value = ['Master', 'Speaker']

        result = get_available_headphone_controls()

        self.assertEqual(result, [])

    @patch('configurator.volume.list_available_controls')
    def test_get_available_headphone_controls_error(self, mock_list_controls):
        """Test error handling"""
        mock_list_controls.side_effect = Exception('Device error')

        result = get_available_headphone_controls()

        self.assertEqual(result, [])

    @patch('configurator.volume.get_available_headphone_controls')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.get_current_volume')
    def test_get_headphone_volume_success(self, mock_get_vol, mock_card, mock_get_controls):
        """Test getting headphone volume"""
        mock_get_controls.return_value = ['Headphone']
        mock_card.return_value = 0
        mock_get_vol.return_value = '85'

        result = get_headphone_volume()

        self.assertEqual(result, ('85', 'Headphone'))

    @patch('configurator.volume.get_available_headphone_controls')
    @patch('configurator.volume.get_cached_card_index')
    def test_get_headphone_volume_no_control(self, mock_card, mock_get_controls):
        """Test when no headphone control available"""
        mock_get_controls.return_value = []
        mock_card.return_value = 0

        result = get_headphone_volume()

        self.assertEqual(result, (None, None))

    @patch('configurator.volume.set_volume')
    @patch('configurator.volume.get_available_headphone_controls')
    @patch('configurator.volume.get_cached_card_index')
    def test_set_headphone_volume_success(self, mock_card, mock_get_controls, mock_set_vol):
        """Test setting headphone volume"""
        mock_get_controls.return_value = ['Headphone']
        mock_card.return_value = 0
        mock_set_vol.return_value = True

        result = set_headphone_volume('80')

        self.assertTrue(result)

    @patch('configurator.volume.get_available_headphone_controls')
    @patch('configurator.volume.get_cached_card_index')
    def test_set_headphone_volume_no_control(self, mock_card, mock_get_controls):
        """Test when no headphone control available"""
        mock_get_controls.return_value = []
        mock_card.return_value = 0

        result = set_headphone_volume('80')

        self.assertFalse(result)


class TestStoreOperations(unittest.TestCase):
    """Tests for store_volume and restore_volume functions"""

    def setUp(self):
        """Reset cache before each test in this suite."""
        import configurator.volume as volume_module
        volume_module._cached_card_index = None
        volume_module._cached_soundcard = None

    @patch('configurator.volume.get_cached_control_name')
    @patch('configurator.volume.store_headphone_volume')
    @patch('configurator.volume.is_pipewire_available')
    @patch('configurator.volume.get_current_volume')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.ConfigDB')
    def test_store_volume_success(self, mock_db_class, mock_card, mock_get_vol,
                                    mock_pipewire, mock_store_headphone, mock_control_name):
        """Test successful volume storage"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_card.return_value = 0
        mock_control_name.return_value = 'PCM'
        mock_get_vol.return_value = '100'
        mock_pipewire.return_value = False
        mock_store_headphone.return_value = False

        result = store_volume()

        self.assertTrue(result)
        mock_db.set.assert_called()

    @patch('configurator.volume.store_headphone_volume')
    @patch('configurator.volume.is_pipewire_available')
    @patch('configurator.volume.get_current_volume')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.Soundcard')
    @patch('configurator.volume.ConfigDB')
    def test_store_volume_recovers_when_cached_soundcard_missing(
        self,
        mock_db_class,
        mock_soundcard_class,
        mock_card,
        mock_get_vol,
        mock_pipewire,
        mock_store_headphone,
    ):
        """Store should recover if card index is cached but soundcard object is missing."""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_card.return_value = 0
        mock_get_vol.return_value = '42'
        mock_pipewire.return_value = False
        mock_store_headphone.return_value = False

        mock_soundcard = MagicMock()
        mock_soundcard.get_mixer_control_name.return_value = 'PCM'
        mock_soundcard_class.return_value = mock_soundcard

        import configurator.volume as volume_module
        volume_module._cached_soundcard = None

        result = store_volume()

        self.assertTrue(result)
        mock_soundcard_class.assert_called_once()
        mock_db.set.assert_any_call('system.volume.control', 'PCM')

    @patch('configurator.volume.store_headphone_volume')
    @patch('configurator.volume.get_cached_card_index')
    def test_store_volume_no_card(self, mock_card, mock_store_headphone):
        """Test storage when no card detected"""
        mock_card.return_value = None
        mock_store_headphone.return_value = False

        result = store_volume()

        self.assertFalse(result)

    @patch('configurator.volume.get_cached_control_name')
    @patch('configurator.volume.restore_headphone_volume')
    @patch('configurator.volume.is_pipewire_available')
    @patch('configurator.volume.set_volume')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.ConfigDB')
    def test_restore_volume_success(self, mock_db_class, mock_card,
                                      mock_set_vol, mock_pipewire, mock_restore_headphone,
                                      mock_control_name):
        """Test successful volume restoration"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume': '85',
            'system.volume.card': '0',
            'system.volume.control': 'PCM'
        }.get(key)
        mock_card.return_value = 0
        mock_control_name.return_value = 'PCM'
        mock_set_vol.return_value = True
        mock_pipewire.return_value = False
        mock_restore_headphone.return_value = False

        result = restore_volume()

        self.assertTrue(result)

    @patch('configurator.volume.get_cached_control_name')
    @patch('configurator.volume.restore_headphone_volume')
    @patch('configurator.volume.is_pipewire_available')
    @patch('configurator.volume.set_pipewire_volume')
    @patch('configurator.volume.set_volume')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.ConfigDB')
    def test_restore_volume_fails_when_pipewire_restore_fails(
        self,
        mock_db_class,
        mock_card,
        mock_set_vol,
        mock_set_pipewire,
        mock_pipewire,
        mock_restore_headphone,
        mock_control_name,
    ):
        """PipeWire restore failures should propagate to overall restore result."""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume': '70',
            'system.volume.card': '0',
            'system.volume.control': 'PCM',
            'system.volume.pipewire.master': '55',
            'system.volume.pipewire.capture': '60',
        }.get(key)
        mock_card.return_value = 0
        mock_control_name.return_value = 'PCM'
        mock_set_vol.return_value = True
        mock_pipewire.return_value = True
        mock_restore_headphone.return_value = False
        mock_set_pipewire.side_effect = [False, True]

        result = restore_volume()

        self.assertFalse(result)

    @patch('configurator.volume.restore_headphone_volume')
    @patch('configurator.volume.is_pipewire_available')
    @patch('configurator.volume.set_volume')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.Soundcard')
    @patch('configurator.volume.ConfigDB')
    def test_restore_volume_recovers_when_cached_soundcard_missing(
        self,
        mock_db_class,
        mock_soundcard_class,
        mock_card,
        mock_set_vol,
        mock_pipewire,
        mock_restore_headphone,
    ):
        """Restore should recover if card index is cached but soundcard object is missing."""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume': '85',
            'system.volume.card': '0',
            'system.volume.control': 'PCM'
        }.get(key)
        mock_card.return_value = 0
        mock_set_vol.return_value = True
        mock_pipewire.return_value = False
        mock_restore_headphone.return_value = False

        mock_soundcard = MagicMock()
        mock_soundcard.get_mixer_control_name.return_value = 'PCM'
        mock_soundcard_class.return_value = mock_soundcard

        import configurator.volume as volume_module
        volume_module._cached_soundcard = None

        result = restore_volume()

        self.assertTrue(result)
        mock_soundcard_class.assert_called_once()


class TestListAvailableControls(unittest.TestCase):
    """Tests for list_available_controls function"""

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_list_controls_subprocess_with_card(self, mock_subprocess):
        """Test listing controls via subprocess"""
        mock_subprocess.return_value = """Simple mixer control 'Master'
Simple mixer control 'PCM'
Simple mixer control 'Headphone'"""

        result = list_available_controls(0)

        self.assertEqual(result, ['Master', 'PCM', 'Headphone'])

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_list_controls_subprocess_default_card(self, mock_subprocess):
        """Test listing controls via subprocess without card"""
        mock_subprocess.return_value = "Simple mixer control 'Master'\nSimple mixer control 'PCM'"

        result = list_available_controls()

        self.assertEqual(result, ['Master', 'PCM'])

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_list_controls_subprocess_error(self, mock_subprocess):
        """Test subprocess error handling"""
        mock_subprocess.side_effect = CalledProcessError(1, 'amixer')

        result = list_available_controls()

        self.assertEqual(result, [])


class TestHeadphoneVolumeStorage(unittest.TestCase):
    """Tests for headphone volume storage and restoration"""

    @patch('configurator.volume.get_current_volume')
    @patch('configurator.volume.get_available_headphone_controls')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.ConfigDB')
    def test_store_headphone_volume_success(self, mock_db_class, mock_card,
                                            mock_get_controls, mock_get_current_vol):
        """Test successful headphone volume storage"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_card.return_value = 0
        mock_get_controls.return_value = ['Headphone']
        mock_get_current_vol.return_value = '90'

        result = store_headphone_volume()

        self.assertTrue(result)
        mock_db.set.assert_called()

    @patch('configurator.volume.get_available_headphone_controls')
    @patch('configurator.volume.get_cached_card_index')
    def test_store_headphone_volume_no_controls(self, mock_card, mock_get_controls):
        """Test when no headphone controls available"""
        mock_card.return_value = 0
        mock_get_controls.return_value = []

        result = store_headphone_volume()

        self.assertFalse(result)

    @patch('configurator.volume.set_volume')
    @patch('configurator.volume.get_available_headphone_controls')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.ConfigDB')
    def test_restore_headphone_volume_success(self, mock_db_class, mock_card,
                                               mock_get_controls, mock_set_vol):
        """Test successful headphone volume restoration"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume.headphone': '90',
            'system.volume.headphone.card': '0',
            'system.volume.headphone.control': 'Headphone'
        }.get(key)
        mock_card.return_value = 0
        mock_get_controls.return_value = ['Headphone']
        mock_set_vol.return_value = True

        result = restore_headphone_volume()

        self.assertTrue(result)

    @patch('configurator.volume.ConfigDB')
    def test_restore_headphone_volume_no_saved(self, mock_db_class):
        """Test when no saved headphone volume"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.return_value = None

        result = restore_headphone_volume()

        self.assertFalse(result)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error conditions"""

    def test_volume_value_conversion(self):
        """Test volume value conversion with floats"""
        result = set_volume(0, 'Headphone', '75.5')
        # Without subprocess mock it will fail, but should parse the float
        self.assertFalse(result)

    @patch('configurator.volume.get_available_headphone_controls')
    @patch('configurator.volume.get_cached_card_index')
    @patch('configurator.volume.get_current_volume')
    def test_get_headphone_volume_first_control(self, mock_get_vol, mock_card, mock_get_controls):
        """Test getting headphone volume uses first available control"""
        mock_get_controls.return_value = ['Headphone']
        mock_card.return_value = 2
        mock_get_vol.return_value = '92'

        volume, control = get_headphone_volume()

        self.assertEqual(volume, '92')
        self.assertEqual(control, 'Headphone')
        mock_get_vol.assert_called_once_with(2, 'Headphone')

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output')
    def test_get_volume_with_special_characters(self, mock_subprocess):
        """Test volume retrieval with special characters in control name"""
        mock_subprocess.return_value = "Simple mixer control 'Line In' [50%]"

        result = get_current_volume(0, 'Line In')

        self.assertEqual(result, '50')


class TestVolumeCliRegression(unittest.TestCase):
    """CLI behavior regression tests for volume main()."""

    @patch('sys.argv', ['config-volume', '--list-controls'])
    @patch('configurator.volume.list_available_controls')
    @patch('configurator.volume.get_cached_card_index')
    def test_main_list_controls_standalone(self, mock_card_index, mock_list_controls):
        """--list-controls should work as a standalone operation."""
        mock_card_index.return_value = 0
        mock_list_controls.side_effect = [['Master'], ['Master', 'Capture']]

        with patch('sys.stdout', new=StringIO()):
            result = main()

        self.assertEqual(result, 0)

    @patch('sys.argv', ['config-volume', '--list-controls', '--store'])
    def test_main_rejects_conflicting_operations(self):
        """Mutually exclusive operations should be rejected by argparse."""
        with self.assertRaises(SystemExit):
            main()

    @patch('sys.argv', ['config-volume', '--list-headphone'])
    @patch('configurator.volume.get_available_headphone_controls')
    def test_main_list_headphone_no_controls_returns_failure(self, mock_controls):
        """No headphone controls should now return non-zero for consistency."""
        mock_controls.return_value = []

        with patch('sys.stderr', new=StringIO()):
            result = main()

        self.assertEqual(result, 1)


class TestAlsaModePaths(unittest.TestCase):
    """Cover direct ALSA API branches that are not exercised by subprocess fallbacks."""

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_get_current_volume_alsa_success(self, mock_alsa):
        mixer = MagicMock()
        mixer.getvolume.return_value = [64, 64]
        mock_alsa.Mixer.return_value = mixer

        result = get_current_volume(0, 'PCM')

        self.assertEqual(result, '64')
        mock_alsa.Mixer.assert_called_once_with('PCM', cardindex=0)

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_get_current_volume_alsa_no_volume_data(self, mock_alsa):
        mixer = MagicMock()
        mixer.getvolume.return_value = []
        mock_alsa.Mixer.return_value = mixer

        self.assertIsNone(get_current_volume(1, 'PCM'))

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_get_current_volume_alsa_exception(self, mock_alsa):
        mock_alsa.Mixer.side_effect = Exception('alsa failure')
        self.assertIsNone(get_current_volume(1, 'PCM'))

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_set_volume_alsa_success_clamps_to_max(self, mock_alsa):
        mixer = MagicMock()
        mock_alsa.Mixer.return_value = mixer

        self.assertTrue(set_volume(0, 'PCM', '140'))
        mixer.setvolume.assert_called_once_with(100)

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_set_volume_alsa_invalid_value(self, mock_alsa):
        mock_alsa.Mixer.return_value = MagicMock()
        self.assertFalse(set_volume(0, 'PCM', 'not-a-number'))

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_set_volume_alsa_exception(self, mock_alsa):
        mock_alsa.Mixer.side_effect = Exception('alsa set fail')
        self.assertFalse(set_volume(0, 'PCM', '50'))

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_pipewire_available_alsa_true(self, mock_alsa):
        mock_alsa.Mixer.return_value = MagicMock()
        self.assertTrue(is_pipewire_available())

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_pipewire_available_alsa_false(self, mock_alsa):
        mock_alsa.Mixer.side_effect = Exception('missing')
        self.assertFalse(is_pipewire_available())

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_get_pipewire_volume_alsa_capture_uses_id0(self, mock_alsa):
        mixer = MagicMock()
        mixer.getvolume.return_value = [33]
        mock_alsa.Mixer.return_value = mixer

        self.assertEqual(get_pipewire_volume('Capture'), '33')
        mock_alsa.Mixer.assert_called_once_with('Capture', id=0, cardindex=-1)

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_get_pipewire_volume_alsa_no_data(self, mock_alsa):
        mixer = MagicMock()
        mixer.getvolume.return_value = []
        mock_alsa.Mixer.return_value = mixer

        self.assertIsNone(get_pipewire_volume('Master'))

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_get_pipewire_volume_alsa_exception(self, mock_alsa):
        mock_alsa.Mixer.side_effect = Exception('pw read fail')
        self.assertIsNone(get_pipewire_volume('Master'))

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_set_pipewire_volume_alsa_success_clamps(self, mock_alsa):
        mixer = MagicMock()
        mock_alsa.Mixer.return_value = mixer

        self.assertTrue(set_pipewire_volume('Capture', '-20'))
        mixer.setvolume.assert_called_once_with(0)
        mock_alsa.Mixer.assert_called_once_with('Capture', id=0, cardindex=-1)

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_set_pipewire_volume_alsa_invalid_value(self, mock_alsa):
        mock_alsa.Mixer.return_value = MagicMock()
        self.assertFalse(set_pipewire_volume('Master', 'oops'))

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_set_pipewire_volume_alsa_exception(self, mock_alsa):
        mock_alsa.Mixer.side_effect = Exception('pw set fail')
        self.assertFalse(set_pipewire_volume('Master', '50'))

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_list_available_controls_alsa_with_card(self, mock_alsa):
        mock_alsa.mixers.return_value = ['Master', 'PCM']
        self.assertEqual(list_available_controls(2), ['Master', 'PCM'])
        mock_alsa.mixers.assert_called_once_with(cardindex=2)

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_list_available_controls_alsa_default(self, mock_alsa):
        mock_alsa.mixers.return_value = ['Master']
        self.assertEqual(list_available_controls(), ['Master'])
        mock_alsa.mixers.assert_called_once_with()

    @patch('configurator.volume.alsa_available', True)
    @patch('configurator.volume.alsaaudio', create=True)
    def test_list_available_controls_alsa_exception(self, mock_alsa):
        mock_alsa.mixers.side_effect = Exception('mixers fail')
        self.assertEqual(list_available_controls(1), [])


class TestHeadphoneBranchCoverage(unittest.TestCase):
    """Add missing error-path tests for headphone helpers."""

    @patch('configurator.volume.get_cached_card_index', return_value=None)
    def test_get_headphone_volume_no_card(self, _mock_card):
        self.assertEqual(get_headphone_volume(), (None, None))

    @patch('configurator.volume.get_cached_card_index', return_value=0)
    @patch('configurator.volume.get_available_headphone_controls', return_value=['Headphone'])
    @patch('configurator.volume.get_current_volume', return_value=None)
    def test_get_headphone_volume_get_current_fails(self, _mock_get, _mock_controls, _mock_card):
        self.assertEqual(get_headphone_volume(), (None, None))

    @patch('configurator.volume.get_cached_card_index', return_value=None)
    def test_set_headphone_volume_no_card(self, _mock_card):
        self.assertFalse(set_headphone_volume('50'))

    @patch('configurator.volume.get_cached_card_index', return_value=0)
    @patch('configurator.volume.get_available_headphone_controls', return_value=['Headphone'])
    @patch('configurator.volume.set_volume', return_value=False)
    def test_set_headphone_volume_set_fails(self, _mock_set, _mock_controls, _mock_card):
        self.assertFalse(set_headphone_volume('50'))

    @patch('configurator.volume.get_cached_card_index', return_value=0)
    @patch('configurator.volume.get_available_headphone_controls', return_value=['Headphone'])
    @patch('configurator.volume.get_current_volume', return_value=None)
    def test_store_headphone_volume_no_current_volume(self, _mock_get, _mock_controls, _mock_card):
        self.assertFalse(store_headphone_volume())

    @patch('configurator.volume.ConfigDB')
    @patch('configurator.volume.get_cached_card_index', return_value=None)
    def test_restore_headphone_volume_no_card(self, _mock_card, mock_db_class):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume.headphone': '40',
            'system.volume.headphone.card': '0',
            'system.volume.headphone.control': 'Headphone',
        }.get(key)
        self.assertFalse(restore_headphone_volume())

    @patch('configurator.volume.ConfigDB')
    @patch('configurator.volume.get_cached_card_index', return_value=0)
    @patch('configurator.volume.get_available_headphone_controls', return_value=[])
    def test_restore_headphone_volume_no_controls(self, _mock_controls, _mock_card, mock_db_class):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume.headphone': '40',
            'system.volume.headphone.card': '0',
            'system.volume.headphone.control': 'Headphone',
        }.get(key)
        self.assertFalse(restore_headphone_volume())

    @patch('configurator.volume.ConfigDB')
    @patch('configurator.volume.get_cached_card_index', return_value=0)
    @patch('configurator.volume.get_available_headphone_controls', return_value=['Headphone'])
    @patch('configurator.volume.set_volume', return_value=False)
    def test_restore_headphone_volume_set_fails(self, _mock_set, _mock_controls, _mock_card, mock_db_class):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume.headphone': '40',
            'system.volume.headphone.card': '0',
            'system.volume.headphone.control': 'Headphone',
        }.get(key)
        self.assertFalse(restore_headphone_volume())


class TestVolumeCliAdditionalBranches(unittest.TestCase):
    """Exercise remaining CLI operations and return-code branches."""

    @patch('sys.argv', ['config-volume', '--get-headphone'])
    @patch('configurator.volume.get_headphone_volume', return_value=('55', 'Headphone'))
    def test_main_get_headphone_success(self, _mock_get):
        with patch('sys.stdout', new=StringIO()):
            self.assertEqual(main(), 0)

    @patch('sys.argv', ['config-volume', '--get-headphone'])
    @patch('configurator.volume.get_headphone_volume', return_value=(None, None))
    def test_main_get_headphone_failure(self, _mock_get):
        with patch('sys.stderr', new=StringIO()):
            self.assertEqual(main(), 1)

    @patch('sys.argv', ['config-volume', '--set-headphone', '66'])
    @patch('configurator.volume.set_headphone_volume', return_value=True)
    def test_main_set_headphone_success(self, _mock_set):
        with patch('sys.stdout', new=StringIO()):
            self.assertEqual(main(), 0)

    @patch('sys.argv', ['config-volume', '--set-headphone', '66'])
    @patch('configurator.volume.set_headphone_volume', return_value=False)
    def test_main_set_headphone_failure(self, _mock_set):
        with patch('sys.stderr', new=StringIO()):
            self.assertEqual(main(), 1)

    @patch('sys.argv', ['config-volume', '--store-headphone'])
    @patch('configurator.volume.store_headphone_volume', return_value=True)
    def test_main_store_headphone_success(self, _mock_store):
        with patch('sys.stdout', new=StringIO()):
            self.assertEqual(main(), 0)

    @patch('sys.argv', ['config-volume', '--store-headphone'])
    @patch('configurator.volume.store_headphone_volume', return_value=False)
    def test_main_store_headphone_failure(self, _mock_store):
        with patch('sys.stderr', new=StringIO()):
            self.assertEqual(main(), 1)

    @patch('sys.argv', ['config-volume', '--restore-headphone'])
    @patch('configurator.volume.restore_headphone_volume', return_value=True)
    def test_main_restore_headphone_success(self, _mock_restore):
        with patch('sys.stdout', new=StringIO()):
            self.assertEqual(main(), 0)

    @patch('sys.argv', ['config-volume', '--restore-headphone'])
    @patch('configurator.volume.restore_headphone_volume', return_value=False)
    def test_main_restore_headphone_failure(self, _mock_restore):
        with patch('sys.stderr', new=StringIO()):
            self.assertEqual(main(), 1)

    @patch('sys.argv', ['config-volume', '--store'])
    @patch('configurator.volume.store_volume', return_value=True)
    def test_main_store_success(self, _mock_store):
        self.assertEqual(main(), 0)

    @patch('sys.argv', ['config-volume', '--store'])
    @patch('configurator.volume.store_volume', return_value=False)
    def test_main_store_failure(self, _mock_store):
        self.assertEqual(main(), 1)

    @patch('sys.argv', ['config-volume', '--restore'])
    @patch('configurator.volume.restore_volume', return_value=True)
    def test_main_restore_success(self, _mock_restore):
        self.assertEqual(main(), 0)

    @patch('sys.argv', ['config-volume', '--restore'])
    @patch('configurator.volume.restore_volume', return_value=False)
    def test_main_restore_failure(self, _mock_restore):
        self.assertEqual(main(), 1)

    @patch('sys.argv', ['config-volume', '--store', '--verbose'])
    @patch('configurator.volume.store_volume', return_value=True)
    @patch('configurator.volume.logging.getLogger')
    def test_main_verbose_sets_debug_level(self, mock_get_logger, _mock_store):
        logger = MagicMock()
        mock_get_logger.return_value = logger
        self.assertEqual(main(), 0)
        logger.setLevel.assert_called_once()


class TestVolumeRemainingBranchCoverage(unittest.TestCase):
    """Additional targeted tests for remaining uncovered branches."""

    @patch('configurator.volume.get_cached_control_name', return_value='PCM')
    @patch('configurator.volume.store_headphone_volume', return_value=True)
    @patch('configurator.volume.is_pipewire_available', return_value=True)
    @patch('configurator.volume.get_pipewire_volume', side_effect=[None, None])
    @patch('configurator.volume.get_current_volume', return_value=None)
    @patch('configurator.volume.get_cached_card_index', return_value=0)
    def test_store_volume_handles_missing_physical_and_pipewire_volumes(
        self,
        _mock_card,
        _mock_get_vol,
        _mock_pipewire_get,
        _mock_pipewire_available,
        _mock_store_hp,
        _mock_control,
    ):
        self.assertFalse(store_volume())

    @patch('configurator.volume.get_cached_card_index', side_effect=Exception('boom'))
    def test_store_volume_top_level_exception(self, _mock_card):
        self.assertFalse(store_volume())

    @patch('configurator.volume.restore_headphone_volume', return_value=True)
    @patch('configurator.volume.is_pipewire_available', return_value=True)
    @patch('configurator.volume.get_cached_control_name', return_value='PCM')
    @patch('configurator.volume.set_volume', return_value=True)
    @patch('configurator.volume.get_cached_card_index', return_value=1)
    @patch('configurator.volume.ConfigDB')
    def test_restore_volume_handles_missing_db_and_pipewire_values(
        self,
        mock_db_class,
        _mock_card,
        _mock_set_vol,
        _mock_control,
        _mock_pipewire,
        _mock_restore_hp,
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume': None,
            'system.volume.card': None,
            'system.volume.control': None,
            'system.volume.pipewire.master': None,
            'system.volume.pipewire.capture': None,
        }.get(key)

        self.assertFalse(restore_volume())

    @patch('configurator.volume.ConfigDB', side_effect=Exception('db exploded'))
    def test_restore_volume_top_level_exception(self, _mock_db):
        self.assertFalse(restore_volume())

    @patch('configurator.volume.alsa_available', False)
    @patch('configurator.volume.subprocess.check_output', return_value='unparseable output')
    def test_get_pipewire_volume_no_percentage_match(self, _mock_subprocess):
        self.assertIsNone(get_pipewire_volume('Master'))

    @patch('configurator.volume.alsa_available', False)
    def test_set_pipewire_volume_invalid_value_subprocess(self):
        self.assertFalse(set_pipewire_volume('Master', 'not-a-number'))

    @patch('configurator.volume.get_cached_card_index', return_value=None)
    def test_get_available_headphone_controls_no_card(self, _mock_card):
        self.assertEqual(get_available_headphone_controls(), [])

    @patch('configurator.volume.ConfigDB')
    @patch('configurator.volume.get_cached_card_index', return_value=1)
    @patch('configurator.volume.get_available_headphone_controls', return_value=['Headphone'])
    @patch('configurator.volume.set_volume', return_value=True)
    def test_restore_headphone_volume_warns_on_configuration_change(
        self,
        _mock_set,
        _mock_controls,
        _mock_card,
        mock_db_class,
    ):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get.side_effect = lambda key: {
            'system.volume.headphone': '75',
            'system.volume.headphone.card': '0',
            'system.volume.headphone.control': 'Speaker',
        }.get(key)
        self.assertTrue(restore_headphone_volume())

    @patch('configurator.volume.get_cached_card_index', side_effect=Exception('hp get fail'))
    def test_get_headphone_volume_exception_path(self, _mock_card):
        self.assertEqual(get_headphone_volume(), (None, None))

    @patch('configurator.volume.get_cached_card_index', side_effect=Exception('hp set fail'))
    def test_set_headphone_volume_exception_path(self, _mock_card):
        self.assertFalse(set_headphone_volume('50'))

    @patch('configurator.volume.get_cached_card_index', side_effect=Exception('hp store fail'))
    def test_store_headphone_volume_exception_path(self, _mock_card):
        self.assertFalse(store_headphone_volume())

    @patch('configurator.volume.ConfigDB', side_effect=Exception('hp restore fail'))
    def test_restore_headphone_volume_exception_path(self, _mock_db):
        self.assertFalse(restore_headphone_volume())

    @patch('sys.argv', ['config-volume', '--list-headphone'])
    @patch('configurator.volume.get_available_headphone_controls', return_value=['Headphone'])
    def test_main_list_headphone_success(self, _mock_controls):
        with patch('sys.stdout', new=StringIO()):
            self.assertEqual(main(), 0)


if __name__ == '__main__':
    unittest.main()
