"""Unit tests for desktop.py — verify pywebview integration doesn't crash."""

import pytest
from unittest.mock import patch, MagicMock
import inspect


def _patch_subprocess_launch(stack):
    """Common patching: replace subprocess.Popen and the readiness poller.

    Returns the entered mocks for caller assertions if needed.
    """
    stack.enter_context(patch('degiro_portfolio.desktop._wait_for_ready', return_value=True))
    fake_proc = MagicMock()
    fake_proc.poll.return_value = 0  # process already exited → no terminate path
    stack.enter_context(patch('subprocess.Popen', return_value=fake_proc))
    stack.enter_context(patch('socket.socket'))
    return fake_proc


def test_create_window_uses_only_supported_kwargs():
    """Regression: create_window must not pass unsupported kwargs like 'icon'."""
    import webview
    from contextlib import ExitStack

    sig = inspect.signature(webview.create_window)
    supported_params = set(sig.parameters.keys())

    captured_kwargs: dict = {}

    def mock_create_window(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return MagicMock()

    with ExitStack() as stack:
        stack.enter_context(patch('webview.create_window', side_effect=mock_create_window))
        stack.enter_context(patch('webview.start'))
        _patch_subprocess_launch(stack)

        from degiro_portfolio.desktop import run_desktop
        run_desktop(port=19999)

        for key in captured_kwargs:
            assert key in supported_params, (
                f"create_window() received unsupported kwarg '{key}'. "
                f"Supported: {supported_params}"
            )


def test_run_desktop_creates_window_with_correct_title():
    """Desktop window should have the correct title and dimensions."""
    from contextlib import ExitStack

    with ExitStack() as stack:
        mock_cw = stack.enter_context(patch('webview.create_window', return_value=MagicMock()))
        stack.enter_context(patch('webview.start'))
        _patch_subprocess_launch(stack)

        from degiro_portfolio.desktop import run_desktop
        run_desktop(port=19998)

        args, kwargs = mock_cw.call_args
        assert args[0] == "DEGIRO Portfolio"
        assert kwargs.get('width') == 1280
        assert kwargs.get('height') == 900


def test_run_desktop_uses_subprocess_not_multiprocessing():
    """The desktop launcher must use subprocess.Popen (not multiprocessing).

    Regression for the resource_tracker semaphore leak: any
    `multiprocessing.Event` / `multiprocessing.Process` allocation here
    would surface as a Ctrl-C warning at interpreter shutdown.
    """
    from contextlib import ExitStack

    with ExitStack() as stack:
        stack.enter_context(patch('webview.create_window', return_value=MagicMock()))
        stack.enter_context(patch('webview.start'))
        mock_popen = stack.enter_context(patch('subprocess.Popen'))
        mock_popen.return_value = MagicMock(poll=MagicMock(return_value=0))
        stack.enter_context(patch('degiro_portfolio.desktop._wait_for_ready', return_value=True))
        stack.enter_context(patch('socket.socket'))
        # Fail loudly if anyone reintroduces multiprocessing primitives
        with patch('multiprocessing.Process', side_effect=AssertionError("don't use multiprocessing in desktop.py")), \
             patch('multiprocessing.Event', side_effect=AssertionError("don't use multiprocessing in desktop.py")):

            from degiro_portfolio.desktop import run_desktop
            run_desktop(port=19997)

        # subprocess.Popen was called with python -m uvicorn
        assert mock_popen.called, "subprocess.Popen was not invoked"
        cmd = mock_popen.call_args[0][0]
        assert cmd[0].endswith("python") or cmd[0].endswith("python3") or "python" in cmd[0]
        assert "-m" in cmd
        assert "uvicorn" in cmd


def _ok_response_mock(status: int = 200):
    """Build a context-manager-capable mock of urllib's HTTPResponse."""
    resp = MagicMock()
    resp.status = status
    cm = MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


def test_wait_for_ready_polls_both_ping_and_holdings():
    """_wait_for_ready returns True when both /api/ping and /api/holdings respond."""
    from degiro_portfolio.desktop import _wait_for_ready
    with patch('urllib.request.urlopen', return_value=_ok_response_mock(200)):
        assert _wait_for_ready("127.0.0.1", 8000, timeout_s=1.0) is True


def test_wait_for_ready_times_out_when_server_never_responds():
    """_wait_for_ready returns False if the server never comes up."""
    import urllib.error
    from degiro_portfolio.desktop import _wait_for_ready
    with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("nope")):
        assert _wait_for_ready("127.0.0.1", 8000, timeout_s=0.5) is False


def test_wait_for_ready_times_out_when_only_ping_responds():
    """If /api/ping succeeds but /api/holdings never does, return False."""
    import urllib.error
    from degiro_portfolio.desktop import _wait_for_ready

    def fake_urlopen(req, timeout=1):
        url = req if isinstance(req, str) else req.full_url
        if url.endswith("/api/ping"):
            return _ok_response_mock(200)
        raise urllib.error.URLError("holdings down")

    with patch('urllib.request.urlopen', side_effect=fake_urlopen):
        assert _wait_for_ready("127.0.0.1", 8000, timeout_s=0.6) is False
