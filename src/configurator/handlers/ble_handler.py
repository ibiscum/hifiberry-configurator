#!/usr/bin/env python3
"""
BLE Provisioning Handler

Handles HTTP API endpoints for managing Bluetooth Low Energy (BLE) provisioning
service. Provides start/stop control and status monitoring for the ble-provisioning
systemd service.
"""

import logging
import subprocess
from typing import Union, Tuple, TYPE_CHECKING, Any, cast, Callable, Optional, Dict

if TYPE_CHECKING:
    from flask import Response  # pyright: ignore[reportMissingModuleSource]
else:
    Response = Any

try:
    from flask import jsonify as _jsonify  # pyright: ignore[reportUnknownVariableType, reportMissingModuleSource]
    jsonify = cast(Any, _jsonify)
except ImportError:
    # Flask is optional - only needed when running with Flask
    def jsonify(*args: Any, **kwargs: Any) -> Any:  # type: ignore
        """Stub jsonify when Flask is not installed"""
        raise RuntimeError("Flask is not installed")

logger = logging.getLogger(__name__)

SERVICE_NAME = "ble-provisioning"


class BLEProvisioningHandler:
    """Handler for BLE provisioning API endpoints"""

    def __init__(
        self,
        service_name: str = SERVICE_NAME,
        run_command: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Initialize BLE provisioning handler.

        Args:
            service_name: systemd service name to control.
            run_command: optional command runner for dependency injection in tests.
        """
        self.service_name = service_name
        self._run_command = run_command

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Run a command using the injected runner or subprocess.run."""
        runner = self._run_command or subprocess.run
        return runner(*args, **kwargs)

    def _success(self, message: str, data: Optional[Dict[str, Any]] = None) -> "Response":
        """Create a standardized success response."""
        payload: Dict[str, Any] = {
            "status": "success",
            "message": message,
            "data": data or {},
        }
        return jsonify(payload)

    def _error(
        self,
        message: str,
        error: str,
        http_status: int = 500,
        data: Optional[Dict[str, Any]] = None,
    ) -> Tuple["Response", int]:
        """Create a standardized error response."""
        payload: Dict[str, Any] = {
            "status": "error",
            "message": message,
            "error": error,
        }
        if data is not None:
            payload["data"] = data
        return jsonify(payload), http_status

    def handle_get_status(self) -> Union["Response", Tuple["Response", int]]:
        """Get BLE provisioning service status.

        Returns:
            Flask JSON response with status and service state information
        """
        try:
            result = self._run(
                ["systemctl", "is-active", self.service_name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            active = result.returncode == 0
            state = result.stdout.strip() if result.stdout else "unknown"
            logger.debug(
                "BLE status check completed: service=%s active=%s state=%s rc=%s",
                self.service_name,
                active,
                state,
                result.returncode,
            )
            return self._success(
                "BLE provisioning status retrieved",
                {"active": active, "state": state},
            )
        except Exception as e:
            logger.error("Error checking BLE provisioning status: %s", e)
            return self._error(
                "Failed to check BLE provisioning status",
                "status_check_failed",
                500,
                {"system_error": str(e)},
            )

    def handle_start(self) -> Union["Response", Tuple["Response", int]]:
        """Start BLE provisioning service.

        Manual start skips the network check (ExecStartPre) by creating
        a runtime override that clears ExecStartPre.

        Returns:
            Flask JSON response with status message, or tuple with response and status code on error
        """
        try:
            # Create runtime override to skip ExecStartPre (network check)
            override_dir = f"/run/systemd/system/{self.service_name}.service.d"
            mkdir_result = self._run(
                ["mkdir", "-p", override_dir],
                capture_output=True, timeout=5,
                check=False,
            )
            if mkdir_result.returncode != 0:
                logger.warning(
                    "Failed to create override dir %s: %s",
                    override_dir,
                    (mkdir_result.stderr or "").strip(),
                )

            write_result = self._run(
                ["bash", "-c",
                 f'echo -e "[Service]\\nExecStartPre=" > {override_dir}/manual.conf'],
                capture_output=True, timeout=5,
                check=False,
            )
            if write_result.returncode != 0:
                logger.warning(
                    "Failed to write runtime override for %s: %s",
                    self.service_name,
                    (write_result.stderr or "").strip(),
                )

            reload_result = self._run(
                ["systemctl", "daemon-reload"],
                capture_output=True, timeout=10,
                check=False,
            )
            if reload_result.returncode != 0:
                logger.warning(
                    "daemon-reload failed before start of %s: %s",
                    self.service_name,
                    (reload_result.stderr or "").strip(),
                )

            result = self._run(
                ["systemctl", "start", self.service_name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                logger.info("BLE provisioning service started: %s", self.service_name)
                return self._success(
                    "BLE provisioning started",
                    {"service": self.service_name},
                )
            logger.error(
                "Failed to start BLE provisioning service %s: rc=%s stderr=%s",
                self.service_name,
                result.returncode,
                (result.stderr or "").strip(),
            )
            return self._error(
                "Failed to start BLE provisioning service",
                "start_failed",
                500,
                {
                    "service": self.service_name,
                    "stderr": (result.stderr or "").strip(),
                },
            )
        except Exception as e:
            logger.error("Error starting BLE provisioning: %s", e)
            return self._error(
                "Failed to start BLE provisioning service",
                "start_exception",
                500,
                {"service": self.service_name, "system_error": str(e)},
            )

    def handle_stop(self) -> Union["Response", Tuple["Response", int]]:
        """Stop BLE provisioning service.

        Removes runtime override so auto-start uses network check again.

        Returns:
            Flask JSON response with status message, or tuple with response and status code on error
        """
        try:
            result = self._run(
                ["systemctl", "stop", self.service_name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            # Remove runtime override so auto-start uses network check again
            override_dir = f"/run/systemd/system/{self.service_name}.service.d"
            rm_result = self._run(
                ["rm", "-rf", override_dir],
                capture_output=True, timeout=5, check=False
            )
            if rm_result.returncode != 0:
                logger.warning(
                    "Failed to remove override dir %s: %s",
                    override_dir,
                    (rm_result.stderr or "").strip(),
                )

            reload_result = self._run(
                ["systemctl", "daemon-reload"],
                capture_output=True, timeout=10, check=False
            )
            if reload_result.returncode != 0:
                logger.warning(
                    "daemon-reload failed after stop of %s: %s",
                    self.service_name,
                    (reload_result.stderr or "").strip(),
                )

            if result.returncode == 0:
                logger.info("BLE provisioning service stopped: %s", self.service_name)
                return self._success(
                    "BLE provisioning stopped",
                    {"service": self.service_name},
                )
            logger.error(
                "Failed to stop BLE provisioning service %s: rc=%s stderr=%s",
                self.service_name,
                result.returncode,
                (result.stderr or "").strip(),
            )
            return self._error(
                "Failed to stop BLE provisioning service",
                "stop_failed",
                500,
                {
                    "service": self.service_name,
                    "stderr": (result.stderr or "").strip(),
                },
            )
        except Exception as e:
            logger.error("Error stopping BLE provisioning: %s", e)
            return self._error(
                "Failed to stop BLE provisioning service",
                "stop_exception",
                500,
                {"service": self.service_name, "system_error": str(e)},
            )
