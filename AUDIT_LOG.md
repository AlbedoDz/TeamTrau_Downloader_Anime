# AUDIT LOG

## [2026-08-15 12:18] — [KAIZEN VERSION V04]: Spanish Subtitle Standardization & Handover
- **Target**: `src/downloader/utils.py`, `src/downloader/anikoto.py`, `src/downloader/core.py`, `run_anikoto.bat`, `run.bat`, `tests/test_spanish_subtitles.py`, `pyproject.toml`, `task.md`
- **Cause**: User required unified Latin American Spanish (`es-LA` / `es-419`) and European Spanish (`es-ES`) classification, batch interactive server persistence, and isolation of existing subtitle checks.
- **Changes**:
  1. Built centralized `classify_spanish_variant()` in `utils.py` to identify `es-LA`, `es-ES`, or `es` without substring false-positives.
  2. Refactored `_select_best_subtitle()` in `anikoto.py` and `resolve_sub_lang_tag()` in `core.py` to use the centralized classifier.
  3. Added `get_target_lang_candidate_tags()` to isolate language checking when pre-evaluating existing subtitles.
  4. Updated interactive server selection in batch mode to preserve chosen server across subsequent episodes.
  5. Updated `run_anikoto.bat` and `run.bat` menu prompts and options.
  6. Added comprehensive unit tests in `test_spanish_subtitles.py`.
- **Test**:
  - `uv run ruff check src/ tests/`: PASS (All checks passed)

## [2026-08-21 16:00] — [PROVIDER EXTENSION]: All-Wish & AnimeSuge Browser-less Extractors
- **Target**: `src/downloader/allwish.py`, `src/downloader/animesuge.py`, `src/downloader/__init__.py`, `tests/test_allwish.py`, `tests/test_animesuge.py`, `task.md`
- **Cause**: Implemented browser-less video and subtitle extraction modules for `all-wish.me` and `animesuge.cz`.
- **Changes**:
  1. Reverse-engineered static HTML & AJAX API endpoints (`/ajax/episode/list/{id}`, `/ajax/server/list`, `/ajax/server?get={link_id}`).
  2. Implemented native VRF simple-hash RC4 cipher encryption/decryption in Python.
  3. Reverse-engineered Megaplay embed player iframe resolving & `/stream/getSources` API.
  4. Implemented adaptive multi-language subtitle selection with prioritization (CR, Forced, Spanish/English variants).
  5. Handled origin-only safe Referers to prevent HTTP 403 Forbidden on `cdn.watching.onl` HLS streams.
  6. Added test suites with live resolving verification for target URLs.
- **Test**:
  - `uv run ruff check src/ tests/`: PASS (All checks passed)
  - `uv run ruff format src/ tests/`: PASS (All files formatted)
  - `uv run pytest`: PASS 32/32 tests (100%)
  - Target A: `https://all-wish.me/watch/world-is-dancing-mof9c/ep-8` -> PASS (HTTP 200 Stream)
  - Target B: `https://animesuge.cz/anime/world-is-dancing-wt8rp/ep-4` -> PASS (HTTP 200 Stream)
- **Impact**: Two new high-speed browser-less providers ready for production batch downloading.

