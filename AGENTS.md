# Repository Guidelines

## Project Structure & Module Organization
- Core runtime code lives in `ps-audio-recorder/`.
- Entry point: `ps-audio-recorder/main.py` (async event loop, input handling, recorder orchestration).
- Recording pipeline: `ps-audio-recorder/recorder.py` (`arecord` -> `lame`, file lifecycle, bulb state handling).
- Device integrations: `ps-audio-recorder/devices/` (`audio.py`, `input.py`, `light.py`).
- Shared utilities: `ps-audio-recorder/utils/logging.py`.
- Provisioning and service setup: root `setup.sh`; runtime launcher: `ps-audio-recorder/start-recorder.sh`.
- ReplayGain helper assets: `ps-audio-recorder/replaygain-watcher.sh`, `replaygain-watcher.env.example`, and smoke test script.

## Build, Test, and Development Commands
- `sudo ./setup.sh`: installs system packages, writes service files, and enables recorder + ReplayGain services.
- `bash ps-audio-recorder/start-recorder.sh`: creates/activates `.venv` and runs the recorder manually.
- `python ps-audio-recorder/main.py`: direct run when dependencies are already installed.
- `bash ps-audio-recorder/smoke-test-replaygain.sh`: end-to-end smoke test for the `ps-replaygain` watcher.
- `sudo systemctl status ps-audio-recorder` and `sudo journalctl -u ps-audio-recorder -f`: service health + live logs.

## Coding Style & Naming Conventions
- Follow existing Python style: 4-space indentation, snake_case for functions/variables, PascalCase for classes (`Recorder`, `Config`).
- Keep configuration constants centralized in `config.py` as UPPER_SNAKE_CASE attributes.
- Prefer small, focused modules under `devices/` for hardware/network integrations.
- Shell scripts should be POSIX/Bash-friendly with defensive flags (`set -e` or `set -euo pipefail` for new scripts).

## Testing Guidelines
- No formal unit test suite is currently checked in; validate behavior with service-level and script-level smoke testing.
- For ReplayGain changes, run `bash ps-audio-recorder/smoke-test-replaygain.sh` and confirm a `[pass]` result.
- For recorder changes, verify start/stop toggle behavior and log output in `/var/log/audio-recorder.log`.

## Commit & Pull Request Guidelines
- Match project history: short, imperative commit subjects (e.g., `Add ReplayGain auto-processor and setup instructions`).
- Keep commits scoped to one logical change; include config/service updates in the same commit when tightly coupled.
- PRs should include: purpose, deployment impact (systemd/config changes), manual test evidence, and relevant log snippets.
- If behavior affects recording flow or web/SMB access, include before/after notes for operators.
