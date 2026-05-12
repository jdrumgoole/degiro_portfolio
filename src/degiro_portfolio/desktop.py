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

import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _log(message: str) -> None:
    """Print a timestamped diagnostic line to stderr."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


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

    _log("creating pywebview window")
    # Create the native window
    window = webview.create_window(
        "DEGIRO Portfolio",
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

    # Handle Ctrl-C reliably even though pywebview's native GUI loop blocks
    # the main thread (preventing Python signal handlers from running
    # promptly). Use the self-pipe trick: signal.set_wakeup_fd causes the
    # kernel to write the signal number to a pipe on delivery; a worker
    # thread select()s on the pipe and reacts. window.destroy() is
    # thread-safe and unblocks webview.start() from the GUI thread.
    import os
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
