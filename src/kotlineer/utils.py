from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

if TYPE_CHECKING:
    from .client import KotlinLspClient

IGNORE_DIRS = {"build", ".gradle", ".idea", "out", ".git"}

SEVERITY_LABELS = {1: "error", 2: "warning", 3: "info", 4: "hint"}


def uri_to_path(uri: str) -> str:
    parsed = urlparse(uri)
    return unquote(parsed.path)


def find_kotlin_files(workspace: Path) -> list[Path]:
    return sorted(
        p for p in workspace.rglob("*.kt") if not any(part in IGNORE_DIRS for part in p.parts)
    )


def apply_text_edits(text: str, edits: list[dict[str, Any]]) -> str:
    lines = text.split("\n")

    sorted_edits = sorted(
        edits,
        key=lambda e: (
            e["range"]["start"]["line"],
            e["range"]["start"]["character"],
        ),
        reverse=True,
    )

    for edit in sorted_edits:
        start = edit["range"]["start"]
        end = edit["range"]["end"]
        new_text = edit["newText"]

        sl, sc = start["line"], start["character"]
        el, ec = end["line"], end["character"]

        before = lines[sl][:sc]
        after = lines[el][ec:]

        new_lines = (before + new_text + after).split("\n")
        lines[sl : el + 1] = new_lines

    return "\n".join(lines)


async def wait_for_diagnostics(
    client: KotlinLspClient,
    timeout: float = 30.0,
    settle: float = 3.0,
) -> None:
    loop = asyncio.get_event_loop()
    last_update: float | None = None

    def on_diag(_uri: str, _diags: list) -> None:
        nonlocal last_update
        last_update = loop.time()

    client.diagnostics.on_update(on_diag)

    deadline = loop.time() + timeout
    while True:
        now = loop.time()
        if now > deadline:
            break
        if last_update is not None and now - last_update >= settle:
            break
        await asyncio.sleep(0.5)
