# Changelog

## 0.1.4

- Internal: `OutputBox`'s queue-post/drain and lazy-start-worker-thread internals migrated to `autourgos_core.PendingCallableQueue`/`LazyBackgroundThread`. No functional change (per-callback exception logging on drain preserved). Bumped `autourgos-core>=0.10.0`. Live-verified real Tk popup show/close round trip.

## 0.1.3

- **Fixed:** `show()`/`show_output()` blindly trusted the `text: str` type hint -- passing the metadata dict an LLM wrapper returns with `structured_output=True` rendered its Python repr instead of the actual response text. Now runs `text` through `autourgos_core.extract_text()` first (bumped `autourgos-core>=0.4.0`); a plain string still passes through unchanged.

## 0.1.2

- Internal: `__version__` resolution moved to `autourgos_core.package_version()` (bumped `autourgos-core>=0.3.0`). No functional change.

## 0.1.1

- Internal: `_load_tkinter()`/`_load_markdown_renderer()`'s import-probing logic moved to `autourgos_core.try_import()` (new `autourgos-core>=0.1.0` dependency), and `_require_available()`'s conditional-raise moved to `autourgos_core.require_available()`. No behavior change -- error messages stay identical.

## 0.1.0

- Initial release: `OutputBox` / `show_output()` -- a thread-safe Tkinter popup for displaying agent/LLM output, with optional Markdown rendering (`markdown` + `tkhtmlview`, gated behind the `markdown` extra; falls back to plain scrollable text without it). Deliberately a separate package from `autourgos-textinput` (capture vs. display are different concerns) and deliberately manages its own internal Tk root on its own background thread (unlike `TextInputBox`, which requires the caller's real main thread) -- since output is naturally triggered from wherever a response becomes available, often a worker thread.
- Live-verified: Markdown rendering confirmed end-to-end (`# Hello\n\nBold **text**` renders with real bold styling, not literal `**` markers -- had to dig one level past `HTMLScrolledText`'s `.pack()`-rebinding-to-an-internal-Frame implementation detail, the classic `tkinter.scrolledtext.ScrolledText` trick, to actually find and inspect the rendered widget). Also live-verified the real intended pairing: a `TextInputBox` (owning the real main thread's Tk root) and an `OutputBox` (owning its own separate background-thread Tk root) coexisting in the same process at the same time, `on_submit` calling `show_output()` -- no conflict.
- 9 tests (real Tkinter widgets; the plain-text fallback path tested both via `markdown=False` and by simulating the `markdown` extra being absent).
