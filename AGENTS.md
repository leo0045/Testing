# AGENTS.md

## Cursor Cloud specific instructions

### Current repository state

As of this environment setup, the repository is **empty of application code**. It
contains only `.gitignore` (a standard Python template with a few custom entries such
as `vendas.csv`, `estoque.xlsx`, and `config.json`, hinting at a future Python
sales/inventory project). There is:

- No application source code
- No dependency manifest (`requirements.txt`, `pyproject.toml`, `Pipfile`, etc.)
- No README, tests, or build configuration

There is therefore nothing to build, run, or test yet. A meaningful application
"hello world" is not possible until source code and a dependency manifest are added.

### Toolchain available in the environment

- Python 3.12.3 (`python3`, `pip` 24.0, `venv` module available; pip is **not**
  externally-managed, so `pip install` into the system interpreter works)
- Node.js 22.14.0 (`node`, `npm`) — available via nvm
- `make`
- Docker is **not** installed
- `uv`, `poetry`, and `pipenv` are **not** installed

### Update script

The startup update script installs Python dependencies only if a manifest exists, so
it safely no-ops on the current empty repo:

```
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi
```

When real code and a dependency manifest are added, revisit this update script (and
this file) to match the actual stack — e.g. add `pip install -e .` for a
`pyproject.toml`, or `npm install` if a `package.json` is introduced. Prefer a
virtualenv (`python3 -m venv .venv`) once the project has real dependencies.
