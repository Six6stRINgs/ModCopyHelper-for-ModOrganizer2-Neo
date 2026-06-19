# ModCopyHelper

A ModOrganizer 2 plugin (Python/PyQt6) that copies selected mod files to the game directory on launch and removes them on exit. Redirects game output to MO2's overwrite folder.

## Architecture

- `__init__.py` — Plugin entry point. Implements `mobase.IPluginTool` + `mobase.IPluginFileMapper`. Exports `createPlugin()` (MO2 convention).
- `logic.py` — Core logic: file copy/remove, settings/manifest I/O, crash recovery, file mapping for overwrite redirection.
- `ui.py` — PyQt6 `QDialog` for mod selection with filtering, table view (Name + Priority columns), sortable headers.
- `logger.py` — Logging to both MO2 log system and a file under `<pluginDataPath>/modcopyhelper/`.

## Key Dependencies

- `mobase` — MO2 Python bindings (not pip-installable; provided by MO2 runtime).
- `PyQt6` — UI framework (bundled with MO2).
- Standard library only otherwise (`json`, `shutil`, `logging`, `pathlib`).

## Development

No build step, no tests, no linting configured. This is a drop-in MO2 plugin — place the folder under MO2's `plugins/` directory.

To test: install in MO2, enable the plugin, configure mod selection via the settings dialog, launch a game, verify files are copied/removed.

## Conventions

- Settings and manifest are JSON files stored per-profile in the MO2 profile directory.
- Crash recovery: on init, if a manifest exists from a previous run, leftover copied files are cleaned up.
- All paths use `pathlib.Path`; `shutil.copy2` for files, `shutil.copytree` for directories.
- Logging format: `%(asctime)s - ModCopyHelper - %(levelname)s - %(message)s`.
