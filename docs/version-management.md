# Version Management

This package uses centralized version management to avoid inconsistencies.

## Single Source of Truth

**Version is defined in one place only:**
- `configurator/_version.py` - Contains `__version__ = "x.y.z"`

## Version Consumers and Sync Points

Version values are consumed or synchronized in these files:

- `pyproject.toml` - Package metadata version used during builds
- `configurator/server.py` - Imports version for API responses
- `docs/api-documentation.md` - Synced via `sync_docs_version.py`
- `debian/changelog` - Can be updated via `update_changelog.py`

## How to Bump Version

1. **Edit source version:** Update `configurator/_version.py`
2. **Sync package metadata version:** Update `pyproject.toml` to match
3. **Sync documentation:** Run `python3 sync_docs_version.py`
4. **Update changelog:** Run `python3 update_changelog.py "description of changes"`

## Scripts

- `sync_docs_version.py` - Updates API documentation version
- `update_changelog.py` - Adds new entry to debian changelog

## Example Version Bump

```bash
# 1. Edit configurator/_version.py: __version__ = "2.1.0"

# 2. Sync docs
python3 sync_docs_version.py

# 3. Update changelog
python3 update_changelog.py "Added new feature X
Fixed bug Y
Improved performance"
```

This helps keep version references in sync across packaging, API output, docs, and changelog.
