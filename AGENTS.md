# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

`bot-vendas/` is a Python service that continuously monitors a sales file
(`vendas.csv` or `.xlsx`) and sends a WhatsApp message via the **Evolution API**
for every new sale. It deduplicates via SQLite, persists the last processed ID in
`config.json`, exposes a Flask **web dashboard**, and has logging + error handling.
See `bot-vendas/README.md` for full setup, configuration, and usage.

### Services and how to run them

Run everything from inside `bot-vendas/`.

- **Bot (monitor + dashboard):** `python3 main.py` (add `--no-dashboard` for headless).
  Dashboard serves on `http://localhost:5000` (`config.json` → `dashboard.port`).
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
