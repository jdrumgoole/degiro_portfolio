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


def _wait_for_ready(host: str, port: int, timeout_s: float = 20.0) -> bool:
    """Poll /api/ping until the server responds or timeout elapses."""
    url = f"http://{host}:{port}/api/ping"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.25)
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
    server_process = subprocess.Popen(server_cmd, **popen_kwargs)

    # Wait for the server to be ready
    print(f"Starting DEGIRO Portfolio on {url} ...")
    if not _wait_for_ready(host, port):
        print("Warning: server may not be ready yet", file=sys.stderr)

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

    # Run the window event loop (blocks until window closes).
    # `func` runs in a thread after GUI initialization.
    webview.start(func=_signal_watcher)

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
