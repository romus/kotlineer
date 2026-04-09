from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from kotlineer.documents import DocumentManager


def _make_mock_connection() -> AsyncMock:
    conn = AsyncMock()
    conn.send_notification = AsyncMock()
    return conn


class TestOpen:
    async def test_opens_document(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "fun main() {}")

        conn.send_notification.assert_called_once_with(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": "file:///a.kt",
                    "languageId": "kotlin",
                    "version": 1,
                    "text": "fun main() {}",
                }
            },
        )

    async def test_open_tracks_document(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "content")

        doc = mgr.get("file:///a.kt")
        assert doc is not None
        assert doc.uri == "file:///a.kt"
        assert doc.content == "content"
        assert doc.version == 1
        assert doc.language_id == "kotlin"

    async def test_open_custom_language(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.java", "class A {}", language_id="java")

        doc = mgr.get("file:///a.java")
        assert doc is not None
        assert doc.language_id == "java"

    async def test_open_already_open_delegates_to_update(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "v1")
        await mgr.open("file:///a.kt", "v2")

        doc = mgr.get("file:///a.kt")
        assert doc is not None
        assert doc.content == "v2"
        assert doc.version == 2


class TestUpdate:
    async def test_updates_existing(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "v1")
        conn.send_notification.reset_mock()

        await mgr.update("file:///a.kt", "v2")

        conn.send_notification.assert_called_once_with(
            "textDocument/didChange",
            {
                "textDocument": {"uri": "file:///a.kt", "version": 2},
                "contentChanges": [{"text": "v2"}],
            },
        )

        doc = mgr.get("file:///a.kt")
        assert doc is not None
        assert doc.content == "v2"
        assert doc.version == 2

    async def test_update_increments_version(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "v1")
        await mgr.update("file:///a.kt", "v2")
        await mgr.update("file:///a.kt", "v3")

        doc = mgr.get("file:///a.kt")
        assert doc is not None
        assert doc.version == 3

    async def test_update_unopened_auto_opens(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.update("file:///a.kt", "content")

        doc = mgr.get("file:///a.kt")
        assert doc is not None
        assert doc.version == 1
        conn.send_notification.assert_called_once_with(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": "file:///a.kt",
                    "languageId": "kotlin",
                    "version": 1,
                    "text": "content",
                }
            },
        )


class TestClose:
    async def test_closes_document(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "content")
        conn.send_notification.reset_mock()

        await mgr.close("file:///a.kt")

        conn.send_notification.assert_called_once_with(
            "textDocument/didClose",
            {"textDocument": {"uri": "file:///a.kt"}},
        )
        assert mgr.get("file:///a.kt") is None

    async def test_close_unknown_is_noop(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.close("file:///unknown.kt")
        conn.send_notification.assert_not_called()


class TestSave:
    async def test_sends_did_save(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "content")
        conn.send_notification.reset_mock()

        await mgr.save("file:///a.kt")

        conn.send_notification.assert_called_once_with(
            "textDocument/didSave",
            {"textDocument": {"uri": "file:///a.kt"}, "text": "content"},
        )

    async def test_save_unknown_is_noop(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.save("file:///unknown.kt")
        conn.send_notification.assert_not_called()


class TestGetAll:
    async def test_returns_all_documents(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "a")
        await mgr.open("file:///b.kt", "b")

        docs = mgr.get_all()
        assert len(docs) == 2
        uris = {d.uri for d in docs}
        assert uris == {"file:///a.kt", "file:///b.kt"}

    async def test_empty(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)
        assert mgr.get_all() == []


class TestCloseAll:
    async def test_closes_all(self):
        conn = _make_mock_connection()
        mgr = DocumentManager(conn)

        await mgr.open("file:///a.kt", "a")
        await mgr.open("file:///b.kt", "b")

        await mgr.close_all()

        assert mgr.get_all() == []
