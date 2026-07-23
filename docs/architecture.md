# Application Architecture

This document explains how the `config-server` and the `config-*` command-line applications are bound together.

## Shared Handler Architecture

The `config-server` and the `config-*` command-line applications are bound together through a shared set of underlying Python modules, not by the command-line tools making API calls to the server. This architecture ensures that business logic is centralized, consistent, and accessible through multiple entry points.

Here's how it works:

### 1. Shared Business Logic in Handlers

The core logic for every configuration task (like managing audio, networking, or system settings) is encapsulated in handler classes within the `src/configurator/handlers/` directory.

For example, `volume_handler.py` contains the `VolumeHandler` class with methods to get, set, and restore volume. This class contains all the implementation details for interacting with the system's audio controls.

### 2. Command-Line Tools as Direct Consumers

Each `config-*` command-line tool is a thin wrapper that directly imports and uses the appropriate handler to perform its task.

When you run a command like `config-volume`, it instantiates the `VolumeHandler` from `volume_handler.py` and calls its methods to execute the requested volume operation. The entry points for these commands are defined in `pyproject.toml`, which maps a command name to a specific function in the codebase that runs the handler.

### 3. Config Server as an API Gateway

The `config-server` application, which is a Flask-based REST API server, also imports these same handler classes. It creates API endpoints (e.g., `/api/v1/volume/headphone`) and maps them to the corresponding methods in the handlers.

When an API request comes in, the server simply calls the same handler method that the equivalent command-line tool would use.

## Summary

Both the CLI tools and the API server act as clients to the same shared handler modules. This design provides several advantages:

-   **Consistency**: The logic for a given operation is identical, whether it is triggered via the command line or the API.
-   **Maintainability**: Business logic is centralized in one place, making it easier to update and maintain.
-   **Flexibility**: New interfaces (e.g., a new type of client) can be added easily by having them consume the existing handler modules.
