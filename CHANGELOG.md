# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.13] - 2026-05-12

### Docs
- **Refreshed all four screenshots** from the bundled `example_data.xlsx` demo dataset using a Playwright capture script:
  - `dashboard-with-buttons.png` now shows the **Portfolio Total Value Over Time** chart (Apr 2024 → May 2026, €0 → €240k) alongside the header buttons and portfolio summary.
  - `portfolio-overview.png` shows the full top of the dashboard including the value chart and all 11 holdings cards.
  - `stock-detail-nvidia.png` and `stock-detail-microsoft.png` show the per-stock candlestick price chart, position value %, investment tranches, and the **Performance vs. Market Indices** comparison (stock vs S&P 500 vs Euro Stoxx 50).
- All screenshots use public-company tickers from the demo dataset — no PII.

## [0.5.12] - 2026-05-12

### Fixed
- **Read the Docs build failing since v0.5.7** (and breaking the docs badge on PyPI / GitHub): `docs/_static/` and `docs/_templates/` were empty directories referenced by `conf.py`'s `html_static_path` / `templates_path`. Git doesn't track empty directories, so RTD's fresh clone lacked them entirely, triggering Sphinx's `html_static_path entry '_static' does not exist` warning. Combined with the v0.5.7 tightening to `fail_on_warning: true`, that warning failed every RTD build. Added `.gitkeep` placeholders so the directories travel with the repo. Local builds were unaffected because the empty dirs already exist on the dev machine.

## [0.5.11] - 2026-05-12

### Fixed
- **Portfolio total inflated 5× by missing FX rates**: a portfolio holding CHF, JPY, PLN, or BGN positions saw its total spike to absurd values (e.g. €651k for a €125k portfolio) the moment Yahoo's exchange-rate cache lacked an entry for those currencies. `_get_fallback_rate` previously only knew USD/GBP/SEK and returned `1.0` for everything else — treating the foreign price as if it were already EUR (a 1599 JPY share inflated to €1599). Replaced the 3-currency hardcoded list with a dynamic discovery from `Stock.currency` / `StockPrice.currency` and a 35-currency static fallback table covering Europe, Asia/Pacific, the Americas, and the Middle East/Africa.
- **3I GROUP and other London-pence stocks counted as full GBP**: yfinance reports London listings with currency `GBp` or `GBX` (British pence). `GBXEUR=X` on Yahoo Finance is a broken alias that returns the GBP rate (off by 100×). Pence aliases are now derived as `GBP / 100` explicitly and cached under both spellings.
- **Bonds inflating portfolio value 100×**: DEGIRO quotes bond prices as percent-of-face (a Dutch government bond at price 103.49 means 103.49% of par); `1000 units × 103.49` was being summed as €103,490 instead of €1,034.90. New `_compute_price_scales` infers a 0.01 scale factor per stock by comparing `quantity × price` to `value_eur` in transactions, and is applied in both `/api/portfolio-summary` and `/api/portfolio-valuation-history`.
- **Library-level INFO log spam**: app modules (`ticker_resolver`, `fetch_prices`, `import_data`, `database`) emit `logger.info(...)` for per-ISIN resolutions, import progress, etc. Uvicorn defaults to INFO log level which surfaced all of these in the user's console. Set the `degiro_portfolio` and `src.degiro_portfolio` loggers to WARNING at app import time (overridable via `DEGIRO_LOG_LEVEL` env var). Uvicorn's own startup lines are unaffected.

### Testing
- **260 tests total** (+2): regression for `_get_fallback_rate` on extended currencies (CHF/JPY/PLN/BGN/etc. must NOT return 1.0), pence-alias derivation (GBp/GBX = GBP/100), and `_compute_price_scales` correctly classifying a bond (1000 units at 103.49% paying €1097) as 0.01 scale while a normal stock keeps 1.0.

## [0.5.10] - 2026-05-12

### Added
- **Desktop app branding on macOS**: menu bar, Activity Monitor, and Force Quit dialog now show "DEGIRO Portfolio" instead of "Python". On first launch the app creates a minimal `.app` bundle at `~/Library/Application Support/DEGIRO Portfolio/DEGIRO Portfolio.app/` (with a symlink to the Python interpreter and an `Info.plist` containing `CFBundleName`) and `os.execv`s through it so `NSBundle.mainBundle` resolves to a real Info.plist. `NSProcessInfo.processName` is set in lockstep so the process name in Activity Monitor matches.
- **Rounded squircle dock icon**: shipped `icon-256-rounded.png` with an 18%-radius corner mask (macOS Big Sur+ icon shape). `setApplicationIconImage_` is now called from `window.events.shown` (after pywebview has finalized NSApplication) so it isn't overwritten during pywebview's init.

### Known limitation
- The macOS Dock hover tooltip still reads `python3.10`. After `os.execv`, the kernel records the *resolved* binary path (pyenv's python3.10) and the Dock reads its tooltip from there — neither `CFBundleName` nor `NSProcessInfo.processName` can override it. Fixing this for real requires shipping a compiled launcher binary or moving to a py2app/briefcase build, both out of scope for a pip-installed package.

### Testing
- **257 tests total** (+6): bundled icon path selection (rounded preferred), no-op behaviour of macOS branding helpers on non-Darwin platforms, mocked `_set_macos_bundle_name` writes to CFBundleName/CFBundleDisplayName, mocked `_set_macos_dock_icon` calls `setApplicationIconImage_`, and the failure path when `NSImage` returns `None`.

## [0.5.9] - 2026-05-12

### Fixed
- **Desktop app: whole window frozen for several seconds on first launch after install**: on a fresh install the server subprocess has to compile `.pyc` for pandas / SQLAlchemy / yfinance — uvicorn answers `/api/ping` as soon as its event loop is up, but FastAPI's first real request still triggers lazy imports. We were showing the pywebview window during that gap; the embedded WKWebView's initial XHRs stalled and pywebview's pyobjc bridge appeared to hold the Cocoa main thread. Two-phase readiness check now waits for both `/api/ping` (uvicorn alive) and `/api/holdings` (FastAPI fully warm) before opening the window. Subsequent launches are unaffected (≈1.3s warm baseline).

### Added
- **Startup timing diagnostics** in `desktop.py`: each phase (subprocess spawn, uvicorn readiness, FastAPI readiness, window creation, GUI loop entry/exit) logs a timestamped line to stderr. Helps pinpoint future first-launch regressions.

### Testing
- **251 tests total** (+1): replaced the `_wait_for_ready` ping-only test with a two-phase variant plus a new regression that fails if only `/api/ping` responds while `/api/holdings` doesn't.

## [0.5.8] - 2026-05-12

### Fixed
- **Portfolio chart spikes from Yahoo data glitches**: Yahoo Finance periodically returns a stale/wrong-listing value (e.g. €982.15 on AMUNDI's `0E2B.IL` ticker, recurring across multiple months) for one day before reverting to the real price. These single-day spikes blew up the "Portfolio Total Value Over Time" chart. Added a centered 5-day rolling-median outlier filter to every price write path — rows whose close deviates more than 5× from the local median are dropped at ingestion. New `invoke clean-price-outliers` task (with `--dry-run`) sweeps existing junk rows from the database.
- **Desktop app `resource_tracker: leaked semaphore` warning on Ctrl-C**: `desktop.py` used `multiprocessing.Process` + `multiprocessing.Event` to run the FastAPI server alongside pywebview. Those allocate POSIX semaphores tracked by the multiprocessing resource_tracker, and an abrupt Ctrl-C interrupted the parent before the tracker could release them. Rewrote the launcher to use `subprocess.Popen([sys.executable, "-m", "uvicorn", …])` — no shared semaphores, no tracker bookkeeping.
- **Desktop app Ctrl-C now actually exits**: pywebview's native Cocoa/Win32 GUI loop blocks the main thread, so Python signal handlers never dispatch until the user closes the window manually. Wired in the self-pipe trick — `signal.set_wakeup_fd()` plus a worker thread (started via `webview.start(func=…)`) that `select()`s on the signal pipe and calls `window.destroy()` when SIGINT/SIGTERM arrives. Ctrl-C now unwinds the GUI loop and reaches the normal server-shutdown cleanup in ~0.8s.
- **`INFO:degiro_portfolio.*` log spam**: `ticker_resolver.py` called `logging.basicConfig(level=logging.INFO)` at module import — a library anti-pattern that hijacked the root logger globally, surfacing one INFO line per resolved ISIN. Removed the basicConfig call; libraries should let the application configure logging.

### Added
- **Documentation link in the web UI header**: small `📖 Documentation` link in the top-right helper area pointing to https://degiro-portfolio.readthedocs.io/.

### Testing
- **250 tests total** (+10 since v0.5.7): 5 covering `drop_price_outliers` (spike, collapse, threshold, short series, steady series) and 5 covering the desktop subprocess launcher + signal-pipe paths, including a regression test that fails if anyone reintroduces `multiprocessing.Process` / `Event` in `desktop.py`.

## [0.5.7] - 2026-05-12

### Fixed
- **Global ISIN → Yahoo ticker resolution**: the previous resolver only recognised US/NL/DE/FR/IT/ES ISIN prefixes and used `f"{ISIN}{suffix}"` candidates that Yahoo Finance doesn't accept. Everything else (Swedish, Greek, Swiss, UK, Japanese, Polish, Bulgarian, Luxembourg, etc.) silently failed, so `yahoo_ticker` stayed NULL and the holdings page showed no prices or charts. Replaced the prefix heuristic with `yf.Search(isin)` as the primary resolver, with a currency-→-suffix preference map (SEK→.ST, CHF→.SW, GBP→.L, JPY→.T, …) and an ISIN-country-→-suffix fallback for ambiguous currencies like EUR. Covers ~30 currencies and ~40 ISIN country codes globally. Kyndryl (US50155Q1004) now resolves to `KD` instead of the raw ISIN.
- **NULL latest_price masking valid historical close**: Yahoo's `Ticker.history()` returns today's intraday row with NaN OHLC before the close prints; Python's `sqlite3` driver silently stores NaN as NULL. The NULL row was then picked as MAX(date) in `/api/holdings`, hiding yesterday's real close. Now skip NaN-close rows at every write site and filter `close IS NULL` on the read side as defence-in-depth.
- **`app.version` actually tracks `__version__`**: v0.5.5 claimed to wire `FastAPI(version=…)` to the package version but it stayed a hardcoded string literal. Now imported from `__init__.__version__` so the OpenAPI/Swagger UI version moves in lockstep with `pyproject.toml`.

### Testing
- **240 tests total**. 14 new ticker-resolver tests cover the Yahoo Search path (currency/country preference, non-equity filtering, exceptions, manual-override precedence, and currency/country map coverage). Two new regression tests cover NaN-close skipping (`fetch_stock_prices`) and NULL-close masking (`/api/holdings`).

### Docs
- `TICKER_RESOLUTION.md` and `docs/data-providers.md`: documented the new Yahoo Search resolver, currency/country suffix preference, supported markets, manual overrides, and the migration snippet for forcing a re-resolve.

### CI
- Added `timeout-minutes` to every job in `ci.yml` and `publish.yml`. The default GitHub Actions job timeout is 6h, so a stuck runner on the Playwright install step could silently burn hours before failing. Test jobs now cap at 15 min, build/publish at 10 min, lint at 5 min.

## [0.5.6] - 2026-05-10

### Fixed
- **Import crash on stocks sharing a product-name prefix (`UNIQUE constraint failed: stocks.symbol`)**: `Stock.symbol` is a display label derived from the first word of the DEGIRO product name, but the column was declared `UNIQUE`. Two iShares ETFs (or two Vanguard ETFs, etc.) with different ISINs both resolved to the same first word and the second insert failed, aborting the import. Removed the bogus uniqueness — ISIN already uniquely identifies a stock — and added an automatic SQLite migration in `init_db()` that rebuilds the legacy `ix_stocks_symbol` UNIQUE index as a plain index on existing databases at startup.

### Testing
- **226 tests total**, full parallel suite green. Two new regressions: importing two iShares ETFs that share a derived symbol, and the migration converting a legacy UNIQUE index in place.

## [0.5.5] - 2026-04-14

### Fixed
- **Event-loop starvation under load (production bug)**: 14 FastAPI endpoints were declared `async def` while doing sync blocking I/O (yfinance HTTP calls, SQLAlchemy queries). A single slow upstream call froze uvicorn's event loop, queuing every concurrent request — including the HTML page — until it completed. Converted all non-awaiting endpoints to plain `def` so FastAPI runs them in a threadpool. Eliminates 30s `page.goto` timeouts seen under parallel test load and prevents the same freeze under real user load with slow upstream APIs.
- **FastAPI `app.version`**: was stuck at `"0.4.0"`, now tracks `pyproject.toml` version.

### Testing
- **Coverage for `main.py`: 72% → 89%** (+115 lines). Added 13 targeted unit tests covering upload pipeline (new-stock insert, duplicate skip, held-stock filtering, FMP live-price branch, index update exceptions), exchange-rate Yahoo fallback paths, `update-market-data` ticker auto-resolve and Yahoo fallback, `refresh-live-prices` error branches, purge/shutdown error paths, and `ensure_indices_exist` rollback.
- **Playwright fixture flakiness eliminated**: switched `page.goto` to `wait_until="domcontentloaded"` in shared_page, CSV, and Dutch e2e fixtures. Combined with the event-loop fix, the full suite now passes 5/5 consecutive parallel runs (was 2–3/5 before).
- **224 tests total**, stable across 5 consecutive parallel runs.

## [0.5.4] - 2026-04-10

### Fixed
- **Dutch DEGIRO Import**: 18-column format now uses positional mapping (like 14-column), so Dutch, German, and all other language exports work without requiring English column names
- **Desktop App Crash**: Removed unsupported `icon` kwarg from `webview.create_window()`

### Testing
- **Dutch E2E Tests**: New test module uploads a Dutch 18-column Excel file and validates import, stock card display, chart loading, and no JS errors
- **Desktop Unit Tests**: Verify `create_window()` only passes supported kwargs
- **211 tests total**, stable across 3 consecutive parallel runs

## [0.5.3] - 2026-04-10

### Fixed
- **Desktop App Crash**: Removed unsupported `icon` kwarg from `webview.create_window()` that caused `TypeError` on startup

### Testing
- **Desktop Unit Tests**: New tests verify `create_window()` only passes supported kwargs (prevents regressions), and checks window title/dimensions
- **207 tests total**

## [0.5.2] - 2026-04-10

### Added
- **Desktop App Icon**: 256x256 PNG icon displayed in macOS dock and Windows taskbar when running in desktop mode
- **Release Notes in Docs**: New release-notes page in Sphinx docs, auto-included from CHANGELOG.md
- **README Improvements**: readthedocs and PyPI badges, links to full documentation and release notes, updated DEGIRO export instructions with CSV support and transactions URL

### Fixed
- **Flaky Test Timeouts**: Increased server startup retries (20→40) and page navigation timeout (10s→15s) for parallel xdist workers

## [0.5.1] - 2026-04-10

### Changed
- **Clean Console Output**: Replaced all `print()` diagnostic messages with Python `logging` across fetch_prices.py, price_fetchers.py, fetch_indices.py, import_data.py, and main.py. Users now see a clean console by default — debug details only appear when logging is set to DEBUG level

## [0.5.0] - 2026-04-10

### Added
- **Server-Side Portfolio Summary**: New `/api/portfolio-summary` endpoint computes net invested, current value, and gain/loss in a single query — replaces 2N client-side API calls
- **Date Parsing with dateutil**: Replaced manual `strptime` format loop with `dateutil.parser.parse(dayfirst=True)` for robust parsing of any date format
- **Test Coverage**: 205 tests total (up from 160), 73% code coverage (up from 31%). New tests for fetch_prices fallback logic, price_fetcher normalization, ticker resolver paths, import_data in-process, and main.py TestClient endpoints

### Changed
- **Faster UI Startup**: Exchange rates and holdings fetch in parallel; portfolio summary and valuation chart load in parallel; live price refresh is non-blocking
- **Loading Status Feedback**: Status indicator shows "Loading holdings..." → "Loading charts..." → live prices update in background instead of a static "Loading portfolio data..." message

### Fixed
- **Startup Responsiveness**: Portfolio summary no longer blocks UI with sequential per-stock API calls

## [0.4.4] - 2026-04-10

### Fixed
- **Null Price JS Crash**: `formatPrice()` now guards against null values, preventing "null is not an object" errors when stocks have no price data yet
- **Chart Rendering**: `renderStats()` and `renderChart()` filter null close values before rendering; show helpful message instead of crashing
- **Portfolio Summary**: Current value calculation skips stocks with null prices instead of producing NaN
- **Chart Data Query**: Server-side SQL now excludes price records with null close values

### Changed
- **Upload Performance**: Only fetches historical prices for currently held stocks (net qty > 0), skipping sold positions — much faster for large transaction files

### Testing
- **160 tests total**: 15 E2E Playwright tests for CSV import covering holdings, all API endpoints, chart rendering per stock, JS error detection, and error banner checking

## [0.4.3] - 2026-04-10

### Fixed
- **Chart Data Crash**: Fixed `TypeError: NoneType` in chart-data, index normalization, position value, and portfolio performance endpoints when price records have null close values
- **Upload Stalling**: Upload now only fetches historical prices for currently held stocks (net qty > 0), not every stock that appears in any transaction — dramatically faster for large transaction files with many sold positions

### Testing
- **157 tests total** (up from 151): 6 new E2E API tests for chart-data, transactions, portfolio-performance, valuation-history, market-data-status, and stock-prices endpoints against CSV import data

## [0.4.2] - 2026-04-10

### Added
- **CSV File Support**: Upload CSV exports (`.csv`) alongside Excel files (`.xlsx`, `.xls`) — both via UI and CLI import
- **18-Column DEGIRO Format**: Supports the newer 18-column DEGIRO transaction export (maps by column name, drops extra columns like AutoFX Fee and Local value)
- **DEGIRO Transactions Link**: App header and docs now link to [trader.degiro.nl/trader/#/transactions](https://trader.degiro.nl/trader/#/transactions) for easy export
- **E2E CSV Import Test**: 6 Playwright tests validate CSV upload against displayed holdings (stock count, share counts, transaction counts, ignored stocks)

### Fixed
- **Upload Crash**: Fixed `NameError: name 'time_str' is not defined` in upload endpoint when creating transactions
- **Docs**: Updated Getting Started with CSV support, DEGIRO export URL, and file format details

### Testing
- **151 tests total** (up from 144): 6 new E2E CSV import tests, 1 new 18-column config unit test

## [0.4.1] - 2026-04-10

### Changed
- **Position-Based Column Mapping**: DEGIRO exports are now mapped by column position instead of column name, making imports work with any language (English, Dutch, German, etc.) without per-language mappings
- **Simplified Config**: Removed language-detection machinery (`detect_and_set_column_mapping`, `normalize_dataframe_columns`, Dutch column mapping) in favour of a single `normalize_degiro_columns` method

### Fixed
- **Date Parsing**: `parse_date()` now handles pandas Timestamps (auto-parsed by `read_excel`), plus multiple string formats (DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD) instead of only DD-MM-YYYY
- **Upload Endpoint**: Uses shared `parse_date()` and position-based column normalization, matching the CLI import behaviour
- **Holdings API Crash**: Fixed `TypeError` in `/api/holdings` when `latest_price` is `None` (e.g. stocks with no historical price data)

### Testing
- **Updated Config Tests**: Rewrote `test_config_unit.py` to match new position-based API (10 tests, 144 total)

## [0.4.0] - 2026-04-09

### Added
- **Desktop Application Mode**: New native desktop app using pywebview — launch with `python -m degiro_portfolio --desktop`. Opens in a native window (WebKit on Mac, WebView2 on Windows) with no browser needed. Server starts and stops automatically with the window
- **`desktop.py` module**: Multiprocessing server management, pywebview window lifecycle, graceful shutdown via `/api/shutdown` endpoint
- **`degiro-portfolio-desktop` console script**: Direct entry point for desktop mode
- **`--desktop` and `--port` CLI flags**: `python -m degiro_portfolio --desktop --port 8001`
- **`/api/shutdown` endpoint**: Graceful server shutdown (used by desktop mode window close and Ctrl-C)
- **`pywebview` included in base install**: Desktop mode works out of the box with `pip install degiro_portfolio`

### Changed
- **Documentation rewritten**: Desktop app is now the primary recommended way to use the application. Web server mode documented as the alternative
- **README**: Quick Start leads with desktop mode installation and launch
- **Getting Started**: Desktop app is Step 1, web server mode is under "Alternative"

## [0.3.10] - 2026-04-08

### Added
- **Windows Support**: CLI script and test suite now work on Windows — platform-conditional subprocess creation and signal handling replace Unix-only `os.setsid`, `os.killpg`, and `signal.SIGKILL`
- **Windows Documentation**: Added Windows-specific instructions to Getting Started, Advanced Setup (PowerShell, cmd.exe, background execution, Task Scheduler)

### Changed
- **Yahoo Finance Only**: Removed Twelve Data and FMP provider documentation and configuration — Yahoo Finance is now the sole supported provider
- **Simplified .env.example**: Removed Twelve Data and FMP API key references
- **Deleted TWELVEDATA_SETUP.md**: No longer needed

### Fixed
- **Windows CLI Crash**: `degiro_portfolio start/stop` no longer crashes on Windows with `ValueError: start_new_session is not supported`
- **Windows Test Suite**: `tests/conftest.py` server fixture no longer uses Unix-only `preexec_fn=os.setsid` on Windows
- **Data Provider Docs Contradiction**: Getting Started page no longer says both "Yahoo is default" and "Twelve Data is default"

## [0.3.9] - 2026-04-08

### Changed
- **Default Price Provider**: Switched from Twelve Data to Yahoo Finance as the default price data provider in `.env` — Yahoo requires no API key and provides better European stock coverage
- **Parallel Test Workers**: Reduced pytest-xdist workers from 4 to 2 for optimal performance with fewer server startup overhead

### Fixed
- **Ticker Resolver Crash**: Fixed `AttributeError` in `resolve_ticker_from_isin()` when ISIN is `None`
- **Playwright Test Timeouts**: Fixed all playwright tests timing out because the page's JavaScript called `/api/refresh-live-prices` on load, blocking the single-threaded test server with external API calls for 30+ seconds. Resolved by intercepting blocking API endpoints at the browser context level
- **Test DB Teardown Race**: Fixed workers deleting the shared master test database while other workers were still using it — only the controller now cleans up shared files

### Testing
- **Performance**: Test suite runtime reduced from ~97s to ~62s (36% faster)
- **Database Caching**: Master test database is now cached between runs using SHA-256 hash of input files — only rebuilt when source code or test data changes
- **Mocked API Tests**: Three slow unit tests (`test_update_market_data_endpoint`, `test_refresh_live_prices_endpoint`, `test_ensure_indices_exist_function`) now mock external API calls instead of hitting Yahoo Finance for all 11 stocks
- **New Tests** (7 added, 133 total):
  - `__main__.py` CLI entry point (0% → 86% coverage)
  - `_get_fallback_rate()` exchange rate fallbacks
  - `GET /api/exchange-rates` endpoint
  - `POST /api/purge-database` endpoint via TestClient
  - Uptime string formatting branches
  - Real yfinance smoke test (single AAPL call verifies API integration)
- **Regression Tests for Issue #1**: 8 tests covering `python -m degiro_portfolio` execution, Dutch column auto-detection, English column whitespace handling, and column validation
- **Coverage**: 70% across all modules (141 tests total)
- **Skipped Real API Calls**: Test database creation no longer fetches real stock prices — uses mock data exclusively, eliminating Twelve Data rate limit errors during tests

## [0.3.0] - 2026-01-15

### Added
- **Auto-Refreshing Stock Charts**: Stock price charts now automatically refresh every minute to show the latest data
- **Portfolio Valuation Timeline Extension**: Portfolio Total Value Over Time chart now always extends to today's date, not just the last price update
- **Latest Date Annotation**: Portfolio valuation chart displays the most recent date in the top-right corner for easy reference
- **Automatic Market Index Loading**: Market indices (S&P 500, Euro Stoxx 50) are now automatically fetched when uploading transactions
- **Comprehensive Test Suite**: Added 55+ unit tests across core modules (fetch_prices, fetch_indices, price_fetchers, ticker_resolver, main API endpoints)
- **Test Coverage Reporting**: New invoke tasks for coverage reports (`test-cov`, `test-cov-html`)
- **Test Organization**: Separated unit tests (`test-unit`) from integration tests (`test-integration`) for faster feedback

### Changed
- **Transaction Marker Positioning**: Buy/sell markers now align with candlestick high/low prices instead of transaction prices, fixing alignment issues caused by stock splits
- **Chart Refresh Interval Management**: Each stock chart properly clears previous refresh intervals when switching stocks

### Fixed
- **Portfolio Chart End Date**: Fixed issue where portfolio valuation chart would stop at the last price update instead of extending to today
- **Transaction Marker Alignment**: Fixed misalignment of transaction markers on stocks with splits (e.g., ASML) by positioning markers at actual candlestick prices
- **Chart Auto-Refresh**: Properly manages refresh intervals to prevent memory leaks and duplicate refreshes

### Testing
- **Test Coverage**: Achieved 70% code coverage (116 passing tests)
- **Unit Test Coverage**:
  - main.py: API endpoints and server functionality
  - fetch_indices.py: Market index data fetching
  - fetch_prices.py: Stock price data fetching
  - price_fetchers.py: Price provider implementations
  - ticker_resolver.py: ISIN to ticker mapping
- **Integration Test Coverage**: All browser-based UI tests passing

### Documentation
- Updated README.md with new features (auto-refresh, test coverage, new invoke tasks)
- Enhanced testing section with coverage information and test organization
- Added changelog entry for version 0.3.0

## [0.2.0] - 2026-01-12

### Added
- **Live Price Updates on Stock Cards**: Stock cards now display the latest closing price with daily percentage change (green ▲ for gains, red ▼ for losses)
- **Market Data Status Display**: Shows the most recent market data update date below the "Update Market Data" button
- **Clickable Company Names**: Company names link to Google search for investor relations information
- **Clickable Ticker Symbols**: Yahoo Finance ticker symbols link directly to corresponding Google Finance pages
- **Exchange Information**: Each stock card now displays the exchange where the stock is traded
- **New API Endpoint**: `GET /api/market-data-status` returns the latest market data update date
- **Enhanced Holdings API**: `/api/holdings` now includes latest_price, price_change_pct, and price_date for each stock

### Changed
- **Compact UI Design**: Reduced font sizes throughout the application for more efficient use of screen space
  - Smaller headers, buttons, labels, and values
  - Tighter spacing and padding
  - More stocks visible without scrolling
- **Uniform Transaction Markers**: Buy/sell markers on charts are now consistent size (14px) instead of varying by quantity
- **Improved Marker Visibility**: Transaction markers have better opacity (0.9) and cleaner borders for easier identification
- **Currency-Aware Charts**: Transaction markers only display when currency matches price data currency, preventing misaligned markers
- **Portfolio Summary Condensed**: More compact layout with smaller fonts and reduced padding
- **Update Market Data**: Now only fetches prices for currently held stocks (ignores sold positions)

### Fixed
- **SAAB Currency Correction**: Fixed SAAB AB currency from EUR to SEK to match Stockholm Exchange pricing
- **ASML Ticker Correction**: Updated ASML ticker from "ASML" (NASDAQ/USD) to "ASML.AS" (Amsterdam/EUR) to match transaction currency
- **Transaction Marker Alignment**: Fixed "floating markers" issue where markers appeared detached from price chart due to currency mismatches
- **Upload Error Handling**: Fixed date/time parsing for DEGIRO transaction files with separate Date and Time columns
- **Auto-refresh Clarity**: Improved upload status messages to clearly indicate automatic page refresh after data updates
- **Active Stock Highlight**: Changed from hard-to-read blue gradient to light green background for better text contrast

### Documentation
- Updated README.md with new features and enhanced feature descriptions
- Created CHANGELOG.md to track version history
- Updated API endpoint documentation
- Added notes about clickable links and compact design

### Example Data
- Extended example_data.xlsx to include European Tech Stocks alongside US AI stocks:
  - ASML (Netherlands) - Semiconductor equipment
  - SAP (Germany) - Enterprise software
  - Infineon (Germany) - Semiconductors
  - Nokia (Finland) - Telecommunications
  - Ericsson (Sweden) - Telecommunications
  - STMicroelectronics (France) - Semiconductors
- Total example transactions increased from 14 to 28
- Demonstrates multi-currency support (EUR, USD, SEK) and multi-exchange functionality

## [0.1.0] - 2025-01-XX

### Initial Release
- DEGIRO transaction import from Excel
- Historical stock price fetching via Yahoo Finance
- Interactive candlestick charts with transaction markers
- Investment tranche tracking
- Position value percentage charts
- Market index comparison (S&P 500, Euro Stoxx 50)
- Multi-currency support (EUR, USD, SEK)
- Web-based portfolio viewer
- Upload transactions via web interface
- One-click market data updates
