"""
autourgos-textoutput
======================
A simple, thread-safe Tkinter popup for displaying agent/LLM output, with
optional Markdown rendering. The output counterpart to `autourgos-textinput`
(kept as a separate package deliberately -- capture and display are
different concerns).

Zero dependency to import; `tkinter` is Python's own stdlib GUI toolkit
(present on most installs, missing on some minimal Linux builds -- handled
as a clear error, not an import-time crash). `markdown` + `tkhtmlview` are
required only for actual Markdown *rendering* and are gated behind the
`markdown` extra (`pip install autourgos-textoutput[markdown]`) -- without
them, `.show()` still works, falling back to plain scrollable text.

Quick start::

    from autourgos_textoutput import show_output

    show_output("# Hello\\n\\nThis is **Markdown**.")

Typically paired with `autourgos-textinput`::

    from autourgos_textinput import TextInputBox
    from autourgos_textoutput import show_output

    def on_submit(text: str) -> None:
        result = my_agent.invoke(text)   # e.g. Markdown from an LLM
        show_output(result)              # rendered in a popup

    TextInputBox(on_submit=on_submit).start()
"""

from .output import OutputBox, TextOutputError, TextOutputUnavailableError, show_output

from autourgos_core import package_version

__version__ = package_version("autourgos-textoutput", fallback="0.1.2")

__all__ = [
    "OutputBox",
    "TextOutputError",
    "TextOutputUnavailableError",
    "show_output",
]
