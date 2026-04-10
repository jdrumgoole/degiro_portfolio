"""Desktop application wrapper using pywebview.

Runs the FastAPI server in a child process and displays it in a native
window with an embedded browser (WebKit on macOS, WebView2 on Windows).
"""

from __future__ import annotations

import multiprocessing
import signal
import sys
import time
import urllib.error
import urllib.request


def _run_server(host: str, port: int, ready_event: multiprocessing.Event) -> None:
    """Entry point for the server child process."""
    import asyncio
    import uvicorn

    # Ignore SIGINT in the child — the parent handles shutdown
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    config = uvicorn.Config(
        "degiro_portfolio.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    async def _serve() -> None:
        await server.serve()

    # Signal readiness once the server is accepting connections
    def _poll_until_ready() -> None:
        url = f"http://{host}:{port}/api/ping"
        for _ in range(80):  # up to 20 seconds
            time.sleep(0.25)
            try:
                urllib.request.urlopen(url, timeout=1)
                ready_event.set()
                return
            except (urllib.error.URLError, ConnectionError, OSError):
                continue
        # Timed out — set anyway so the parent doesn't hang
        ready_event.set()

    import threading
    threading.Thread(target=_poll_until_ready, daemon=True).start()

    asyncio.run(_serve())


def run_desktop(*, port: int = 8000) -> None:
    """Launch DEGIRO Portfolio as a desktop application.

    Starts the FastAPI server in a child process and opens a native
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
            f"Use a different port: python -m degiro_portfolio --desktop --port {port + 1}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Start the server in a child process
    ready_event = multiprocessing.Event()
    server_process = multiprocessing.Process(
        target=_run_server,
        args=(host, port, ready_event),
        daemon=True,
    )
    server_process.start()

    # Wait for the server to be ready
    print(f"Starting DEGIRO Portfolio on {url} ...")
    if not ready_event.wait(timeout=20):
        print("Warning: server may not be ready yet", file=sys.stderr)

    # Resolve icon path
    import os
    icon_path = os.path.join(os.path.dirname(__file__), "static", "icon-256.png")

    # Create the native window
    window_kwargs = dict(
        title="DEGIRO Portfolio",
        url=url,
        width=1280,
        height=900,
        min_size=(800, 600),
    )
    if os.path.exists(icon_path):
        window_kwargs["icon"] = icon_path

    window = webview.create_window(**window_kwargs)

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

    # Handle Ctrl-C: close the window which triggers _on_closing
    def _sigint_handler(signum: int, frame: object) -> None:
        print("\nShutting down...", file=sys.stderr)
        try:
            window.destroy()
        except Exception:
            pass

    signal.signal(signal.SIGINT, _sigint_handler)

    # Run the window event loop (blocks until window closes)
    webview.start()

    # Clean up the server process
    if server_process.is_alive():
        server_process.terminate()
        server_process.join(timeout=5)
        if server_process.is_alive():
            server_process.kill()

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
