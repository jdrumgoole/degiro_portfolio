"""Desktop application wrapper using pywebview.

Runs the FastAPI server in a child process (via subprocess) and displays it
in a native window with an embedded browser (WebKit on macOS, WebView2 on
Windows).

We deliberately avoid `multiprocessing.Process` / `multiprocessing.Event`
here. On macOS / Linux those allocate POSIX semaphores tracked by
`multiprocessing.resource_tracker`, and an abrupt Ctrl-C interrupts the
parent's shutdown before the tracker can release them, producing
"leaked semaphore objects" warnings at exit. A plain subprocess has no
such bookkeeping and survives Ctrl-C cleanly.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


APP_NAME = "DEGIRO Portfolio"


def _log(message: str) -> None:
    """Print a timestamped diagnostic line to stderr."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def _icon_path() -> "str | None":
    """Return the absolute path to the bundled app icon, if present.

    Prefer the squircle-clipped variant so the dock doesn't show sharp
    corners on macOS Big Sur+. Fall back to the flat 256×256 PNG.
    """
    from pathlib import Path
    static = Path(__file__).parent / "static"
    for name in ("icon-256-rounded.png", "icon-256.png"):
        candidate = static / name
        if candidate.exists():
            return str(candidate)
    return None


def _ensure_macos_app_bundle() -> "str | None":
    """Create a minimal .app bundle under ~/Library/Application Support and
    return the path to the bundled executable symlink, or None if not on
    macOS / not possible.

    Why: re-execing through a bundle gives the app a proper Info.plist
    context, which gets us:
      - menu bar reads "DEGIRO Portfolio" (CFBundleName)
      - Activity Monitor / Force Quit show "DEGIRO Portfolio"
        (NSProcessInfo.processName works once NSBundle has bundle context)
      - app identity in the bundle is set correctly for NSBundle queries

    KNOWN LIMITATION — the Dock hover tooltip still shows "python3.10":
    macOS records the *resolved* binary path at exec time, and our bundle
    executable is a symlink to the pyenv python binary. After symlink
    resolution the kernel sees "python3.10". Neither CFBundleName nor
    NSProcessInfo.processName overrides this for the Dock tooltip. The
    only fixes are (a) ship a compiled C launcher named "DEGIRO Portfolio"
    that dlopen's libpython directly, or (b) ship a full py2app/briefcase
    bundle. Both are out of scope for a pip-installed package.
    """
    if sys.platform != "darwin":
        return None
    from pathlib import Path
    bundle_root = Path.home() / "Library" / "Application Support" / APP_NAME / f"{APP_NAME}.app"
    macos_dir = bundle_root / "Contents" / "MacOS"
    plist_path = bundle_root / "Contents" / "Info.plist"
    exec_path = macos_dir / APP_NAME

    try:
        macos_dir.mkdir(parents=True, exist_ok=True)
        # Always refresh the symlink — sys.executable can change between
        # virtualenvs / Python upgrades, and a stale symlink to a deleted
        # interpreter would re-exec into nothing.
        target = Path(sys.executable).resolve()
        if exec_path.is_symlink() or exec_path.exists():
            if not exec_path.is_symlink() or Path(os.readlink(exec_path)).resolve() != target:
                exec_path.unlink()
        if not exec_path.exists():
            exec_path.symlink_to(target)
        if not plist_path.exists():
            plist_path.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0">\n'
                '<dict>\n'
                f'    <key>CFBundleName</key><string>{APP_NAME}</string>\n'
                f'    <key>CFBundleDisplayName</key><string>{APP_NAME}</string>\n'
                f'    <key>CFBundleExecutable</key><string>{APP_NAME}</string>\n'
                '    <key>CFBundleIdentifier</key><string>com.degiro.portfolio</string>\n'
                '    <key>CFBundlePackageType</key><string>APPL</string>\n'
                '    <key>CFBundleVersion</key><string>1.0</string>\n'
                '    <key>NSHighResolutionCapable</key><true/>\n'
                '</dict>\n'
                '</plist>\n'
            )
        return str(exec_path)
    except Exception as e:
        _log(f"bundle creation failed: {e}")
        return None


def _reexec_via_macos_bundle_if_needed() -> None:
    """If we're not already running from inside the .app bundle, re-exec
    through it so NSApp picks up the bundled Info.plist (and thus the
    proper Dock tooltip and identity).

    Guarded by an env var to prevent recursion if the re-exec itself fails
    or if something goes wrong with the bundle.
    """
    if sys.platform != "darwin":
        return
    if os.environ.get("_DEGIRO_BUNDLED") == "1":
        return  # already inside the bundle, no further re-exec

    exec_path = _ensure_macos_app_bundle()
    if not exec_path:
        return

    # Recursion guard is purely the env var — the bundle symlink resolves
    # to the same underlying python binary as sys.executable, so a path
    # comparison would always say "same" and the re-exec would be skipped.
    os.environ["_DEGIRO_BUNDLED"] = "1"
    # argv[0] becomes the bundle path so macOS records the bundle as the
    # executable. Subsequent argv entries preserve user-supplied flags.
    new_argv = [exec_path] + sys.argv
    os.execv(exec_path, new_argv)


def _set_macos_bundle_name() -> None:
    """Override the app name shown in the menu bar, Dock tooltip, and
    Activity Monitor / Force Quit dialog.

    Three knobs need to be set in lockstep on a non-bundled Python app:
      - CFBundleName / CFBundleDisplayName: drive the menu-bar name.
      - NSProcessInfo.processName: drives the Dock tooltip and Activity
        Monitor entry (without this they fall back to "python3.10").
    """
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle, NSProcessInfo
    except ImportError:
        _log("Foundation unavailable, skipping menu-bar name override")
        return
    try:
        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = APP_NAME
        info["CFBundleDisplayName"] = APP_NAME
    except Exception as e:
        _log(f"failed to set CFBundleName: {e}")
    try:
        NSProcessInfo.processInfo().setProcessName_(APP_NAME)
    except Exception as e:
        _log(f"failed to set process name: {e}")


def _set_macos_dock_icon(icon_file: "str | None") -> None:
    """Apply `icon_file` as the dock icon for this process.

    Must be called *after* pywebview has set up NSApplication (otherwise
    pywebview's internal init overwrites the icon with macOS's default).
    Hook this to `window.events.shown` so it runs on the GUI thread once
    the window is visible.
    """
    if sys.platform != "darwin" or not icon_file:
        return
    try:
        from AppKit import NSApplication, NSImage
    except ImportError:
        _log("AppKit unavailable, skipping dock icon")
        return
    try:
        image = NSImage.alloc().initWithContentsOfFile_(icon_file)
        if image is None:
            _log(f"NSImage failed to load icon at {icon_file}")
            return
        NSApplication.sharedApplication().setApplicationIconImage_(image)
        _log(f"dock icon set from {icon_file}")
    except Exception as e:
        _log(f"failed to set dock icon: {e}")


def _probe(url: str, timeout_s: float = 1.0) -> bool:
    """Return True iff `url` responds with HTTP 2xx within `timeout_s`."""
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, ConnectionError, OSError):
        return False


def _wait_for_ready(host: str, port: int, timeout_s: float = 30.0) -> bool:
    """Wait until the server is fully warm before showing the GUI.

    Two phases:
      1. /api/ping — uvicorn event loop accepting connections.
      2. /api/holdings — forces FastAPI to fully initialise (SQLAlchemy
         session factory, pandas / yfinance lazy imports). On first launch
         after install this is what costs multiple seconds; opening the
         pywebview window before /api/holdings is warm leaves the embedded
         WKWebView's initial XHRs stalled and the whole window appears
         frozen.
    """
    ping_url = f"http://{host}:{port}/api/ping"
    holdings_url = f"http://{host}:{port}/api/holdings"
    deadline = time.monotonic() + timeout_s

    # Phase 1: socket accepting + uvicorn loop alive
    ping_started = time.monotonic()
    while time.monotonic() < deadline:
        if _probe(ping_url):
            _log(f"server accepting connections (uvicorn up) in {time.monotonic() - ping_started:.2f}s")
            break
        time.sleep(0.25)
    else:
        _log("timed out waiting for /api/ping")
        return False

    # Phase 2: FastAPI app fully initialised (heavy imports done)
    holdings_started = time.monotonic()
    while time.monotonic() < deadline:
        if _probe(holdings_url, timeout_s=5.0):
            _log(f"server fully warm (/api/holdings responsive) in {time.monotonic() - holdings_started:.2f}s")
            return True
        time.sleep(0.25)

    _log("timed out waiting for /api/holdings")
    return False


def run_desktop(*, port: int = 8000) -> None:
    """Launch DEGIRO Portfolio as a desktop application.

    Starts the FastAPI server in a child subprocess and opens a native
    window with pywebview pointing at it.
    """
    try:
        import webview
    except ImportError:
        print(
            "Error: pywebview is required for desktop mode.\n"
            "Install it with: pip install pywebview",
            file=sys.stderr,
        )
        sys.exit(1)

    host = "127.0.0.1"
    url = f"http://{host}:{port}/"

    # Check port availability before starting
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if sys.platform != "win32":
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
    except OSError:
        print(
            f"Error: port {port} is already in use.\n"
            f"Use a different port: degiro-portfolio-desktop --port {port + 1}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Start the server in a child subprocess. Using sys.executable + uvicorn
    # ensures we run inside the same Python environment without depending on
    # `uv` or `uvicorn` being on PATH.
    server_cmd = [
        sys.executable, "-m", "uvicorn",
        "degiro_portfolio.main:app",
        "--host", host,
        "--port", str(port),
        "--log-level", "warning",
    ]
    popen_kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.STDOUT,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # New session so SIGINT in our terminal doesn't propagate to the
        # uvicorn child — we want to shut it down ourselves.
        popen_kwargs["start_new_session"] = True
    _log(f"spawning server subprocess on {host}:{port}")
    server_process = subprocess.Popen(server_cmd, **popen_kwargs)
    _log(f"subprocess PID {server_process.pid} started, waiting for readiness")

    # Wait for the server to be ready
    print(f"Starting DEGIRO Portfolio on {url} ...")
    if not _wait_for_ready(host, port):
        print("Warning: server may not be ready yet", file=sys.stderr)

    # Menu-bar name: must be set before NSApplication is referenced, so it
    # goes here, before webview.create_window.
    _set_macos_bundle_name()

    _log("creating pywebview window")
    # Create the native window
    window = webview.create_window(
        APP_NAME,
        url,
        width=1280,
        height=900,
        min_size=(800, 600),
    )

    def _on_closing() -> None:
        """Shut down the server when the window closes."""
        try:
            urllib.request.urlopen(
                urllib.request.Request(f"{url}api/shutdown", method="POST"),
                timeout=2,
            )
        except Exception:
            pass

    window.events.closing += _on_closing

    # Re-apply the dock icon after pywebview has set up NSApplication.
    # Setting it before webview.start() runs gets overwritten by pywebview's
    # internal init; events.shown fires after the window is visible and
    # NSApp is stable.
    icon_file = _icon_path()
    if icon_file:
        window.events.shown += lambda: _set_macos_dock_icon(icon_file)

    # Handle Ctrl-C reliably even though pywebview's native GUI loop blocks
    # the main thread (preventing Python signal handlers from running
    # promptly). Use the self-pipe trick: signal.set_wakeup_fd causes the
    # kernel to write the signal number to a pipe on delivery; a worker
    # thread select()s on the pipe and reacts. window.destroy() is
    # thread-safe and unblocks webview.start() from the GUI thread.
    import select

    _signal_r, _signal_w = os.pipe()
    os.set_blocking(_signal_r, False)
    os.set_blocking(_signal_w, False)

    # Install a no-op handler so set_wakeup_fd actually triggers (Python
    # only writes to the wakeup fd when a signal has a handler installed,
    # not when it's SIG_DFL/SIG_IGN).
    signal.signal(signal.SIGINT, lambda *_: None)
    signal.signal(signal.SIGTERM, lambda *_: None)
    signal.set_wakeup_fd(_signal_w)

    def _signal_watcher() -> None:
        """Block in a worker thread until a signal arrives, then tear down."""
        select.select([_signal_r], [], [])
        print("\nShutting down...", file=sys.stderr)
        _on_closing()  # POST /api/shutdown so the server exits cleanly
        try:
            window.destroy()
        except Exception:
            pass

    _log("entering pywebview event loop (webview.start)")
    # Run the window event loop (blocks until window closes).
    # `func` runs in a thread after GUI initialization.
    webview.start(func=_signal_watcher)
    _log("pywebview event loop exited")

    # Clean up the server process
    if server_process.poll() is None:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait(timeout=2)

    print("DEGIRO Portfolio closed.")


def main() -> None:
    """Entry point for the degiro-portfolio-desktop command."""
    # Re-exec through a .app bundle on macOS so the Dock tooltip and other
    # identity strings come from a real Info.plist instead of "python3.10".
    # This MUST run before any other initialization (no imports of webview,
    # no logging, no NSApplication references) because os.execv replaces
    # the entire process image.
    _reexec_via_macos_bundle_if_needed()

    import argparse
    parser = argparse.ArgumentParser(description="DEGIRO Portfolio Desktop")
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for the backend server (default: 8000)",
    )
    args = parser.parse_args()
    run_desktop(port=args.port)


if __name__ == "__main__":
    main()
