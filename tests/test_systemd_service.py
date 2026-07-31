from unittest.mock import MagicMock, patch, mock_open

from configurator.systemd_service import SystemdServiceManager


@patch.object(SystemdServiceManager, "_build_service_environment_map")
@patch.object(SystemdServiceManager, "_detect_user_service_user")
def test_status_propagates_failed_status_success(mock_detect_user, mock_build_map):
    manager = SystemdServiceManager()

    with patch.object(
        manager,
        "_run_service_cmd",
        side_effect=[
            (False, "", "Unit missing"),
            (False, "", ""),
            (False, "", ""),
        ],
    ):
        success, payload = manager.status("missing-service")

    assert success is False
    assert payload["status_available"] is False
    assert payload["status_output"] == "Unit missing"


@patch.object(SystemdServiceManager, "_build_service_environment_map")
@patch.object(SystemdServiceManager, "_detect_user_service_user")
def test_run_service_cmd_user_uses_user_gid(mock_detect_user, mock_build_map):
    manager = SystemdServiceManager()
    manager.user_name = "alice"
    manager.user_uid = 1001
    manager.user_gid = 1005
    manager.user_runtime_dir = "/run/user/1001"

    with patch.object(manager, "_get_service_environment", return_value="user"), \
         patch.object(manager, "_run_command", return_value=(True, "", "")) as mock_run:
        manager._run_service_cmd(["status", "demo.service"], "demo.service")

    cmd = mock_run.call_args[0][0]
    assert cmd[:6] == ["systemd-run", "--uid", "1001", "--gid", "1005", "--setenv"]
    assert "XDG_RUNTIME_DIR=/run/user/1001" in cmd
    assert cmd[-4:] == ["systemctl", "--user", "status", "demo.service"]


@patch.object(SystemdServiceManager, "_build_service_environment_map")
@patch.object(SystemdServiceManager, "_detect_user_service_user")
def test_list_services_returns_false_when_all_commands_fail(mock_detect_user, mock_build_map):
    manager = SystemdServiceManager()
    manager.user_name = "alice"
    manager.user_uid = 1001
    manager.user_gid = 1005
    manager.user_runtime_dir = "/run/user/1001"

    with patch.object(manager, "_run_command", return_value=(False, "", "error")):
        success, services = manager.list_services()

    assert success is False
    assert services == []


@patch.object(SystemdServiceManager, "_build_service_environment_map")
@patch.object(SystemdServiceManager, "_detect_user_service_user")
def test_list_services_user_listing_uses_systemd_run(mock_detect_user, mock_build_map):
    manager = SystemdServiceManager()
    manager.user_name = "alice"
    manager.user_uid = 1001
    manager.user_gid = 1005
    manager.user_runtime_dir = "/run/user/1001"

    system_stdout = "UNIT LOAD ACTIVE SUB DESCRIPTION\nalpha.service loaded active running Alpha\n"
    user_stdout = "UNIT LOAD ACTIVE SUB DESCRIPTION\nbeta.service loaded inactive dead Beta\n"

    with patch.object(
        manager,
        "_run_command",
        side_effect=[(True, system_stdout, ""), (True, user_stdout, "")],
    ) as mock_run:
        success, services = manager.list_services(pattern="")

    assert success is True
    assert len(services) == 2

    user_cmd = mock_run.call_args_list[1][0][0]
    assert user_cmd[0] == "systemd-run"
    assert "--uid" in user_cmd and "1001" in user_cmd
    assert "--gid" in user_cmd and "1005" in user_cmd
    assert "--setenv" in user_cmd
    assert "XDG_RUNTIME_DIR=/run/user/1001" in user_cmd
    assert "systemctl" in user_cmd and "--user" in user_cmd


def test_detect_user_service_user_sets_gid():
    manager = SystemdServiceManager.__new__(SystemdServiceManager)
    manager.user_name = None
    manager.user_uid = None
    manager.user_gid = None
    manager.user_runtime_dir = None

    passwd_entry = MagicMock()
    passwd_entry.pw_uid = 1234
    passwd_entry.pw_gid = 4321

    with patch("configurator.systemd_service.os.path.exists", return_value=True), \
         patch("configurator.systemd_service.pwd.getpwnam", return_value=passwd_entry), \
         patch("builtins.open", mock_open(read_data="alice\n")):
        manager._detect_user_service_user()

    assert manager.user_name == "alice"
    assert manager.user_uid == 1234
    assert manager.user_gid == 4321
    assert manager.user_runtime_dir == "/run/user/1234"
