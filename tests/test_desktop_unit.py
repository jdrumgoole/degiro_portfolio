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


def test_icon_path_returns_bundled_icon():
    """_icon_path() should resolve to a bundled icon (rounded preferred)."""
    from degiro_portfolio.desktop import _icon_path
    import os
    p = _icon_path()
    assert p is not None, "bundled icon not found"
    assert os.path.exists(p)
    # Prefer the squircle-clipped variant; fall back to the flat PNG.
    assert p.endswith(("icon-256-rounded.png", "icon-256.png"))


def test_icon_path_prefers_rounded_over_flat():
    """When both icons exist, the rounded variant is chosen."""
    from degiro_portfolio.desktop import _icon_path
    p = _icon_path()
    # The rounded variant is shipped in v0.5.10+; if it exists, it should win.
    import os
    static_dir = os.path.dirname(p)
    if os.path.exists(os.path.join(static_dir, "icon-256-rounded.png")):
        assert p.endswith("icon-256-rounded.png")


def test_branding_helpers_noop_on_non_darwin():
    """On linux/windows, both helpers must do nothing and not crash."""
    from degiro_portfolio.desktop import _set_macos_bundle_name, _set_macos_dock_icon
    with patch('sys.platform', 'linux'):
        _set_macos_bundle_name()
        _set_macos_dock_icon("/some/icon.png")


def test_set_macos_bundle_name_overrides_cf_bundle_name():
    """On darwin, _set_macos_bundle_name should mutate CFBundleName in infoDictionary."""
    from contextlib import ExitStack

    info_dict: dict = {}
    bundle = MagicMock()
    bundle.infoDictionary.return_value = info_dict
    ns_bundle_class = MagicMock()
    ns_bundle_class.mainBundle.return_value = bundle
    foundation = MagicMock(NSBundle=ns_bundle_class)

    with ExitStack() as stack:
        stack.enter_context(patch('sys.platform', 'darwin'))
        stack.enter_context(patch.dict('sys.modules', {'Foundation': foundation}))

        from degiro_portfolio.desktop import _set_macos_bundle_name
        _set_macos_bundle_name()

    assert info_dict.get("CFBundleName") == "DEGIRO Portfolio"
    assert info_dict.get("CFBundleDisplayName") == "DEGIRO Portfolio"


def test_set_macos_dock_icon_calls_setApplicationIconImage():
    """On darwin, _set_macos_dock_icon should load the image and apply it."""
    from contextlib import ExitStack

    ns_app_instance = MagicMock()
    ns_app_class = MagicMock()
    ns_app_class.sharedApplication.return_value = ns_app_instance
    fake_image = MagicMock()
    ns_image_class = MagicMock()
    ns_image_class.alloc.return_value.initWithContentsOfFile_.return_value = fake_image
    appkit = MagicMock(NSApplication=ns_app_class, NSImage=ns_image_class)

    with ExitStack() as stack:
        stack.enter_context(patch('sys.platform', 'darwin'))
        stack.enter_context(patch.dict('sys.modules', {'AppKit': appkit}))

        from degiro_portfolio.desktop import _set_macos_dock_icon
        _set_macos_dock_icon("/some/icon.png")

    ns_app_instance.setApplicationIconImage_.assert_called_once_with(fake_image)


def test_set_macos_dock_icon_skips_when_image_load_fails():
    """If NSImage returns None, setApplicationIconImage_ must NOT be called."""
    from contextlib import ExitStack

    ns_app_instance = MagicMock()
    ns_app_class = MagicMock()
    ns_app_class.sharedApplication.return_value = ns_app_instance
    ns_image_class = MagicMock()
    ns_image_class.alloc.return_value.initWithContentsOfFile_.return_value = None  # load fails
    appkit = MagicMock(NSApplication=ns_app_class, NSImage=ns_image_class)

    with ExitStack() as stack:
        stack.enter_context(patch('sys.platform', 'darwin'))
        stack.enter_context(patch.dict('sys.modules', {'AppKit': appkit}))

        from degiro_portfolio.desktop import _set_macos_dock_icon
        _set_macos_dock_icon("/bogus.png")

    ns_app_instance.setApplicationIconImage_.assert_not_called()


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
