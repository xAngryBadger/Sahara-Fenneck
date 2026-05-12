# Changelog

All notable changes to Sahara Fennec will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.0.0] — 2026-05-08

### Added

- **NVIDIA NIM cloud backend** — primary LLM provider via OpenAI-compatible API (`meta/llama-3.1-70b-instruct` default). Radio toggle in Settings: NIM (cloud) or Ollama (local).
- **`LLMClient` protocol** — `is_available()` + `generate(prompt, system, max_tokens)` interface for pluggable LLM backends.
- **NimClient** (`src/agent/nim_client.py`) — OpenAI SDK-based client with auth validation, error code integration (E022–E024).
- **Encrypted API key storage** — NIM key stored via Fernet (DPAPI-derived key on Windows, machine-identity on Linux).
- **Error codes** (`src/errcodes.py`) — machine-parseable `[E0xx]` error strings for all failure modes (E001–E024).
- **`COMContext` context manager** (`src/com_utils.py`) — DRY replacement for 4 COM init/uninit patterns across the codebase.
- **MainWindow decomposition** — `ChatController`, `SettingsController`, `WorkspaceManager` extracted from monolithic 1076-line `main_window.py` (now 552 lines).
- **Integration backend plugin architecture** (`src/integrations/backends/`) — 10 backend modules, thin keyword dispatcher in `router.py` (550→117 lines).
- **`APP_VERSION` single-sourced** from `pyproject.toml` via `_read_version()`, shared via `gui/constants.py`.
- **`_MODIFY_SIGNALS` guard** — keyword-based intent classifier prevents accidental `[ACTIONS]` on read-only queries.
- **Word-boundary keyword matching** for integration routing — eliminates false positives.
- **Performance optimizations**:
  - `@lru_cache` on `load_settings()` with mtime-based invalidation (2–3× speedup).
  - `@lru_cache` on `_cached_sheet_names()` (12,000× speedup on repeated sheet name queries).
  - `@lru_cache` on `settings_client_ids()`.
  - Single-sheet indexing path in `index_from_path()` (1.8× faster when only active sheet needed).
  - Optimized `hydrate_workspace_full()` — uses `index_from_path()` instead of full multi-sheet reindex.
  - Checkpoint index compaction — capped at 200 entries per workspace with stale file cleanup.
  - `[perf]` timing logs in `run_agent()` for hydration, LLM call, tool execution.
- **Benchmark script** (`scripts/bench.py`) — measures settings, indexing, sheet name caching, and NIM client performance.
- **196 automated tests** — `test_nim_client`, `test_llm_client`, `test_errcodes`, `test_token_store`, `test_agent_loop`, `test_checkpoints`, `test_excel_reader`, `test_sandbox`, `test_structured_actions`.
- **CLI REPL mode** (`src/cli/repl.py`) — interactive terminal interface for headless/automation use, with commands (`/index`, `/actions`, `/sheets`, `/checkpoint`, `/undo`, `/help`, `/quit`), ANSI colors, and argparse entry point.
- **ODS + .xls format support** — `odfpy` reads `.ods`, `xlrd` reads legacy `.xls`; both auto-convert to `.xlsx` on save. GUI file dialog includes `*.ods`.
- **6 new Excel actions** (19 total) — `filter_contains`, `filter_range`, `pivot_table`, `merge_columns`, `strip_whitespace`, `change_dtype`.
- **System prompt updated** — all 19 actions documented for LLM consumption.
- **311 automated tests** (up from 196) — added `test_ods_xls_reader` (26 tests), `test_cli_repl` (14 tests), `test_new_actions` (29 tests), `test_router` (19 tests), `test_runner_edge` (15 tests).
- **Rewritten README** — architecture diagram, NIM quick start, config table, security section, integrations table, test/lint commands.

### Changed

- Settings UI now includes NIM model selector, NIM base URL, and backend radio toggle.
- Integration router is now a thin dispatcher — all backend logic lives in `src/integrations/backends/`.
- Integration queries demoted — LLM consulted first; integrations only tried when no LLM client available.
- `_list_sheet_names()` and `_detect_sheet_name()` use cached sheet names to avoid redundant openpyxl opens.
- `index_file_multi()` rewritten to use `pd.ExcelFile` with engine dispatch (`openpyxl`/`xlrd`/`odf`) instead of raw openpyxl — supports all 4 formats.
- `_cached_sheet_names()` uses same engine dispatch; removed dead openpyxl-only fallback.
- ODS/.xls inputs get `workspace.path` rewritten to `.xlsx` on save.
- Workbook-level actions blocked for non-xlsx inputs with clear error message.
- `change_dtype` to float now uses `.astype(float)` after `pd.to_numeric()` for correct dtype conversion.
- `save_settings()` now clears the settings cache to prevent stale reads.
- `build_installer.ps1` and `create_v1_backup.ps1` fixed (`$PSScriptRoot | Split-Path`).

### Removed

- **`exec()` removed permanently** — `optimize_tool` fully deleted for security.
- **Dead files deleted** — `src/agent/executor.py`, `src/agent/prompts/`, stale `__pycache__`.
- **UTF-8 BOMs stripped** from 4 source files.

### Fixed

- Import paths in `backends/_utils.py` corrected (`from .oauth` → `from ..oauth`, `from ..config` → `from ...config`).
- `ruff check src/` and `mypy src/` pass with zero errors.
- 132 auto-fixable lint issues resolved, 5 F821 undefined-name bugs fixed.
- Duplicate dead `if mode == "fernet"` block removed from `token_store.py`.
- `_cached_sheet_names` engine variable scoping fixed (was using `engine if 'engine' in dir() else "?"`).
- `excel_reader.py` docstring updated to include `.ods` format.
