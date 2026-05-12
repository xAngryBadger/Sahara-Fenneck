# Fennec Excel Supercharge Plan — v1.0

## Objective

Take Fennec from late-alpha to a professional-grade v1.0 release. No rewrites — surgical fixes, hardening, and test coverage. The goal: a portfolio-ready desktop AI agent that a stranger can install, trust, and use without hitting a crash, a security hole, or a silent failure.

## Audit Summary

62 findings across 8 categories:

| Category | Count | P0 (blocks release) | P1 (must fix) | P2 (should fix) |
|----------|-------|---------------------|---------------|-----------------|
| Critical Bugs | 8 | 4 | 3 | 1 |
| Security | 8 | 3 | 3 | 2 |
| Dead Code | 8 | 1 | 4 | 3 |
| Architecture | 8 | 0 | 4 | 4 |
| Testing | 8 | 2 | 4 | 2 |
| Performance | 6 | 1 | 3 | 2 |
| Error Handling | 6 | 2 | 3 | 1 |
| Config/Deploy | 10 | 2 | 4 | 4 |

---

## Phase 0: Emergency Triage (P0 fixes — do first, before anything else)

**Goal:** Eliminate the things that can destroy user data or compromise security.

### Task 0.1: Kill the exec() sandbox escape vectors
**Description:** The `optimize_tool` sandbox in `tools.py` is fundamentally broken. `getattr()` is not blocked, `Exception` is in `SAFE_BUILTINS`, and the Python class hierarchy provides a trivial escape to `os._wrap_close` / `subprocess.Popen`. This is a remote code execution vulnerability — the LLM generates code that runs with full user privileges.

**Acceptance criteria:**
- [ ] `getattr`, `type`, `vars`, `dir`, `hasattr`, `delattr`, `setattr` added to `FORBIDDEN_NAMES`
- [ ] `Exception`, `BaseException`, `object` removed from `SAFE_BUILTINS`
- [ ] `pd` and `openpyxl` namespace restricted — no `__builtins__` access via `pd.io.common.os` etc.
- [ ] 20+ adversarial sandbox bypass tests pass (see Task 2.3)
- [ ] Exec runs in a subprocess with resource limits (timeout, memory cap) — not in-process

**Verification:** Run sandbox test suite. Attempt all known Python sandbox escapes.

**Dependencies:** None

**Files likely touched:**
- `src/agent/tools.py` (sandbox validation, exec context)
- NEW: `src/agent/sandbox.py` (subprocess-based execution)

**Estimated scope:** M (3-5 files)

### Task 0.2: Add threading.Lock to _workspaces dict
**Description:** `MainWindow._workspaces` is mutated from background threads and read from the UI thread with no synchronization. This causes `RuntimeError: dictionary changed size during iteration` and potential data corruption.

**Acceptance criteria:**
- [ ] `threading.Lock` wraps all `_workspaces` reads and writes in `MainWindow`
- [ ] No bare `_workspaces[key]` access — all go through a locked accessor
- [ ] Agent callback closures acquire lock before mutating

**Verification:** Run app, send rapid messages while indexing, no RuntimeError.

**Dependencies:** None

**Files likely touched:**
- `src/gui/main_window.py`

**Estimated scope:** S (1-2 files)

### Task 0.3: Fix PyInstaller hiddenimports
**Description:** The `.spec` file has `hiddenimports=[]` — the packaged executable will crash on import for `win32crypt`, `pythoncom`, `win32com.client`, `psutil`, `tkinterdnd2`.

**Acceptance criteria:**
- [ ] All dynamically-imported modules listed in `hiddenimports`
- [ ] Packaged executable starts without `ImportError`
- [ ] COM operations work in packaged build

**Verification:** Build with PyInstaller, run the exe, test COM indexing.

**Dependencies:** None

**Files likely touched:**
- `FennecExcel.spec`

**Estimated scope:** XS (1 file)

### Task 0.4: Remove dead dependencies from requirements.txt
**Description:** `ollama`, `langchain`, `langchain-ollama`, `sentence-transformers`, `pymongo` are listed but never imported. `sentence-transformers` alone pulls PyTorch (~2GB). This bloats the installer by ~3GB and the PyInstaller build.

**Acceptance criteria:**
- [ ] `requirements.txt` contains only actually-used packages
- [ ] `pip install -r requirements.txt` succeeds and is <500MB
- [ ] All imports in `src/` resolve after cleanup

**Verification:** Fresh venv, `pip install -r requirements.txt`, `python -c "import src"`.

**Dependencies:** None

**Files likely touched:**
- `requirements.txt`

**Estimated scope:** XS (1 file)

### Task 0.5: Add timeout to confirmation dialog wait
**Description:** `_confirm_change_blocking` uses `decision.wait()` with no timeout. If the UI is closed while waiting, the background thread hangs forever.

**Acceptance criteria:**
- [ ] `decision.wait(timeout=300)` (5 min max)
- [ ] Timeout returns `False` (reject the modification)
- [ ] User sees a message when confirmation times out

**Verification:** Start modification, close app before confirming, thread exits cleanly.

**Dependencies:** None

**Files likely touched:**
- `src/gui/main_window.py`

**Estimated scope:** XS (1 file)

### Task 0.6: Fix openpyxl resource leaks in runner.py
**Description:** `_detect_sheet_name()` and `_list_sheet_names()` open workbooks with `openpyxl.load_workbook()` but don't use `try/finally` — exceptions between open and close leak file handles.

**Acceptance criteria:**
- [ ] All `load_workbook()` calls wrapped in `try/finally` with `wb.close()`
- [ ] Or use context manager: `with openpyxl.load_workbook(...) as wb:`

**Verification:** Run agent against file with corrupted sheet names, no leaked handles.

**Dependencies:** None

**Files likely touched:**
- `src/agent/runner.py`

**Estimated scope:** XS (1 file)

### Task 0.7: Replace string-based error checking with structured results
**Description:** `runner.py` checks `"sucesso" in result.lower()` and `result.lower().startswith("erro ao salvar checkpoint")` to determine if tools succeeded. This is fragile and locale-dependent.

**Acceptance criteria:**
- [ ] Tools return `ToolResult` dataclass with `success: bool`, `message: str`, `data: dict | None`
- [ ] Runner checks `result.success` instead of string matching
- [ ] All 10 structured actions return `ToolResult`
- [ ] `optimize_tool` returns `ToolResult`

**Verification:** Existing smoke tests adapted, new unit tests pass.

**Dependencies:** None

**Files likely touched:**
- `src/agent/tools.py`
- `src/agent/runner.py`
- NEW: `src/agent/result.py`

**Estimated scope:** M (3-5 files)

---

## Checkpoint 0: Emergency Triage Complete
- [ ] No known RCE vectors in the sandbox
- [ ] No thread-unsafe shared state
- [ ] PyInstaller build works
- [ ] `pip install` is <500MB
- [ ] No hung threads on app close
- [ ] No resource leaks on error paths
- [ ] No string-based error detection

---

## Phase 1: Security Hardening

**Goal:** Make the OAuth flow, token storage, and command execution safe enough for a stranger to trust.

### Task 1.1: Move OAuth client IDs out of source code
**Description:** Google and Microsoft OAuth client IDs are hardcoded in `oauth_defaults.py`. While client IDs alone aren't secrets, they enable impersonation when combined with a compromised binary.

**Acceptance criteria:**
- [ ] `oauth_defaults.py` reads IDs from env vars or `oauth_defaults.json` only
- [ ] `EMBEDDED_GOOGLE_CLIENT_ID` and `EMBEDDED_MICROSOFT_CLIENT_ID` removed from source
- [ ] `.env.example` documents `FENNEC_GOOGLE_CLIENT_ID` and `FENNEC_MICROSOFT_CLIENT_ID`
- [ ] Fallback: if no env var / JSON file, show setup instructions in UI

**Verification:** Build without embedded IDs, set env vars, OAuth flow works.

**Dependencies:** None

**Files likely touched:**
- `src/integrations/oauth_defaults.py`
- `.env.example`

**Estimated scope:** S (1-2 files)

### Task 1.2: Encrypt token storage on non-Windows / no-DPAPI
**Description:** When DPAPI is unavailable, tokens are stored as base64-encoded plaintext — trivially decodable by any process.

**Acceptance criteria:**
- [ ] When DPAPI unavailable, use `cryptography.fernet.Fernet` with a key derived from machine-specific data (hostname + username salt)
- [ ] Plaintext mode removed entirely — always encrypted
- [ ] Migration: existing plaintext tokens auto-encrypted on first load
- [ ] `_unprotect()` raises on decryption failure instead of returning `b""`

**Verification:** Delete DPAPI module, run app, tokens encrypted, no silent data loss.

**Dependencies:** None

**Files likely touched:**
- `src/integrations/token_store.py`
- `requirements.txt` (add `cryptography`)

**Estimated scope:** S (1-2 files)

### Task 1.3: Fix PowerShell command injection in OAuth URL opening
**Description:** `oauth.py` interpolates a URL into a PowerShell `-Command` string with single quotes. A URL containing a single quote breaks out of the string.

**Acceptance criteria:**
- [ ] URL passed as a separate argument, not interpolated into the command string
- [ ] Or use `webbrowser.open()` exclusively (remove PowerShell/cmd fallbacks)
- [ ] No shell injection vector in any subprocess call

**Verification:** Test with URL containing `'` character, no PowerShell error.

**Dependencies:** None

**Files likely touched:**
- `src/integrations/oauth.py`

**Estimated scope:** XS (1 file)

### Task 1.4: Add logging framework
**Description:** The entire app has zero usage of Python's `logging` module. 53 `except Exception:` blocks silently swallow errors. There is no way to diagnose issues from production installations.

**Acceptance criteria:**
- [ ] `logging` configured with file handler in APPDATA (`sahara_fennec.log`)
- [ ] Rotating file handler (10MB max, 3 backups)
- [ ] All `except Exception: pass` replaced with `except Exception: log.exception(...)`
- [ ] Key operations log at INFO level (indexing, agent calls, OAuth events, checkpoints)
- [ ] Debug-level logging for agent loop internals

**Verification:** Run app, trigger errors, check log file has full stack traces.

**Dependencies:** None

**Files likely touched:**
- `src/agent/runner.py`
- `src/agent/tools.py`
- `src/agent/ollama_client.py`
- `src/gui/main_window.py`
- `src/integrations/oauth.py`
- `src/integrations/token_store.py`
- `src/integrations/router.py`
- `src/checkpoints/manager.py`
- `src/indexing/excel_reader.py`
- NEW: `src/logging_config.py`

**Estimated scope:** L (5+ files) — but each change is mechanical (add `log = logging.getLogger(__name__)`, replace `pass` with `log.exception`)

---

## Checkpoint 1: Security Hardening Complete
- [ ] No secrets in source code
- [ ] Token storage always encrypted
- [ ] No shell injection vectors
- [ ] All errors logged with stack traces
- [ ] Log file exists and is useful

---

## Phase 2: Test Infrastructure

**Goal:** Build the test suite from zero. Target: 80% coverage on core modules (`agent/`, `indexing/`, `checkpoints/`), 60% on `integrations/`, 40% on `gui/`.

### Task 2.1: Set up pytest infrastructure
**Description:** No test framework exists. Need pytest, fixtures, and CI-compatible test runner.

**Acceptance criteria:**
- [ ] `pytest` in `requirements-dev.txt`
- [ ] `conftest.py` with shared fixtures (fake workspace, fake ollama, temp excel files)
- [ ] `pyproject.toml` with pytest config, coverage settings
- [ ] `pytest` runs and discovers tests correctly
- [ ] `make test` or `python -m pytest` works

**Verification:** `pytest --co` lists all test files, `pytest` runs them.

**Dependencies:** Phase 0 (structured results)

**Files likely touched:**
- NEW: `tests/conftest.py`
- NEW: `pyproject.toml`
- NEW: `requirements-dev.txt`

**Estimated scope:** S (1-2 files)

### Task 2.2: Unit tests for structured actions tool
**Description:** 10 action types (sort, fillna, replace, rename_column, drop_columns, add_computed_column, filter_equals, duplicate_sheet, create_sheet, delete_sheet) with zero test coverage.

**Acceptance criteria:**
- [ ] Each action type has 3+ test cases (happy path, edge case, error case)
- [ ] Tests use in-memory `Workspace` objects with small DataFrames
- [ ] Tests verify DataFrame state after each action
- [ ] Coverage of `structured_actions_tool()` > 90%

**Verification:** `pytest tests/test_structured_actions.py — all pass.

**Dependencies:** Task 2.1

**Files likely touched:**
- NEW: `tests/test_structured_actions.py`

**Estimated scope:** M (3-5 files with fixtures)

### Task 2.3: Adversarial sandbox bypass tests
**Description:** The exec() sandbox is the most security-critical component. It needs exhaustive adversarial testing.

**Acceptance criteria:**
- [ ] 20+ bypass attempts tested, all blocked:
  - `getattr(os, 'system')`
  - `().__class__.__bases__[0].__subclasses__()`
  - `type.__subclasses__(type)`
  - `pd.io.common.os.system`
  - `openpyxl.__builtins__['__import__']`
  - `[x for x in [].__class__.__base__.__subclasses__() if 'wrap_close' in x.__name__][0].__init__.__globals__`
  - `eval`, `compile`, `__import__` in various forms
  - `breakpoint()`, `exit()`, `quit()`
- [ ] Each test documents the bypass technique being tested
- [ ] Sandbox rejects all attempts with clear error messages

**Verification:** `pytest tests/test_sandbox.py` — all 20+ tests pass.

**Dependencies:** Task 0.1 (sandbox fix)

**Files likely touched:**
- NEW: `tests/test_sandbox.py`

**Estimated scope:** S (1-2 files)

### Task 2.4: Unit tests for checkpoint manager
**Description:** Save, restore, list, and index persistence — all untested.

**Acceptance criteria:**
- [ ] Save checkpoint creates file copy + updates index
- [ ] Restore overwrites workspace file with checkpoint
- [ ] Index persists across manager instances
- [ ] Max 50 checkpoints enforced
- [ ] Corrupted index handled gracefully

**Verification:** `pytest tests/test_checkpoints.py — all pass.

**Dependencies:** Task 2.1, Task 0.7 (structured results for error reporting)

**Files likely touched:**
- NEW: `tests/test_checkpoints.py`

**Estimated scope:** S (1-2 files)

### Task 2.5: Unit tests for Excel reader
**Description:** File-based and COM-based indexing, edge cases (empty sheets, missing files, large files, BOM headers).

**Acceptance criteria:**
- [ ] `index_from_path()` works with `.xlsx`, `.xlsm`, `.xls`
- [ ] Empty sheets return valid Workspace with empty DataFrame
- [ ] Row limit truncation works correctly
- [ ] Multi-sheet indexing returns one Workspace per sheet
- [ ] Missing file raises with clear error
- [ ] `get_workspace_summary()` produces LLM-readable text

**Verification:** `pytest tests/test_excel_reader.py — all pass.

**Dependencies:** Task 2.1

**Files likely touched:**
- NEW: `tests/test_excel_reader.py`
- NEW: `tests/fixtures/` (sample Excel files)

**Estimated scope:** M (3-5 files)

### Task 2.6: Integration tests for agent loop
**Description:** The ReAct agent loop (intent classification, sheet switching, tool dispatch, multi-step) needs end-to-end tests with a fake LLM.

**Acceptance criteria:**
- [ ] Fake Ollama client returns scripted responses
- [ ] Read-only queries don't trigger modifications
- [ ] Modification queries trigger confirmation
- [ ] Sheet name detection switches workspace
- [ ] Multi-step loop terminates after max steps
- [ ] Error recovery (LLM returns garbage) handled gracefully

**Verification:** `pytest tests/test_agent_loop.py — all pass.

**Dependencies:** Task 2.1, Task 0.7

**Files likely touched:**
- NEW: `tests/test_agent_loop.py`

**Estimated scope:** M (3-5 files)

### Task 2.7: Unit tests for OAuth token store
**Description:** DPAPI encryption, Fernet fallback, load/save cycle, corruption handling.

**Acceptance criteria:**
- [ ] Save + load roundtrip preserves tokens
- [ ] DPAPI failure falls back to Fernet (not plaintext)
- [ ] Corrupted file raises, doesn't return `{}`
- [ ] Multiple providers stored independently

**Verification:** `pytest tests/test_token_store.py — all pass.

**Dependencies:** Task 1.2 (Fernet fallback)

**Files likely touched:**
- NEW: `tests/test_token_store.py`

**Estimated scope:** S (1-2 files)

---

## Checkpoint 2: Test Infrastructure Complete
- [ ] `pytest` runs clean with 40+ tests
- [ ] Core module coverage > 80% (`agent/`, `indexing/`, `checkpoints/`)
- [ ] All sandbox bypass attempts blocked
- [ ] CI can run the suite (no live Ollama or Excel required)

---

## Phase 3: Performance & Reliability

**Goal:** Make Fennec fast enough for real work and reliable enough for real users.

### Task 3.1: Batch COM reads instead of cell-by-cell
**Description:** `index_open_excel_workbooks` reads each cell with an individual COM call. A 5000x50 sheet = 250,000 COM calls. Should use `ws.UsedRange.Value` to read the entire range in one call.

**Acceptance criteria:**
- [ ] `ws.UsedRange.Value` reads full range in one COM call
- [ ] Fallback to cell-by-cell if `UsedRange` fails (corrupted range)
- [ ] Indexing a 5000-row sheet completes in <2s (vs current 30s+)
- [ ] Result DataFrame is identical to cell-by-cell approach

**Verification:** Benchmark before/after with a large workbook.

**Dependencies:** None

**Files likely touched:**
- `src/indexing/excel_reader.py`

**Estimated scope:** S (1-2 files)

### Task 3.2: Cache sheet names and model list
**Description:** `_detect_sheet_name()` opens the workbook every call. `_list_local_models()` makes an HTTP request every call. Both should be cached.

**Acceptance criteria:**
- [ ] Sheet names cached per workspace path with TTL (60s)
- [ ] Cache invalidated on re-index
- [ ] `_list_local_models()` result cached for 30s
- [ ] OllamaClient reused across messages (not re-instantiated)

**Verification:** Send 5 messages, check Ollama HTTP logs — 1 model list call, not 5.

**Dependencies:** None

**Files likely touched:**
- `src/agent/runner.py`
- `src/agent/ollama_client.py`
- `src/gui/main_window.py`

**Estimated scope:** S (1-2 files)

### Task 3.3: Smart hydration — only re-index the active sheet
**Description:** `hydrate_workspace_full()` re-indexes ALL sheets with no row limit every time a truncated workspace enters the modify path. For large multi-sheet workbooks, this is catastrophic.

**Acceptance criteria:**
- [ ] Hydration re-indexes only the active sheet, not all sheets
- [ ] Row limit removed only for the active sheet
- [ ] Other sheets remain truncated (don't need full data for modification)
- [ ] Performance: hydration of one sheet vs all sheets — measurable improvement

**Verification:** Hydrate on a 5-sheet workbook, check only one sheet is re-read.

**Dependencies:** None

**Files likely touched:**
- `src/indexing/excel_reader.py`
- `src/agent/runner.py`

**Estimated scope:** S (1-2 files)

### Task 3.4: Add progress feedback for long operations
**Description:** Model download (up to 1 hour), indexing large files, and agent steps have no progress indication. The app appears frozen.

**Acceptance criteria:**
- [ ] Model download shows progress in chat ("Baixando modelo qwen2.5:7b — isso pode levar alguns minutos...")
- [ ] Indexing shows sheet name + row count as it progresses
- [ ] Agent steps show "Pensando... (etapa 1/5)" counter
- [ ] All long operations run in background threads with UI updates

**Verification:** Download a new model, watch chat for progress. Index a large file, see sheet-by-sheet feedback.

**Dependencies:** None

**Files likely touched:**
- `src/agent/ollama_client.py`
- `src/gui/main_window.py`
- `src/indexing/excel_reader.py`

**Estimated scope:** M (3-5 files)

### Task 3.5: Ollama process lifecycle management
**Description:** `_start_ollama_if_possible` starts `ollama serve` but discards the process handle. No PID tracking, no health monitoring, no shutdown.

**Acceptance criteria:**
- [ ] Ollama process PID stored and tracked
- [ ] Health check before each request (ping `/api/version`)
- [ ] Auto-restart if Ollama dies mid-session
- [ ] Clean shutdown: Ollama process terminated on app exit (only if app started it)

**Verification:** Kill ollama process mid-session, app detects and restarts it.

**Dependencies:** None

**Files likely touched:**
- `src/agent/ollama_client.py`
- `src/gui/main_window.py`

**Estimated scope:** S (1-2 files)

---

## Checkpoint 3: Performance & Reliability Complete
- [ ] Large workbook indexes in <5s (vs 30s+ before)
- [ ] No redundant HTTP calls or re-indexing
- [ ] Progress shown for all long operations
- [ ] Ollama lifecycle managed
- [ ] Hydration targets only the active sheet

---

## Phase 4: Architecture Cleanup

**Goal:** Reduce complexity, improve maintainability, make future additions easy. No new features — just better structure.

### Task 4.1: Extract MainWindow into focused controllers
**Description:** `MainWindow` is a 926-line god class handling UI, chat, threads, agent, settings, OAuth, checkpoints, and workspace state.

**Acceptance criteria:**
- [ ] `ChatController` — chat rendering, message sending, chat state
- [ ] `WorkspaceManager` — workspace dict, active workspace, hydration
- [ ] `SettingsController` — model selection, indexing config, OAuth connect/disconnect
- [ ] `MainWindow` orchestrates controllers, owns the tkinter root
- [ ] All controller classes have <300 lines each
- [ ] No behavioral change — pure refactor

**Verification:** App works identically before and after. All existing tests pass.

**Dependencies:** Phase 0 (thread safety lock must be in place first)

**Files likely touched:**
- `src/gui/main_window.py` (shrunk)
- NEW: `src/gui/chat_controller.py`
- NEW: `src/gui/workspace_manager.py`
- NEW: `src/gui/settings_controller.py`

**Estimated scope:** L (5+ files) — but pure refactor, no logic change

### Task 4.2: Extract COM context manager
**Description:** COM init/uninit is copy-pasted across 4 files with the same `pythoncom.CoInitialize()` / `finally: pythoncom.CoUninitialize()` pattern.

**Acceptance criteria:**
- [ ] `COMContext` context manager: `with com_context() as excel:`
- [ ] Handles `CoInitialize`, `CoUninitialize`, Excel app acquisition, and workbook resolution
- [ ] All 4 call sites use the context manager
- [ ] No duplicated COM lifecycle code

**Verification:** App works identically. All COM operations function.

**Dependencies:** None

**Files likely touched:**
- NEW: `src/com_utils.py`
- `src/agent/runner.py`
- `src/agent/tools.py`
- `src/indexing/excel_reader.py`
- `src/checkpoints/manager.py`

**Estimated scope:** M (3-5 files)

### Task 4.3: Add LLM client protocol (prepare for multi-backend)
**Description:** `OllamaClient` is instantiated inline with no interface. Adding OpenAI/Claude backend requires modifying `runner.py`.

**Acceptance criteria:**
- [ ] `LLMClient` protocol defined: `generate(messages, model) -> str`
- [ ] `OllamaClient` implements the protocol
- [ ] `runner.py` depends on the protocol, not the concrete class
- [ ] No behavioral change — Ollama still the only backend

**Verification:** App works identically. No new backend added (just the interface).

**Dependencies:** None

**Files likely touched:**
- `src/agent/ollama_client.py`
- `src/agent/runner.py`
- NEW: `src/agent/llm_client.py`

**Estimated scope:** S (1-2 files)

### Task 4.4: Clean up integration router — plugin pattern
**Description:** All 8 integrations are flat functions in a 524-line module. Adding a new integration requires modifying `router.py`.

**Acceptance criteria:**
- [ ] Each integration is a separate module in `src/integrations/backends/`
- [ ] Each backend registers itself with a decorator or entry point
- [ ] Router discovers backends, doesn't hardcode them
- [ ] Keyword matching lives in each backend, not in a central function
- [ ] No behavioral change — all 8 integrations work as before

**Verification:** All integration smoke tests pass. App works identically.

**Dependencies:** None

**Files likely touched:**
- `src/integrations/router.py` (shrunk)
- NEW: `src/integrations/backends/gmail.py`
- NEW: `src/integrations/backends/calendar.py`
- NEW: `src/integrations/backends/drive.py`
- NEW: `src/integrations/backends/outlook.py`
- NEW: `src/integrations/backends/teams.py`
- NEW: `src/integrations/backends/trello.py`
- NEW: `src/integrations/backends/onedrive.py`
- NEW: `src/integrations/backends/sharepoint.py`

**Estimated scope:** L (5+ files) — but pure refactor, no logic change

---

## Checkpoint 4: Architecture Cleanup Complete
- [ ] No file > 400 lines
- [ ] No god classes or god modules
- [ ] COM lifecycle in one place
- [ ] LLM client swappable via protocol
- [ ] Integrations are pluggable
- [ ] All tests pass, no behavioral change

---

## Phase 5: Code Quality & Polish

**Goal:** Remove every wart that would make a reviewer say "hmm."

### Task 5.1: Remove BOM characters from source files
**Description:** 5 files have UTF-8 BOM (`\ufeff`) at the start, which can cause subtle string matching bugs.

**Acceptance criteria:**
- [ ] No BOM in any `.py` or `.txt` file
- [ ] `requirements.txt` starts with a letter, not a BOM

**Verification:** `grep -r $'\xef\xbb\xbf' src/` returns nothing.

**Dependencies:** None

**Files likely touched:**
- `src/indexing/excel_reader.py`
- `src/indexing/__init__.py`
- `src/checkpoints/manager.py`
- `src/gui/side_buttons.py`
- `requirements.txt`

**Estimated scope:** XS (1 file, re-encoding)

### Task 5.2: Remove dead scripts and hardcoded paths
**Description:** `gera_tabela_papai.py` has hardcoded `E:/Sahara Fenneck/` paths. `create_v1_backup.ps1` has hardcoded paths.

**Acceptance criteria:**
- [ ] Dead scripts moved to `scripts/archive/` or deleted
- [ ] No hardcoded absolute paths in any script
- [ ] APP_VERSION single-sourced in `src/__init__.py` or `pyproject.toml`

**Verification:** `grep -r "E:/" scripts/` returns nothing.

**Dependencies:** None

**Files likely touched:**
- `scripts/gera_tabela_papai.py` (delete or archive)
- `installer/create_v1_backup.ps1` (fix or archive)
- `src/gui/main_window.py` (version import)

**Estimated scope:** XS (1 file)

### Task 5.3: Add ruff linting + mypy type checking
**Description:** No linter or type checker configured. Code quality depends on manual review only.

**Acceptance criteria:**
- [ ] `ruff` in `requirements-dev.txt` with config in `pyproject.toml`
- [ ] `mypy` in `requirements-dev.txt` with config in `pyproject.toml`
- [ ] `ruff check src/` passes clean
- [ ] `mypy src/` passes clean (strictness: medium — no `--strict`)
- [ ] Pre-commit hook or CI step runs both

**Verification:** `ruff check src/ && mypy src/` — both pass.

**Dependencies:** Phase 0 (fix errors before linting)

**Files likely touched:**
- `pyproject.toml`
- `requirements-dev.txt`
- Any files with lint errors

**Estimated scope:** M (3-5 files — fixing lint errors across codebase)

### Task 5.4: Document environment variables
**Description:** 12+ environment variables referenced in code with zero documentation.

**Acceptance criteria:**
- [ ] `.env.example` lists all env vars with descriptions and example values
- [ ] README has "Configuration" section linking to `.env.example`
- [ ] Each env var has a comment explaining what it does

**Verification:** New developer reads `.env.example`, can configure all integrations.

**Dependencies:** None

**Files likely touched:**
- `.env.example`
- `README.md`

**Estimated scope:** S (1-2 files)

### Task 5.5: Clean up integration router keyword conflicts
**Description:** Keyword matching creates false positives ("agenda" as column name triggers Calendar, "drive" as verb triggers Google Drive).

**Acceptance criteria:**
- [ ] Integration keywords require explicit trigger prefix ("enviar email", "criar evento", "upload para drive")
- [ ] Column names that match integration keywords don't trigger integrations
- [ ] User can opt out of integration routing per query

**Verification:** Ask "ordenar por agenda" — no Calendar trigger. Ask "enviar por email" — Gmail triggers.

**Dependencies:** Task 4.4 (plugin pattern makes this easier)

**Files likely touched:**
- `src/integrations/router.py` or backend modules

**Estimated scope:** S (1-2 files)

---

## Checkpoint 5: Code Quality & Polish Complete
- [ ] No BOM characters
- [ ] No hardcoded paths
- [ ] `ruff check` passes
- [ ] `mypy` passes
- [ ] All env vars documented
- [ ] No integration false positives
- [ ] Version single-sourced

---

## Phase 6: Release Preparation

**Goal:** Everything needed for a v1.0 release that a stranger can install and trust.

### Task 6.1: Write comprehensive README
**Description:** Current README exists but needs to reflect v1.0 quality. Must include screenshots, setup guide, architecture overview.

**Acceptance criteria:**
- [ ] Screenshots of the desert-themed UI
- [ ] Quick start guide (install Ollama, install Fennec, run)
- [ ] Architecture diagram (agent loop, integrations, checkpoint system)
- [ ] Configuration section (env vars, model selection)
- [ ] Security section (sandbox, token storage, OAuth)
- [ ] Contributing guide (run tests, lint, typecheck)

**Verification:** A new developer reads README and can build + run from source.

**Dependencies:** All previous phases

**Files likely touched:**
- `README.md`

**Estimated scope:** S (1-2 files)

### Task 6.2: Final installer build and test
**Description:** Build the slim installer with cleaned dependencies, test on a clean Windows VM.

**Acceptance criteria:**
- [ ] Slim installer <500MB (vs ~2GB with PyTorch)
- [ ] Fresh install on Windows 10/11 works
- [ ] Ollama auto-start works
- [ ] Model download with progress works
- [ ] COM indexing of open Excel works
- [ ] OAuth flow works in packaged build
- [ ] Checkpoint save/restore works

**Verification:** Install on clean Windows VM, run full workflow.

**Dependencies:** All previous phases

**Files likely touched:**
- `FennecExcel.spec`
- `installer/` scripts

**Estimated scope:** M (3-5 files)

### Task 6.3: Create CHANGELOG.md
**Description:** No changelog exists. v1.0 needs a changelog that documents the journey from v2.0-alpha to v1.0.

**Acceptance criteria:**
- [ ] CHANGELOG.md with sections: Added, Changed, Fixed, Security, Removed
- [ ] All P0 fixes documented
- [ ] Breaking changes called out (if any)

**Verification:** Changelog covers all major changes from this plan.

**Dependencies:** All previous phases

**Files likely touched:**
- NEW: `CHANGELOG.md`

**Estimated scope:** XS (1 file)

### Task 6.4: Tag v1.0 release
**Description:** Git tag, GitHub release with installer assets.

**Acceptance criteria:**
- [ ] All tests pass
- [ ] All checkpoints verified
- [ ] Git tag `v1.0.0` created
- [ ] GitHub release with installer + checksums

**Verification:** `git tag -l v1.0.0` exists, release page has assets.

**Dependencies:** All previous phases

**Files likely touched:**
- None (git operations only)

**Estimated scope:** XS (0 files)

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Subprocess sandbox breaks COM integration | High | Medium | Keep `structured_actions_tool` (no exec) as primary path; subprocess sandbox only for `optimize_tool` |
| PyInstaller missing hidden imports | High | Medium | Test build early (Task 0.3), test on clean VM (Task 6.2) |
| Refactoring MainWindow breaks UI | Medium | Medium | Pure refactor with test coverage first; no logic changes |
| DPAPI → Fernet migration loses tokens | High | Low | Migration: detect plaintext, encrypt in-place, backup original |
| Ollama model format changes | Low | Medium | Model resolution already has fallback chain; test with multiple models |
| Integration refactor breaks OAuth | Medium | Medium | Integration tests for token store; manual OAuth test before merge |

---

## Open Questions

1. **Subprocess sandbox vs RestrictedPython?** Subprocess is more secure but slower and can't access COM. RestrictedPython is in-process but has a larger attack surface. Recommend: subprocess for `optimize_tool`, keep `structured_actions_tool` as-is (no exec at all).
2. **Keep or remove `optimize_tool`?** If we move to subprocess sandbox, the UX changes (slower, no COM access from optimize code). Should we just expand `structured_actions_tool` to cover more operations and deprecate `optimize_tool`?
3. **Non-Windows support?** The Fernet token storage task (1.2) makes non-Windows possible but COM is still Windows-only. Do we want to support file-based Excel operations on Linux/Mac for v1.1?
4. **LLM backend priority?** After the protocol is in place (Task 4.3), which backend next? OpenAI API? Local LM Studio? This affects the protocol design.

---

## Task Summary

| Phase | Tasks | Estimated Scope | Depends On |
|-------|-------|----------------|------------|
| 0: Emergency Triage | 7 | 2M, 4S, 1XS | None |
| 1: Security Hardening | 4 | 1L, 1S, 2XS | Phase 0 |
| 2: Test Infrastructure | 7 | 3M, 4S | Phase 0, 1 |
| 3: Performance & Reliability | 5 | 2M, 3S | Phase 0 |
| 4: Architecture Cleanup | 4 | 2L, 1M, 1S | Phase 0 |
| 5: Code Quality & Polish | 5 | 1M, 2S, 2XS | Phase 0-4 |
| 6: Release Preparation | 4 | 1M, 1S, 2XS | All phases |
| **Total** | **36 tasks** | **5L, 10M, 14S, 7XS** | |

---

## Execution Order

Tasks within each phase can be parallelized where they have no dependencies. Critical path:

```
0.1 (sandbox) ──→ 2.3 (sandbox tests)
0.7 (structured results) ──→ 2.1 (pytest infra) ──→ 2.2, 2.4, 2.5, 2.6, 2.7
1.2 (Fernet tokens) ──→ 2.7 (token store tests)
0.2 (thread lock) ──→ 4.1 (MainWindow refactor)
3.1 (COM batch reads) ──→ independent
4.3 (LLM protocol) ──→ independent
4.4 (integration plugins) ──→ 5.5 (keyword conflicts)
```

Most tasks are independent and can be worked on in parallel by multiple agents or sessions.
