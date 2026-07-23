# Debian Package Installation

When installed as a Debian package, the `hifiberry-configurator` sets up a self-contained Python application environment and integrates it with the system using systemd services and command-line entry points.

This document provides a breakdown of what happens during installation.

## 1. Virtual Environment Creation

The package uses `dh_virtualenv` to install a private Python virtual environment into `/usr/lib/hifiberry-configurator/`. This approach provides several benefits:

-   **Isolation**: The application and its specific Python dependencies are isolated from the system's Python, preventing version conflicts.
-   **Reproducibility**: All required Python libraries are vendored into the package, ensuring consistent behavior across different systems.

## 2. Command-Line Tools

Symlinks are created in `/usr/bin/` that point to the executable scripts within the virtual environment. This makes tools like `config-soundcard`, `config-volume`, and `config-server` directly available to be run from the command line.

The full list of installed commands can be found in the `debian/hifiberry-configurator.install` file.

## 3. Systemd Services

The package installs and enables several systemd services to run background processes. These services are defined in the `systemd/` directory and include:

-   `config-server.service`: Runs the main configuration server application.
-   `volume-restore.service`: Restores the last known volume settings on startup.
-   `volume-store.timer` and `volume-store.service`: Periodically save the current volume settings.
-   `config-detect.service`: Detects hardware on startup.

## 4. Configuration Files

-   A default configuration file is placed in `/etc/configserver/configserver.json`.
-   An Nginx configuration snippet is installed at `/etc/nginx/hifiberry-api.d/hifiberry-config.nginx` to proxy web requests to the configuration server.

## 5. Post-Installation Script

The `debian/hifiberry-configurator.postinst` script runs after the package files are copied. It ensures necessary directories like `/etc/configserver` exist and then enables and starts the systemd services.

For more technical details on the build process itself, see [DEBIAN_BUILD.md](../DEBIAN_BUILD.md).
