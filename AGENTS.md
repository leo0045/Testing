# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

`bot-vendas/` is a Python service that continuously monitors a sales file
(`vendas.csv` or `.xlsx`) and sends a WhatsApp message via the **Evolution API**
for every new sale. It deduplicates via SQLite, persists the last processed ID in
`config.json`, exposes a Flask **web dashboard**, and has logging + error handling.
See `bot-vendas/README.md` for full setup, configuration, and usage.

### Services and how to run them

Run everything from inside `bot-vendas/`. `app.py` (`BotApplication`) is the shared
core used by the CLI, GUI, and Windows service — change wiring there, not in three
places.

- **Bot CLI (monitor + dashboard):** `python3 main.py` (add `--no-dashboard`).
  Dashboard serves on `http://localhost:5000` (`config.json` → `dashboard.port`).
- **GUI (config + operate):** `python3 gui.py` (Tkinter). Configures phone, monitored
  file, and Evolution API; starts/stops the bot in-process; tails the log file.
- **Windows service:** `python windows_service.py install|start|stop|remove`
  (Windows-only; needs `pywin32`).
- **Build executable:** `python3 build_exe.py` (GUI) or `--service`; or
  `pyinstaller bot_vendas.spec`.
- **Tests:** `python3 -m pytest` (config in `bot-vendas/pytest.ini`).
- **Mock Evolution API (for end-to-end testing without a real instance):**
  `python3 tests/mock_evolution_api.py --port 8081 --out tests/received_messages.jsonl`
  — records every message it receives and serves them at `GET /messages`.

### Non-obvious gotchas

- `config.json`, `vendas.csv`, `bot_vendas.db`, and `*.log` are **runtime files**
  and are gitignored. On a fresh checkout there is no `config.json`/`vendas.csv`:
  create them with `cp config.example.json config.json` and
  `cp vendas.example.csv vendas.csv`. `config.py` also auto-creates a default
  `config.json` on first run if missing.
- `config.json` is **both config and state**: the app writes `last_id` back to it.
  Deleting `bot_vendas.db` but leaving `last_id` set will skip re-notifying old
  sales; reset both together for a clean run (`rm bot_vendas.db` + set `last_id: 0`).
- Deduplication source of truth is the SQLite `sales` table, so re-writing or
  re-scanning the CSV never resends notifications.
- Keep `evolution_api.dry_run: true` unless real Evolution API credentials are set;
  in dry-run, messages are only logged (no network). For end-to-end tests, point
  `evolution_api.base_url` at the mock server and set `dry_run: false`.
- The monitor uses `watchdog` events **plus** a polling fallback
  (`check_interval`), so it still works on filesystems that don't deliver inotify
  events reliably (some container/network volumes).
- **GUI on Linux** needs the system package `python3-tk` (not a pip dependency, so
  it is NOT in the update script). On Windows/macOS Tkinter ships with Python.
  Running the GUI requires a display (`DISPLAY`); this VM has one at `:1`.
- **PyInstaller does not cross-compile:** building on Linux yields a Linux ELF
  binary (`dist/BotVendas`), not a Windows `.exe`. Produce the `.exe` by running
  the build on Windows (or Wine). The Linux build is still valid for verifying the
  packaging/entrypoints.
- **`windows_service.py` / `pywin32`** only work on Windows; the pywin32 imports are
  guarded so the module imports safely on Linux (used by a unit test). `pywin32` is
  marked `sys_platform == "win32"` in `requirements.txt`, so it is skipped on Linux.
