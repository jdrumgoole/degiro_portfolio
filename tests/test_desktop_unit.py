"""Unit tests for desktop.py — verify pywebview integration doesn't crash."""

import pytest
from unittest.mock import patch, MagicMock
import inspect


def test_create_window_uses_only_supported_kwargs():
    """Regression: create_window must not pass unsupported kwargs like 'icon'."""
    import webview

    # Get the actual signature of webview.create_window
    sig = inspect.signature(webview.create_window)
    supported_params = set(sig.parameters.keys())

    # Mock webview and capture the kwargs passed to create_window
    captured_kwargs = {}

    def mock_create_window(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return MagicMock()

    with patch('webview.create_window', side_effect=mock_create_window) as mock_cw, \
         patch('webview.start'), \
         patch('multiprocessing.Process') as mock_proc, \
         patch('multiprocessing.Event') as mock_event, \
         patch('socket.socket'):

        mock_process = MagicMock()
        mock_proc.return_value = mock_process
        mock_event_inst = MagicMock()
        mock_event_inst.wait.return_value = True
        mock_event.return_value = mock_event_inst

        from degiro_portfolio.desktop import run_desktop
        run_desktop(port=19999)

        # Every kwarg passed to create_window must be in the supported set
        for key in captured_kwargs:
            assert key in supported_params, (
                f"create_window() received unsupported kwarg '{key}'. "
                f"Supported: {supported_params}"
            )


def test_run_desktop_creates_window_with_correct_title():
    """Desktop window should have the correct title."""
    with patch('webview.create_window', return_value=MagicMock()) as mock_cw, \
         patch('webview.start'), \
         patch('multiprocessing.Process') as mock_proc, \
         patch('multiprocessing.Event') as mock_event, \
         patch('socket.socket'):

        mock_proc.return_value = MagicMock()
        mock_event_inst = MagicMock()
        mock_event_inst.wait.return_value = True
        mock_event.return_value = mock_event_inst

        from degiro_portfolio.desktop import run_desktop
        run_desktop(port=19998)

        args, kwargs = mock_cw.call_args
        # Title is first positional arg
        assert args[0] == "DEGIRO Portfolio"
        assert kwargs.get('width') == 1280
        assert kwargs.get('height') == 900
