"""
Tests for autourgos_textoutput.OutputBox / show_output.

tkinter itself is real -- these tests exercise actual Tk widgets. Skips
automatically if no display is available. `markdown`/`tkhtmlview` are
exercised for real when installed (this package's own `dev` extra installs
them) -- the fallback (plain text) path is tested by forcing `markdown=False`
and separately by simulating the extra being absent.
"""

import sys
import threading
import time

import pytest

tkinter = pytest.importorskip("tkinter")

from autourgos_textoutput.output import OutputBox, TextOutputUnavailableError, show_output


def _tk_available() -> bool:
    try:
        root = tkinter.Tk()
        root.destroy()
        return True
    except tkinter.TclError:
        return False


pytestmark = pytest.mark.skipif(not _tk_available(), reason="no display available for tkinter")


def _wait_for_toplevel(box: OutputBox, expected_count: int = 1, timeout: float = 3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if box._root is not None:
            tops = [w for w in box._root.winfo_children() if isinstance(w, tkinter.Toplevel) and w.winfo_exists()]
            if len(tops) >= expected_count:
                return tops
        time.sleep(0.05)
    raise AssertionError(f"expected {expected_count} Toplevel(s), timed out waiting")


def test_show_starts_its_own_thread_and_root():
    box = OutputBox(title="Test Output")
    assert not box._bg.is_started
    box.show("hello")
    tops = _wait_for_toplevel(box)
    assert box._bg.is_started
    assert box._bg._thread.is_alive()
    assert tops[0].title() == "Test Output"
    box.close_all()


def test_poll_queue_survives_a_raising_callback():
    box = OutputBox()
    box._ensure_started()

    def boom():
        raise RuntimeError("simulated bad render")

    box._queue.post(boom)
    box.show("still works after a bad callback")
    _wait_for_toplevel(box)
    assert box._bg._thread.is_alive()
    box.close_all()


def test_show_is_safe_from_a_worker_thread():
    box = OutputBox()
    done = threading.Event()

    def worker():
        box.show("from a worker thread")
        done.set()

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=3)
    assert done.is_set()
    _wait_for_toplevel(box)
    box.close_all()


def test_plain_text_fallback_when_markdown_false():
    box = OutputBox()
    box.show("plain **not rendered** text", markdown=False)
    tops = _wait_for_toplevel(box)
    win = tops[0]
    text_widgets = [w for f in win.winfo_children() for w in getattr(f, "winfo_children", lambda: [])()
                    if isinstance(w, tkinter.Text)]
    assert len(text_widgets) == 1
    assert "**not rendered**" in text_widgets[0].get("1.0", "end")
    box.close_all()


def test_structured_output_dict_response_is_extracted():
    """
    Regression: show()/show_output() used to trust the `text: str` type
    hint blindly -- an LLM wrapper constructed with structured_output=True
    (autourgos-openaichat/autourgos-responses) returns a metadata dict, not
    a plain string, and passing one straight to show() rendered the dict's
    repr instead of the actual response text (or worse, depending on the
    Markdown renderer's handling of a non-str input).
    """
    box = OutputBox()
    box.show({"model": "gpt-4o", "response": "the actual answer", "input_tokens": 9}, markdown=False)
    tops = _wait_for_toplevel(box)
    win = tops[0]
    text_widgets = [w for f in win.winfo_children() for w in getattr(f, "winfo_children", lambda: [])()
                    if isinstance(w, tkinter.Text)]
    assert len(text_widgets) == 1
    rendered = text_widgets[0].get("1.0", "end")
    assert "the actual answer" in rendered
    assert "'model'" not in rendered  # not the raw dict repr
    box.close_all()


def test_markdown_rendering_when_extra_installed():
    from tkhtmlview import HTMLScrolledText

    box = OutputBox()
    box.show("# Hello\n\nBold **text** here.", markdown=True)
    tops = _wait_for_toplevel(box)
    win = tops[0]
    # HTMLScrolledText rebinds .pack() to an internal wrapper Frame (the
    # classic tkinter.scrolledtext.ScrolledText trick), so the actual widget
    # is one level deeper than a direct child of the Toplevel.
    wrapper_frame = win.winfo_children()[0]
    html_widgets = [c for c in wrapper_frame.winfo_children() if isinstance(c, HTMLScrolledText)]
    assert len(html_widgets) == 1
    rendered_text = html_widgets[0].get("1.0", "end")
    assert "Hello" in rendered_text
    assert "Bold text here" in rendered_text  # ** markers consumed by real bold styling, not left literal
    assert "**" not in rendered_text
    box.close_all()


def test_close_all_on_never_started_box_does_not_start_a_thread():
    box = OutputBox()
    assert not box._bg.is_started
    box.close_all()
    assert not box._bg.is_started


def test_window_is_not_permanently_topmost():
    box = OutputBox()
    box.show("hi", markdown=False)
    tops = _wait_for_toplevel(box)
    win = tops[0]

    deadline = time.time() + 3.0
    while time.time() < deadline and win.attributes("-topmost"):
        time.sleep(0.05)
    assert not win.attributes("-topmost")
    box.close_all()


def test_custom_title_overrides_default_per_call():
    box = OutputBox(title="Default Title")
    box.show("hi", title="Custom Title", markdown=False)
    tops = _wait_for_toplevel(box)
    assert tops[0].title() == "Custom Title"
    box.close_all()


def test_close_all_removes_windows():
    box = OutputBox()
    box.show("one", markdown=False)
    box.show("two", markdown=False)
    _wait_for_toplevel(box, expected_count=2)
    box.close_all()
    time.sleep(0.3)
    remaining = [w for w in box._root.winfo_children() if isinstance(w, tkinter.Toplevel) and w.winfo_exists()]
    assert remaining == []


def test_falls_back_to_plain_text_when_markdown_extra_missing(monkeypatch):
    import autourgos_textoutput.output as output_module

    monkeypatch.setattr(
        output_module, "_load_markdown_renderer",
        lambda: (False, None, None, "simulated missing markdown/tkhtmlview"),
    )
    box = OutputBox()
    box.show("# Not rendered\n\nStill **raw**.", markdown=True)  # markdown=True, but the extra is "missing"
    tops = _wait_for_toplevel(box)
    win = tops[0]
    text_widgets = [w for f in win.winfo_children() for w in getattr(f, "winfo_children", lambda: [])()
                    if isinstance(w, tkinter.Text)]
    assert len(text_widgets) == 1
    raw = text_widgets[0].get("1.0", "end")
    assert "# Not rendered" in raw  # shown as literal raw Markdown text, not rendered
    box.close_all()


def test_tk_root_start_failure_raises_instead_of_silently_no_oping(monkeypatch):
    box = OutputBox()

    class _ExplodingTk:
        def __init__(self, *a, **kw):
            raise RuntimeError("simulated Tk() startup failure")

    monkeypatch.setattr(box._tkinter, "Tk", _ExplodingTk)

    with pytest.raises(TextOutputUnavailableError):
        box.show("hi")


def test_without_tkinter_raises(monkeypatch):
    import autourgos_textoutput.output as output_module

    monkeypatch.setattr(output_module, "_load_tkinter", lambda: (False, None, "simulated missing tkinter"))
    box = OutputBox()
    with pytest.raises(TextOutputUnavailableError):
        box.show("hi")


def test_module_level_show_output_uses_shared_default_box():
    import autourgos_textoutput.output as output_module

    output_module._default_box = None  # reset the module-level singleton for this test
    show_output("shared box test", markdown=False, title="Shared Box")
    box = output_module._get_default_box()
    tops = _wait_for_toplevel(box)
    assert tops[-1].title() == "Shared Box"
    box.close_all()
