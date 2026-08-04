#!/usr/bin/env python3
"""
Regression tests for ble_provisioning module

Tests the BLE WiFi provisioning server functionality for:
- Device identity and network status retrieval
- JSON serialization of responses
- WiFi scan and connection handling
- BLE control message parsing
- Network connectivity checks
- CLI argument parsing
- Logging setup
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os
import importlib
import types

# Mock the bless module and other dependencies before importing anything from src
sys.modules['bless'] = MagicMock()
sys.modules['bless.backends'] = MagicMock()
sys.modules['bless.backends.bluezdbus'] = MagicMock()
sys.modules['bless.backends.bluezdbus.server'] = MagicMock()
sys.modules['bless.backends.bluezdbus.characteristic'] = MagicMock()
sys.modules['bless.backends.attribute'] = MagicMock()
sys.modules['bless.backends.characteristic'] = MagicMock()

sys.modules['netifaces'] = MagicMock()

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the src modules that have external dependencies
sys.modules['src.wifi'] = MagicMock()
sys.modules['src.network'] = MagicMock()

from configurator.ble_provisioning import (  # noqa: E402
    BLEProvisioningServer,
    CHAR_BLE_CONTROL,
    CHAR_DEVICE_IDENTITY,
    CHAR_NETWORK_STATUS,
    CHAR_WIFI_CONNECT,
    CHAR_WIFI_CONNECT_STATUS,
    CHAR_WIFI_SCAN_RESULTS,
    CHAR_WIFI_SCAN_TRIGGER,
    MAX_SCAN_RESULTS,
    SERVICE_UUID,
    has_network_connectivity,
    setup_logging,
    main,
)


def test_bless_symbol_fallback_on_missing_attributes():
    """Missing bless symbols should trigger module fallback without crashing."""
    import configurator.ble_provisioning as ble_provisioning

    real_import_module = importlib.import_module

    def _fake_import_module(name, package=None):
        if name in {
            "bless.backends.attribute",
            "bless.backends.characteristic",
            "bless.backends.bluezdbus.server",
        }:
            # Deliberately provide modules without expected attributes.
            return types.SimpleNamespace()
        return real_import_module(name, package)

    with patch(
        "configurator.ble_provisioning.importlib.import_module",
        side_effect=_fake_import_module,
    ):
        reloaded = importlib.reload(ble_provisioning)

    assert reloaded.GATTAttributePermissions is reloaded.Any
    assert reloaded.GATTCharacteristicProperties is reloaded.Any
    assert reloaded.BlessServer is reloaded.Any

    # Restore regular module state for subsequent tests.
    importlib.reload(ble_provisioning)


class TestBLEProvisioningServer:
    """Test cases for BLEProvisioningServer class"""

    @pytest.fixture
    def server(self):
        """Fixture providing a BLEProvisioningServer instance"""
        return BLEProvisioningServer()

    def test_init_creates_instance(self, server):
        """Test that BLEProvisioningServer initializes correctly"""
        assert server.server is None
        assert server.loop is None
        assert server._scan_results == []
        assert server._connect_status == {
            "state": "idle",
            "ssid": "",
            "error": "",
        }
        assert server._shutdown_requested is False

    @patch("configurator.ble_provisioning.platform.node")
    def test_get_hostname(self, mock_node, server):
        """Test hostname retrieval"""
        mock_node.return_value = "hifiberry-test"

        hostname = server._get_hostname()

        assert hostname == "hifiberry-test"
        mock_node.assert_called_once()

    @patch("configurator.ble_provisioning.platform.node")
    def test_get_device_identity_success(self, mock_node, server):
        """Test device identity retrieval with all components"""
        mock_node.return_value = "hifiberry-01"

        with patch("configurator.ble_provisioning.sys"):
            identity_bytes = server._get_device_identity()

        data = json.loads(identity_bytes.decode("utf-8"))
        assert data["hostname"] == "hifiberry-01"
        assert "model" in data
        assert "version" in data

    @patch("configurator.ble_provisioning.platform.node")
    def test_get_device_identity_minimal(self, mock_node, server):
        """Test device identity with missing optional components"""
        mock_node.return_value = "test-host"

        # Mock the version import to return nothing
        with patch.dict('sys.modules', {'configurator._version': None}):
            identity_bytes = server._get_device_identity()

        data = json.loads(identity_bytes.decode("utf-8"))
        assert data["hostname"] == "test-host"
        assert "model" in data
        assert "version" in data

    @patch("configurator.ble_provisioning.network.get_network_config")
    @patch("configurator.ble_provisioning.wifi.get_current_connection")
    @patch("configurator.ble_provisioning.platform.node")
    def test_get_network_status_no_interfaces(
        self, mock_node, mock_get_conn, mock_get_config, server
    ):
        """Test network status with no interfaces"""
        mock_node.return_value = "test-host"
        mock_get_config.return_value = {
            "hostname": "test-host",
            "interfaces": []
        }

        status_bytes = server._get_network_status()

        data = json.loads(status_bytes.decode("utf-8"))
        assert data["wifi_connected"] is False
        assert data["eth_connected"] is False
        assert data["hostname"] == "test-host"

    @patch("configurator.ble_provisioning.network.get_network_config")
    @patch("configurator.ble_provisioning.wifi.get_current_connection")
    @patch("configurator.ble_provisioning.platform.node")
    def test_get_network_status_wifi_connected(
        self, mock_node, mock_get_conn, mock_get_config, server
    ):
        """Test network status with WiFi connected"""
        mock_node.return_value = "test-host"
        mock_get_config.return_value = {
            "hostname": "test-host",
            "interfaces": [
                {
                    "name": "wlan0",
                    "type": "wireless",
                    "ipv4": "192.168.1.100"
                }
            ]
        }
        mock_get_conn.return_value = {"ssid": "TestNetwork"}

        status_bytes = server._get_network_status()

        data = json.loads(status_bytes.decode("utf-8"))
        assert data["wifi_connected"] is True
        assert data["wifi_ip"] == "192.168.1.100"
        assert data["wifi_ssid"] == "TestNetwork"

    @patch("configurator.ble_provisioning.network.get_network_config")
    @patch("configurator.ble_provisioning.wifi.get_current_connection")
    @patch("configurator.ble_provisioning.platform.node")
    def test_get_network_status_eth_connected(
        self, mock_node, mock_get_conn, mock_get_config, server
    ):
        """Test network status with Ethernet connected"""
        mock_node.return_value = "test-host"
        mock_get_config.return_value = {
            "hostname": "test-host",
            "interfaces": [
                {
                    "name": "eth0",
                    "type": "wired",
                    "ipv4": "10.0.0.50"
                }
            ]
        }

        status_bytes = server._get_network_status()

        data = json.loads(status_bytes.decode("utf-8"))
        assert data["eth_connected"] is True
        assert data["eth_ip"] == "10.0.0.50"

    @patch("configurator.ble_provisioning.network.get_network_config")
    @patch("configurator.ble_provisioning.platform.node")
    def test_get_network_status_ignores_unknown_interface_type(
        self, mock_node, mock_get_config, server
    ):
        """Only explicit wired interfaces should set eth_* status fields."""
        mock_node.return_value = "test-host"
        mock_get_config.return_value = {
            "hostname": "test-host",
            "interfaces": [
                {
                    "name": "br0",
                    "type": "bridge",
                    "ipv4": "10.10.10.10",
                }
            ],
        }

        status_bytes = server._get_network_status()

        data = json.loads(status_bytes.decode("utf-8"))
        assert data["eth_connected"] is False
        assert data["eth_ip"] == ""

    @patch("configurator.ble_provisioning.network.get_network_config")
    def test_get_network_status_error_handling(self, mock_get_config, server):
        """Test network status with error retrieving config"""
        mock_get_config.side_effect = IOError("Connection error")

        status_bytes = server._get_network_status()

        data = json.loads(status_bytes.decode("utf-8"))
        # When there's an error, network status should still return valid structure
        assert data["wifi_connected"] is False
        assert data["eth_connected"] is False

    def test_get_scan_results_bytes_empty(self, server):
        """Test scan results bytes with empty results"""
        server._scan_results = []

        results_bytes = server._get_scan_results_bytes()

        data = json.loads(results_bytes.decode("utf-8"))
        assert data == []

    def test_get_scan_results_bytes_with_networks(self, server):
        """Test scan results bytes with WiFi networks"""
        server._scan_results = [
            {"ssid": "Network1", "signal": -50, "security": "WPA2"},
            {"ssid": "Network2", "signal": -70, "security": "Open"},
        ]

        results_bytes = server._get_scan_results_bytes()

        data = json.loads(results_bytes.decode("utf-8"))
        assert len(data) == 2
        assert data[0]["ssid"] == "Network1"
        assert data[1]["signal"] == -70

    def test_get_connect_status_bytes_idle(self, server):
        """Test connect status bytes in idle state"""
        status_bytes = server._get_connect_status_bytes()

        data = json.loads(status_bytes.decode("utf-8"))
        assert data["state"] == "idle"
        assert data["ssid"] == ""
        assert data["error"] == ""

    def test_get_connect_status_bytes_connecting(self, server):
        """Test connect status bytes while connecting"""
        server._connect_status = {
            "state": "connecting",
            "ssid": "MyNetwork",
            "error": ""
        }

        status_bytes = server._get_connect_status_bytes()

        data = json.loads(status_bytes.decode("utf-8"))
        assert data["state"] == "connecting"
        assert data["ssid"] == "MyNetwork"

    def test_handle_scan_trigger_with_trigger_byte(self, server):
        """Test WiFi scan trigger with 0xFF byte"""
        with patch("asyncio.ensure_future") as mock_future:
            mock_future.side_effect = lambda coro: coro.close()
            server._handle_scan_trigger(bytearray(b"\xFF"))

        # Should schedule the scan
        mock_future.assert_called_once()

    def test_handle_scan_trigger_with_empty_value(self, server):
        """Test WiFi scan trigger with empty value"""
        with patch("asyncio.ensure_future") as mock_future:
            server._handle_scan_trigger(bytearray(b""))

        # Should not schedule the scan
        mock_future.assert_not_called()

    def test_handle_wifi_connect_valid_payload(self, server):
        """Test WiFi connect with valid JSON payload"""
        payload = json.dumps({
            "ssid": "TestNetwork",
            "passphrase": "password123"
        }).encode("utf-8")

        with patch("asyncio.ensure_future") as mock_future:
            mock_future.side_effect = lambda coro: coro.close()
            server._handle_wifi_connect(bytearray(payload))

        assert server._connect_status["state"] == "connecting"
        assert server._connect_status["ssid"] == "TestNetwork"
        mock_future.assert_called_once()

    def test_handle_wifi_connect_empty_ssid(self, server):
        """Test WiFi connect with empty SSID"""
        payload = json.dumps({
            "ssid": "",
            "passphrase": "password"
        }).encode("utf-8")

        with patch("asyncio.ensure_future") as mock_future:
            server._handle_wifi_connect(bytearray(payload))

        # Should not attempt connection
        mock_future.assert_not_called()

    def test_handle_wifi_connect_invalid_json(self, server):
        """Test WiFi connect with invalid JSON"""
        invalid_json = b"{ invalid json"

        server._handle_wifi_connect(bytearray(invalid_json))

        assert server._connect_status["state"] == "failed"
        assert server._connect_status["error"] != ""

    def test_handle_ble_control_stop_ble(self, server):
        """Test BLE control stop command"""
        payload = json.dumps({
            "action": "stop_ble"
        }).encode("utf-8")

        mock_loop = MagicMock()
        server.loop = mock_loop

        server._handle_ble_control(bytearray(payload))

        assert server._shutdown_requested is True
        mock_loop.call_soon_threadsafe.assert_called_once()

    def test_handle_ble_control_unknown_action(self, server):
        """Test BLE control with unknown action"""
        payload = json.dumps({
            "action": "unknown_action"
        }).encode("utf-8")

        server._handle_ble_control(bytearray(payload))

        # Should not set shutdown flag
        assert server._shutdown_requested is False

    def test_handle_ble_control_invalid_json(self, server):
        """Test BLE control with invalid JSON"""
        invalid_json = b"{ invalid }"

        # Should not raise exception
        server._handle_ble_control(bytearray(invalid_json))
        assert server._shutdown_requested is False

    def test_on_read_dispatches_all_characteristics(self, server):
        """Read callback should route to the correct payload helpers."""
        with patch.object(server, "_get_device_identity", return_value=b"id") as mock_id, \
            patch.object(server, "_get_network_status", return_value=b"net") as mock_net, \
            patch.object(server, "_get_scan_results_bytes", return_value=b"scan") as mock_scan, \
            patch.object(server, "_get_connect_status_bytes", return_value=b"conn") as mock_conn:
            assert server._on_read(types.SimpleNamespace(uuid=CHAR_DEVICE_IDENTITY)) == bytearray(b"id")
            assert server._on_read(types.SimpleNamespace(uuid=CHAR_NETWORK_STATUS)) == bytearray(b"net")
            assert server._on_read(types.SimpleNamespace(uuid=CHAR_WIFI_SCAN_RESULTS)) == bytearray(b"scan")
            assert server._on_read(types.SimpleNamespace(uuid=CHAR_WIFI_CONNECT_STATUS)) == bytearray(b"conn")
            assert server._on_read(types.SimpleNamespace(uuid="00000000-0000-0000-0000-000000000000")) == bytearray(b"")

        mock_id.assert_called_once()
        mock_net.assert_called_once()
        mock_scan.assert_called_once()
        mock_conn.assert_called_once()

    def test_on_write_dispatches_to_handlers(self, server):
        """Write callback should route writes by characteristic UUID."""
        value = bytearray(b"payload")
        with patch.object(server, "_handle_scan_trigger") as mock_scan, \
            patch.object(server, "_handle_wifi_connect") as mock_connect, \
            patch.object(server, "_handle_ble_control") as mock_control:
            server._on_write(types.SimpleNamespace(uuid=CHAR_WIFI_SCAN_TRIGGER), value)
            server._on_write(types.SimpleNamespace(uuid=CHAR_WIFI_CONNECT), value)
            server._on_write(types.SimpleNamespace(uuid=CHAR_BLE_CONTROL), value)
            server._on_write(types.SimpleNamespace(uuid="00000000-0000-0000-0000-000000000000"), value)

        mock_scan.assert_called_once_with(value)
        mock_connect.assert_called_once_with(value)
        mock_control.assert_called_once_with(value)

    @pytest.mark.asyncio
    async def test_do_wifi_scan_success_updates_characteristic(self, server):
        """Successful scans should cache capped results and notify clients."""
        networks = [
            {"ssid": f"Net-{i}", "signal": -40 - i, "security": "WPA2"}
            for i in range(MAX_SCAN_RESULTS + 3)
        ]
        char = MagicMock()
        server.server = MagicMock()
        server.server.get_characteristic.return_value = char

        with patch("configurator.ble_provisioning.asyncio.to_thread", new=AsyncMock(return_value=networks)):
            await server._do_wifi_scan()

        assert len(server._scan_results) == MAX_SCAN_RESULTS
        assert server._scan_results[0]["ssid"] == "Net-0"
        server.server.get_characteristic.assert_called_with(CHAR_WIFI_SCAN_RESULTS)
        server.server.update_value.assert_called_once_with(SERVICE_UUID, CHAR_WIFI_SCAN_RESULTS)
        assert isinstance(char.value, bytearray)

    @pytest.mark.asyncio
    async def test_do_wifi_scan_failure_clears_results(self, server):
        """Scan exceptions should clear cached scan results."""
        server._scan_results = [{"ssid": "old", "signal": -99, "security": "WEP"}]

        with patch(
            "configurator.ble_provisioning.asyncio.to_thread",
            new=AsyncMock(side_effect=RuntimeError("scan failed")),
        ):
            await server._do_wifi_scan()

        assert server._scan_results == []

    @pytest.mark.asyncio
    async def test_do_wifi_connect_success_updates_network_status(self, server):
        """Successful WiFi connect should transition to connected and notify."""
        net_char = MagicMock()
        server.server = MagicMock()
        server.server.get_characteristic.return_value = net_char

        with patch("configurator.ble_provisioning.asyncio.to_thread", new=AsyncMock(return_value=True)), \
            patch.object(server, "_get_network_status", return_value=b"{}"), \
            patch.object(server, "_notify_connect_status") as mock_notify:
            await server._do_wifi_connect("TestWiFi", "secret")

        assert server._connect_status == {"state": "connected", "ssid": "TestWiFi", "error": ""}
        mock_notify.assert_called_once()
        server.server.get_characteristic.assert_called_with(CHAR_NETWORK_STATUS)
        server.server.update_value.assert_called_once_with(SERVICE_UUID, CHAR_NETWORK_STATUS)
        assert isinstance(net_char.value, bytearray)

    @pytest.mark.asyncio
    async def test_do_wifi_connect_failed_result(self, server):
        """A false backend result should become a failed state."""
        with patch("configurator.ble_provisioning.asyncio.to_thread", new=AsyncMock(return_value=False)), \
            patch.object(server, "_notify_connect_status") as mock_notify:
            await server._do_wifi_connect("TestWiFi", "secret")

        assert server._connect_status["state"] == "failed"
        assert server._connect_status["error"] == "Connection failed"
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_do_wifi_connect_exception(self, server):
        """Backend exceptions should propagate as failed connect status."""
        with patch(
            "configurator.ble_provisioning.asyncio.to_thread",
            new=AsyncMock(side_effect=OSError("nmcli failure")),
        ), patch.object(server, "_notify_connect_status") as mock_notify:
            await server._do_wifi_connect("TestWiFi", None)

        assert server._connect_status["state"] == "failed"
        assert server._connect_status["error"] == "nmcli failure"
        mock_notify.assert_called_once()

    def test_notify_connect_status_no_server_is_noop(self, server):
        """Notification helper should safely no-op when no server exists."""
        server.server = None
        server._notify_connect_status()

    def test_notify_connect_status_updates_characteristic(self, server):
        """Notification helper should update and publish status characteristic."""
        status_char = MagicMock()
        server.server = MagicMock()
        server.server.get_characteristic.return_value = status_char

        server._notify_connect_status()

        server.server.get_characteristic.assert_called_once_with(CHAR_WIFI_CONNECT_STATUS)
        server.server.update_value.assert_called_once_with(SERVICE_UUID, CHAR_WIFI_CONNECT_STATUS)
        assert isinstance(status_char.value, bytearray)

    @pytest.mark.asyncio
    async def test_start_registers_services_and_characteristics(self, server):
        """Server start should configure callbacks, GATT service, and characteristics."""
        fake_server = MagicMock()
        fake_server.add_new_service = AsyncMock()
        fake_server.add_new_characteristic = AsyncMock()
        fake_server.start = AsyncMock()

        fake_props = types.SimpleNamespace(read=0x01, notify=0x02, write=0x04)
        fake_perms = types.SimpleNamespace(readable=0x01, writeable=0x02)

        with patch("configurator.ble_provisioning.BlessServer", return_value=fake_server), \
            patch("configurator.ble_provisioning.asyncio.get_event_loop", return_value=MagicMock()), \
            patch("configurator.ble_provisioning.GATTCharacteristicProperties", fake_props), \
            patch("configurator.ble_provisioning.GATTAttributePermissions", fake_perms), \
            patch.object(server, "_get_hostname", return_value="x" * 64), \
            patch.object(server, "_get_device_identity", return_value=b"id"), \
            patch.object(server, "_get_network_status", return_value=b"net"), \
            patch.object(server, "_get_connect_status_bytes", return_value=b"conn"):
            await server.start()

        assert server.server is fake_server
        assert fake_server.read_request_func == server._on_read
        assert fake_server.write_request_func == server._on_write
        fake_server.add_new_service.assert_called_once_with(SERVICE_UUID)
        assert fake_server.add_new_characteristic.await_count == 7
        fake_server.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_raises_when_server_init_fails(self, server):
        """Start should fail fast when BlessServer initialization fails."""
        with patch("configurator.ble_provisioning.BlessServer", return_value=None), \
            patch("configurator.ble_provisioning.asyncio.get_event_loop", return_value=MagicMock()):
            with pytest.raises(RuntimeError, match="Failed to initialize BLE server"):
                await server.start()

    @pytest.mark.asyncio
    async def test_stop_shuts_down_server_and_clears_reference(self, server):
        """Stop should await backend shutdown and clear server handle."""
        backend = MagicMock()
        backend.stop = AsyncMock()
        server.server = backend
        server._shutdown_requested = True

        await server.stop()

        backend.stop.assert_awaited_once()
        assert server.server is None

    @pytest.mark.asyncio
    async def test_stop_no_server_is_noop(self, server):
        """Stop should no-op when no backend server exists."""
        server.server = None
        await server.stop()


class TestNetworkConnectivity:
    """Test cases for network connectivity check"""

    @patch("configurator.ble_provisioning.network.list_physical_interfaces")
    def test_has_network_connectivity_true(self, mock_interfaces):
        """Test network connectivity detection when connected"""
        mock_interfaces.return_value = [
            {"name": "eth0", "ipv4": "192.168.1.100"},
            {"name": "wlan0", "ipv4": None}
        ]

        result = has_network_connectivity()

        assert result is True

    @patch("configurator.ble_provisioning.network.list_physical_interfaces")
    def test_has_network_connectivity_false(self, mock_interfaces):
        """Test network connectivity detection when not connected"""
        mock_interfaces.return_value = [
            {"name": "eth0", "ipv4": None},
            {"name": "wlan0", "ipv4": None}
        ]

        result = has_network_connectivity()

        assert result is False

    @patch("configurator.ble_provisioning.network.list_physical_interfaces")
    def test_has_network_connectivity_error(self, mock_interfaces):
        """Test network connectivity detection with error"""
        mock_interfaces.side_effect = IOError("Error reading interfaces")

        result = has_network_connectivity()

        assert result is False

    @patch("configurator.ble_provisioning.network.list_physical_interfaces")
    def test_has_network_connectivity_empty_list(self, mock_interfaces):
        """Test network connectivity detection with no interfaces"""
        mock_interfaces.return_value = []

        result = has_network_connectivity()

        assert result is False


class TestSetupLogging:
    """Test cases for setup_logging function"""

    @patch("configurator.ble_provisioning.logging.getLogger")
    @patch("configurator.ble_provisioning.logging.StreamHandler")
    @patch("configurator.ble_provisioning.logging.Formatter")
    def test_setup_logging_normal(self, mock_formatter, mock_handler, mock_logger):
        """Test logging setup with normal verbosity"""
        mock_root_logger = MagicMock()
        mock_logger.return_value = mock_root_logger

        setup_logging(verbose=False)

        mock_root_logger.setLevel.assert_called()

    @patch("configurator.ble_provisioning.logging.getLogger")
    @patch("configurator.ble_provisioning.logging.StreamHandler")
    @patch("configurator.ble_provisioning.logging.Formatter")
    def test_setup_logging_verbose(self, mock_formatter, mock_handler, mock_logger):
        """Test logging setup with verbose flag"""
        mock_root_logger = MagicMock()
        mock_logger.return_value = mock_root_logger

        setup_logging(verbose=True)

        mock_root_logger.setLevel.assert_called()


class TestMainCLI:
    """Test cases for main CLI function"""

    @patch("configurator.ble_provisioning.has_network_connectivity")
    @patch("sys.exit")
    def test_main_check_network_no_connectivity(self, mock_exit, mock_has_conn):
        """Test check-network when no network connectivity"""
        mock_has_conn.return_value = False

        with patch("sys.argv", ["ble-provisioning", "--check-network"]):
            main()

        mock_exit.assert_called_with(0)

    @patch("configurator.ble_provisioning.has_network_connectivity")
    @patch("sys.exit")
    def test_main_check_network_with_connectivity(self, mock_exit, mock_has_conn):
        """Test check-network when network is connected"""
        mock_has_conn.return_value = True

        with patch("sys.argv", ["ble-provisioning", "--check-network"]):
            main()

        mock_exit.assert_called_with(1)

    @patch("configurator.ble_provisioning.subprocess.run")
    @patch("sys.exit")
    def test_main_stop_service(self, mock_exit, mock_run):
        """Test stop action"""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("sys.argv", ["ble-provisioning", "--stop"]):
            main()

        mock_run.assert_called_once()
        mock_exit.assert_called_with(0)

    @patch("configurator.ble_provisioning.subprocess.run")
    @patch("sys.exit")
    def test_main_stop_service_failure(self, mock_exit, mock_run):
        """Test stop action when systemctl returns an error."""
        mock_run.return_value = MagicMock(returncode=1, stderr="unit not found")

        with patch("sys.argv", ["ble-provisioning", "--stop"]):
            main()

        mock_run.assert_called_once()
        mock_exit.assert_called_with(1)

    @patch("sys.argv", ["ble-provisioning"])
    def test_main_no_action_required(self):
        """Test main with no action specified"""
        # Should exit with error due to mutually exclusive group requirement
        with pytest.raises(SystemExit):
            main()

    @patch("configurator.ble_provisioning.setup_logging")
    def test_main_verbose_flag(self, mock_setup_logging):
        """Test that verbose flag is processed"""
        with patch("sys.argv", ["ble-provisioning", "--check-network", "-v"]):
            with patch("configurator.ble_provisioning.has_network_connectivity", return_value=False):
                with patch("sys.exit"):
                    main()

        mock_setup_logging.assert_called()

    @patch("configurator.ble_provisioning.BLEProvisioningServer")
    @patch("configurator.ble_provisioning.asyncio.set_event_loop")
    @patch("configurator.ble_provisioning.asyncio.new_event_loop")
    def test_main_serve_happy_path(self, mock_new_loop, mock_set_loop, mock_server_cls):
        """Serve mode should start, run, and stop the provisioner cleanly."""
        loop = MagicMock()
        mock_new_loop.return_value = loop
        provisioner = MagicMock()
        provisioner.start = MagicMock()
        provisioner.stop = MagicMock()
        mock_server_cls.return_value = provisioner

        with patch("sys.argv", ["ble-provisioning", "--serve"]):
            main()

        mock_set_loop.assert_called_once_with(loop)
        assert loop.add_signal_handler.call_count == 2
        assert loop.run_until_complete.call_count == 2
        loop.run_forever.assert_called_once()
        loop.close.assert_called_once()

    @patch("configurator.ble_provisioning.BLEProvisioningServer")
    @patch("configurator.ble_provisioning.asyncio.set_event_loop")
    @patch("configurator.ble_provisioning.asyncio.new_event_loop")
    def test_main_serve_signal_handler_stops_loop(self, mock_new_loop, mock_set_loop, mock_server_cls):
        """Serve mode should register a signal handler that stops the loop."""
        loop = MagicMock()
        captured_callbacks = []

        def capture_handler(_sig, callback):
            captured_callbacks.append(callback)

        loop.add_signal_handler.side_effect = capture_handler
        mock_new_loop.return_value = loop

        provisioner = MagicMock()
        provisioner.start = MagicMock()
        provisioner.stop = MagicMock()
        mock_server_cls.return_value = provisioner

        with patch("sys.argv", ["ble-provisioning", "--serve"]):
            main()

        assert len(captured_callbacks) == 2
        captured_callbacks[0]()
        loop.stop.assert_called_once()

    @patch("configurator.ble_provisioning.BLEProvisioningServer")
    @patch("configurator.ble_provisioning.asyncio.set_event_loop")
    @patch("configurator.ble_provisioning.asyncio.new_event_loop")
    def test_main_serve_start_error_still_runs_finally(self, mock_new_loop, mock_set_loop, mock_server_cls):
        """Serve mode should still execute stop/close in finally on startup error."""
        loop = MagicMock()
        loop.run_until_complete.side_effect = [RuntimeError("start failed"), None]
        mock_new_loop.return_value = loop
        provisioner = MagicMock()
        provisioner.start = MagicMock()
        provisioner.stop = MagicMock()
        mock_server_cls.return_value = provisioner

        with patch("sys.argv", ["ble-provisioning", "--serve"]):
            main()

        mock_set_loop.assert_called_once_with(loop)
        loop.run_forever.assert_not_called()
        loop.close.assert_called_once()
