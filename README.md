# autourgos-textoutput

[![Framework: Autourgos](https://img.shields.io/badge/Framework-Autourgos-orange.svg)](https://github.com/devxjitin)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/autourgos-textoutput/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://github.com/devxjitin/autourgos-textoutput/blob/main/LICENSE)
[![Author](https://img.shields.io/badge/Author-Jitin%20Kumar%20Sengar-blue.svg)](https://github.com/devxjitin)

A simple, thread-safe Tkinter popup for displaying agent/LLM output for the Autourgos framework, with optional **Markdown rendering** (headings, bold/italic, code blocks, lists, links — not just raw text). The output counterpart to [autourgos-textinput](https://github.com/devxjitin/autourgos-textinput), kept as a **separate package deliberately** — capture and display are different concerns.

```python
from autourgos_textoutput import show_output

show_output("# Hello\n\nThis is **Markdown**, rendered properly.")
```

---

## Install

```bash
pip install "autourgos-textoutput[markdown]"
```

`markdown` + `tkhtmlview` are required only for actual Markdown *rendering* and are gated behind the `markdown` extra — `import autourgos_textoutput` alone never requires them, and `.show()`/`show_output()` still work without them, falling back to plain scrollable text. `tkinter` is Python's own stdlib GUI toolkit — present on most installs; if missing (some minimal Linux builds), that's surfaced as a clear error rather than an import-time crash. Requires Python 3.10+.

---

## Usage

### Quick (shared default box)

```python
from autourgos_textoutput import show_output

show_output(agent_result)                                  # Markdown rendering, default title "Autourgos Output"
show_output(agent_result, title="Weather Bot")              # custom title
show_output(agent_result, markdown=False)                   # force plain text
```

`show_output()` is **safe to call from any thread** — it lazily starts its own background Tk root/thread on first use, so you don't need to manage Tkinter's main-thread requirement yourself. This matters because output is naturally triggered from wherever a response becomes available — often a worker thread, e.g. inside `autourgos_textinput.TextInputBox`'s `on_submit`, which itself runs off the Tk thread.

### Multiple independent output windows (`OutputBox`)

```python
from autourgos_textoutput import OutputBox

box = OutputBox(title="My Assistant", width=600, height=500)
box.show(result_1)
box.show(result_2)   # a second, independent popup
box.close_all()       # close every window this box currently has open
```

### With autourgos-textinput

Full example — a global-hotkey prompt that shows the agent's Markdown reply back in a rendered popup:

```python
"""
pip install "autourgos-textinput[gui]" "autourgos-textoutput[markdown]" autourgos-agent autourgos-openaichat
"""
import os

from autourgos_agent import Agent
from autourgos_openaichat import OpenAIChatModel
from autourgos_textinput import TextInputBox
from autourgos_textoutput import show_output

llm = OpenAIChatModel(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"])
agent = Agent(llm=llm, verbose=False)


def on_submit(text: str) -> None:
    # Runs in its own worker thread (see autourgos-textinput's README) --
    # show_output() is safe to call from here since it manages its own
    # separate Tk root/thread rather than requiring the input box's.
    try:
        result = agent.invoke(text)  # may itself be Markdown
    except Exception as exc:
        result = f"**Error:** {exc}"
    show_output(result, title="Agent Response")


box = TextInputBox(hotkey="<ctrl>+<alt>+space", title="Ask the Agent", on_submit=on_submit)
box.start()  # blocks -- this must be your program's main thread
```

Both packages run their own independent Tk root on their own thread (`TextInputBox` needs the real main thread for its hotkey lifecycle; `OutputBox` deliberately doesn't, so it can be triggered from anywhere) — live-verified to coexist in the same process without conflict.

---

## API Reference

### `OutputBox(*, title="Autourgos Output", width=560, height=420)`

| Method | Description |
|---|---|
| `show(text, *, title=None, markdown=True)` | Show `text` in a popup. Safe to call from any thread. |
| `close_all()` | Close every currently-open window belonging to this box. Safe to call from any thread. |

### `show_output(text, *, title="Autourgos Output", markdown=True)`

Convenience function using one shared, lazily started `OutputBox` internally. Fine for most callers; construct your own `OutputBox()` for independent windows/settings.

### Errors (`autourgos_textoutput`)

| Name | Raised when |
|---|---|
| `TextOutputError` | Base class |
| `TextOutputUnavailableError` | `tkinter` isn't available |

---

## License

Apache License 2.0, Copyright (c) 2026 Jitin Kumar Sengar
