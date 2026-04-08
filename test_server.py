#!/usr/bin/env python3
"""
Test server management script for DEGIRO Portfolio.
Allows running multiple server instances with different databases and ports.
"""
import os
import sys
import signal
import platform
import subprocess
import time
import argparse
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"


class ServerManager:
    """Manage server instances."""

    def __init__(self, port=8001, database="degiro_portfolio_test.db"):
        self.port = port
        self.database = database
        self.project_root = Path(__file__).parent
        self.db_path = self.project_root / database
        self.pid_file = self.project_root / f".degiro_portfolio_test-{port}.pid"
        self.log_file = self.project_root / f"degiro_portfolio_test-{port}.log"

    def start(self):
        """Start the test server."""
        # Check if already running
        if self.is_running():
            pid = self.get_pid()
            print(f"❌ Server already running on port {self.port} (PID: {pid})")
            return False

        print(f"🚀 Starting test server...")
        print(f"   Port: {self.port}")
        print(f"   Database: {self.db_path}")
        print(f"   Log file: {self.log_file}")

        # Set environment variable for database
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{self.db_path}"
        env["PYTHONPATH"] = str(self.project_root)

        # Start uvicorn server
        cmd = [
            "uv", "run", "python", "-m",
            "uvicorn",
            "src.degiro_portfolio.main:app",
            "--host", "0.0.0.0",
            "--port", str(self.port)
        ]

        with open(self.log_file, 'w') as log:
            popen_kwargs = dict(
                cwd=self.project_root, env=env,
                stdout=log, stderr=subprocess.STDOUT
            )
            if IS_WINDOWS:
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True
            process = subprocess.Popen(cmd, **popen_kwargs)

        # Save PID
        with open(self.pid_file, 'w') as f:
            f.write(str(process.pid))

        # Wait a moment and check if server started
        time.sleep(3)

        if self.is_running():
            print(f"✅ Server started successfully")
            print(f"   PID: {process.pid}")
            print(f"   URL: http://localhost:{self.port}")
            print(f"   Logs: {self.log_file}")
            return True
        else:
            print(f"❌ Server failed to start")
            print(f"   Check logs: {self.log_file}")
            # Show last few lines of log
            if self.log_file.exists():
                with open(self.log_file) as f:
                    lines = f.readlines()
                    print("\n   Last log lines:")
                    for line in lines[-10:]:
                        print(f"   {line.rstrip()}")
            return False

    def stop(self):
        """Stop the test server."""
        if not self.is_running():
            print(f"ℹ️  Server not running on port {self.port}")
            return True

        pid = self.get_pid()
        print(f"🛑 Stopping server (PID: {pid})...")

        try:
            os.kill(pid, signal.SIGTERM)

            # Wait for process to stop
            for _ in range(10):
                time.sleep(0.5)
                if not self.is_running():
                    break

            if self.is_running():
                # Force kill if still running
                print(f"   Force killing...")
                if IS_WINDOWS:
                    os.kill(pid, signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGKILL)
                time.sleep(1)

            # Remove PID file
            if self.pid_file.exists():
                self.pid_file.unlink()

            print(f"✅ Server stopped")
            return True

        except ProcessLookupError:
            print(f"⚠️  Process not found, cleaning up PID file")
            if self.pid_file.exists():
                self.pid_file.unlink()
            return True
        except Exception as e:
            print(f"❌ Error stopping server: {e}")
            return False

    def status(self):
        """Check server status."""
        if self.is_running():
            pid = self.get_pid()
            print(f"✅ Server is running")
            print(f"   PID: {pid}")
            print(f"   Port: {self.port}")
            print(f"   Database: {self.db_path}")
            print(f"   URL: http://localhost:{self.port}")
            print(f"   Logs: {self.log_file}")

            # Show recent logs
            if self.log_file.exists():
                print(f"\n📋 Recent logs:")
                with open(self.log_file) as f:
                    lines = f.readlines()
                    for line in lines[-5:]:
                        print(f"   {line.rstrip()}")
        else:
            print(f"❌ Server is not running on port {self.port}")
            if self.pid_file.exists():
                print(f"   (Stale PID file found, removing...)")
                self.pid_file.unlink()

    def is_running(self):
        """Check if server is running."""
        if not self.pid_file.exists():
            return False

        pid = self.get_pid()
        if pid is None:
            return False

        try:
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def get_pid(self):
        """Get server PID."""
        if not self.pid_file.exists():
            return None

        try:
            with open(self.pid_file) as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage DEGIRO Portfolio test servers"
    )
    parser.add_argument(
        'action',
        choices=['start', 'stop', 'restart', 'status'],
        help='Action to perform'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8001,
        help='Port to run server on (default: 8001)'
    )
    parser.add_argument(
        '--database',
        default='degiro_portfolio_test.db',
        help='Database file to use (default: degiro_portfolio_test.db)'
    )

    args = parser.parse_args()

    manager = ServerManager(port=args.port, database=args.database)

    if args.action == 'start':
        sys.exit(0 if manager.start() else 1)
    elif args.action == 'stop':
        sys.exit(0 if manager.stop() else 1)
    elif args.action == 'restart':
        manager.stop()
        time.sleep(1)
        sys.exit(0 if manager.start() else 1)
    elif args.action == 'status':
        manager.status()
        sys.exit(0 if manager.is_running() else 1)


if __name__ == '__main__':
    main()
