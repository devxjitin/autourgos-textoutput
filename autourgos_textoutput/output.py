"""
OutputBox -- a simple, thread-safe Tkinter popup for displaying agent/LLM
output, with optional Markdown rendering, for autourgos-textoutput.

This is autourgos-textinput's output counterpart, and deliberately a
separate package (not bundled into autourgos-textinput) -- capture and
display are different concerns.

Threading: unlike autourgos-textinput's TextInputBox (which requires the
caller's program to run its own Tk mainloop on the real main thread, since
it also has to own the global hotkey lifecycle), OutputBox runs its OWN Tk
root on its own dedicated background thread, started lazily on the first
`.show()` call. That's a deliberate difference: output is naturally
triggered from wherever a response becomes available -- often a worker
thread (e.g. autourgos-textinput's own `on_submit`, which runs off the Tk
thread) -- so requiring the caller to manage a main-thread mainloop just to
show a result would be awkward. `.show()` is safe to call from any thread.

Markdown rendering is gated behind the `markdown` extra (`markdown` +
`tkhtmlview`, `pip install autourgos-textoutput[markdown]`) -- without it,
`.show()` still works, falling back to plain scrollable text.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable, Optional, Tuple

from autourgos_core import require_available, try_import

logger = logging.getLogger(__name__)

_DEFAULT_TITLE = "Autourgos Output"


class TextOutputError(Exception):
    """Base error for autourgos-textoutput."""


class TextOutputUnavailableError(TextOutputError):
    """Raised when `tkinter` isn't available."""


def _load_tkinter() -> Tuple[bool, Any, Optional[str]]:
    available, modules, error = try_import("tkinter")
    if not available:
        return False, None, f"tkinter is not available: {error}"
    return True, modules["tkinter"], None


def _load_markdown_renderer() -> Tuple[bool, Any, Any, Optional[str]]:
    """Try to import `markdown` and `tkhtmlview`. Returns (available, markdown module, HTMLScrolledText class, error)."""
    md_available, md_modules, md_error = try_import("markdown")
    if not md_available:
        return False, None, None, (
            "The 'markdown' package is required for Markdown rendering "
            f"(pip install autourgos-textoutput[markdown]). Import error: {md_error}"
        )
    tk_available, tk_modules, tk_error = try_import("tkhtmlview")
    if not tk_available:
        return False, None, None, (
            "The 'tkhtmlview' package is required for Markdown rendering "
            f"(pip install autourgos-textoutput[markdown]). Import error: {tk_error}"
        )
    return True, md_modules["markdown"], tk_modules["tkhtmlview"].HTMLScrolledText, None


class OutputBox:
    """
    A reusable popup for showing text/Markdown output. Thread-safe --
    `.show()` may be called from any thread.

    Usage::

        box = OutputBox(title="Autourgos Output")
        box.show(agent_result)                    # rendered as Markdown if the 'markdown' extra is installed
        box.show(agent_result, markdown=False)     # force plain text

    Or the module-level convenience for a shared default instance:
    `from autourgos_textoutput import show_output`.
    """

    def __init__(self, *, title: str = _DEFAULT_TITLE, width: int = 560, height: int = 420) -> None:
        self._tk_available, self._tkinter, self._tk_import_error = _load_tkinter()
        self.title = title
        self.width = width
        self.height = height

        self._root: Any = None
        self._queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._started = threading.Event()
        self._start_lock = threading.Lock()
        self._start_error: Optional[Exception] = None

    def _require_available(self) -> None:
        require_available(
            self._tk_available,
            f"autourgos-textoutput is unavailable. Detail: {self._tk_import_error}",
            TextOutputUnavailableError,
        )

    def _ensure_started(self) -> None:
        self._require_available()
        with self._start_lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
        started = self._started.wait(timeout=5)
        if not started or self._start_error is not None:
            raise TextOutputUnavailableError(
                f"autourgos-textoutput failed to start its Tk root. Detail: {self._start_error}"
            )

    def _run(self) -> None:
        tkinter = self._tkinter
        try:
            self._root = tkinter.Tk()
            self._root.withdraw()  # the root itself is never shown -- only output windows are
        except Exception as exc:
            self._start_error = exc
            self._started.set()
            return
        self._started.set()
        self._root.after(50, self._poll_queue)
        self._root.mainloop()

    def _poll_queue(self) -> None:
        while True:
            try:
                fn = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                logger.exception("autourgos-textoutput: queued callback raised")
        if self._root is not None:
            self._root.after(50, self._poll_queue)

    def show(self, text: str, *, title: Optional[str] = None, markdown: bool = True) -> None:
        """
        Show `text` in a popup window. Safe to call from any thread --
        starts this box's internal Tk root/thread on first use if not
        already running.

        markdown: if True (default) and the `markdown` extra is installed,
            renders `text` as Markdown (headings, bold/italic, code blocks,
            lists, links). Falls back to plain scrollable text if the extra
            isn't installed, or if `markdown=False`.
        """
        self._ensure_started()
        self._queue.put(lambda: self._show_window(text, title or self.title, markdown))

    def close_all(self) -> None:
        """Close every currently-open output window belonging to this box. Safe to call from any thread."""
        if self._thread is None:
            return  # never started -- nothing could possibly be open
        self._ensure_started()
        self._queue.put(self._close_all_windows)

    # ── popups (always called on this box's own Tk thread) ─────────────────

    def _show_window(self, text: str, title: str, use_markdown: bool) -> None:
        tkinter = self._tkinter
        win = tkinter.Toplevel(self._root)
        win.title(title)
        win.geometry(f"{self.width}x{self.height}")
        win.attributes("-topmost", True)  # bring to front once...

        def _unpin():
            if win.winfo_exists():
                win.attributes("-topmost", False)

        win.after(200, _unpin)  # ...then stop pinning it above other windows

        rendered = False
        if use_markdown:
            available, markdown_module, html_scrolled_text_cls, _error = _load_markdown_renderer()
            if available:
                html = markdown_module.markdown(text, extensions=["fenced_code", "tables"])
                view = html_scrolled_text_cls(win, html=html)
                view.pack(fill="both", expand=True, padx=8, pady=(8, 0))
                rendered = True

        if not rendered:
            frame = tkinter.Frame(win)
            frame.pack(fill="both", expand=True, padx=8, pady=(8, 0))
            text_widget = tkinter.Text(frame, wrap="word", font=("Consolas", 10))
            scrollbar = tkinter.Scrollbar(frame, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            text_widget.insert("1.0", text)
            text_widget.configure(state="disabled")
            text_widget.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        close_button = tkinter.Button(win, text="Close", command=win.destroy, width=10)
        close_button.pack(pady=8)
        win.bind("<Escape>", lambda _e: win.destroy())
        win.focus_force()

    def _close_all_windows(self) -> None:
        tkinter = self._tkinter
        for widget in list(self._root.winfo_children()):
            if isinstance(widget, tkinter.Toplevel) and widget.winfo_exists():
                widget.destroy()


_default_box: Optional[OutputBox] = None
_default_box_lock = threading.Lock()


def _get_default_box() -> OutputBox:
    global _default_box
    with _default_box_lock:
        if _default_box is None:
            _default_box = OutputBox()
    return _default_box


def show_output(text: str, *, title: str = _DEFAULT_TITLE, markdown: bool = True) -> None:
    """
    Convenience function: show `text` (typically an agent/LLM response) in
    a popup, rendered as Markdown by default. Uses one shared, lazily
    started `OutputBox` internally -- fine for most callers; construct your
    own `OutputBox()` if you want independent windows/settings.

    Safe to call from any thread -- e.g. directly from
    `autourgos_textinput.TextInputBox`'s `on_submit` callback, which runs
    off the Tk thread.
    """
    _get_default_box().show(text, title=title, markdown=markdown)
