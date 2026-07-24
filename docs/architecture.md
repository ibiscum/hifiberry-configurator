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

### 4. Import Semantics and `main` Functions

A common question is how Flask can import handler modules if those modules also define a `main()` function or a `if __name__ == "__main__":` block.

Python import behavior makes this safe:

- Importing a module executes top-level definitions (classes, functions, constants), so handler classes become available to the server.
- A `main()` function is only a function definition until it is explicitly called.
- Code under `if __name__ == "__main__":` only runs when that file is executed directly (for example, `python some_module.py`), not when imported by another module.

In this project, the server imports handlers through the package export layer in `src/configurator/handlers/__init__.py`, and then instantiates them in `src/configurator/server.py`. This is why handler modules can be reused by both CLI tools and the Flask server without unintended side effects.

### 5. How `config-*` Commands Are Generated

The `config-*` commands are not handwritten shell scripts. They are generated from Python packaging entry points during installation.

Generation flow:

- Command mappings are declared in `pyproject.toml` under `[project.scripts]` (for example, `config-hattools = "configurator.hattools:main"`).
- The package uses `setuptools.build_meta` as build backend, which reads these script declarations.
- During installation (local pip install or Debian package build), setuptools creates executable launcher wrappers for each declared command.
- These wrappers import the target module and call its `main()` function.

Result:

- Running `config-hattools` executes `configurator.hattools:main`.
- Running `config-server` executes `configurator.server:main`.

For Debian builds, `debian/rules` is configured to use the pyproject/pybuild path, so command generation still comes from the same `[project.scripts]` definitions.

## Summary

Both the CLI tools and the API server act as clients to the same shared handler modules. This design provides several advantages:

-   **Consistency**: The logic for a given operation is identical, whether it is triggered via the command line or the API.
-   **Maintainability**: Business logic is centralized in one place, making it easier to update and maintain.
-   **Flexibility**: New interfaces (e.g., a new type of client) can be added easily by having them consume the existing handler modules.
