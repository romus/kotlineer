from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kotlineer.client import DEFAULT_HOST, DEFAULT_PORT, KotlinLspClient, _path_to_uri
from kotlineer.types import ServerNotRunningError


class TestPathToUri:
    def test_absolute_path(self, tmp_path):
        p = tmp_path / "src" / "Main.kt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        uri = _path_to_uri(str(p))
        assert uri.startswith("file://")
        assert "Main.kt" in uri

    def test_preserves_slashes(self, tmp_path):
        p = tmp_path / "a" / "b" / "c.kt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        uri = _path_to_uri(str(p))
        assert "/a/b/c.kt" in uri

    def test_encodes_spaces(self, tmp_path):
        p = tmp_path / "my project" / "Main.kt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        uri = _path_to_uri(str(p))
        assert "%20" in uri or "my project" not in uri


class TestClientLifecycle:
    def test_not_running_initially(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))
        assert client.is_running is False
        assert client.capabilities is None

    def test_ensure_running_raises(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))
        with pytest.raises(ServerNotRunningError):
            client._ensure_running()

    def test_service_access_before_start_raises(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))
        with pytest.raises(ServerNotRunningError):
            _ = client.completion
        with pytest.raises(ServerNotRunningError):
            _ = client.hover
        with pytest.raises(ServerNotRunningError):
            _ = client.diagnostics

    async def test_on_diagnostics_before_start_raises(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))
        with pytest.raises(ServerNotRunningError):
            client.on_diagnostics(lambda p: None)


class TestDefaultConstructor:
    def test_defaults(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))
        assert client._server is None
        assert client._remote_host == DEFAULT_HOST
        assert client._remote_port == DEFAULT_PORT

    def test_custom_host_port(self, tmp_path):
        client = KotlinLspClient(str(tmp_path), host="10.0.0.1", port=9999)
        assert client._remote_host == "10.0.0.1"
        assert client._remote_port == 9999

    async def test_start_connects_via_tcp(self, tmp_path):
        client = KotlinLspClient(str(tmp_path), port=8080)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.send_request = AsyncMock(
            return_value={"capabilities": {"completionProvider": {}}}
        )
        mock_conn.send_notification = AsyncMock()

        with (
            patch("kotlineer.client.asyncio.open_connection", new_callable=AsyncMock, return_value=(mock_reader, mock_writer)),
            patch("kotlineer.client.LspConnection", return_value=mock_conn),
        ):
            caps = await client.start()

        assert caps == {"completionProvider": {}}
        assert client.is_running is True
        mock_conn.start.assert_called_once()

    async def test_stop_closes_socket(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))

        mock_conn = AsyncMock()
        mock_conn.send_request = AsyncMock(return_value=None)
        mock_conn.send_notification = AsyncMock()

        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        mock_docs = AsyncMock()

        client._connection = mock_conn
        client._documents = mock_docs
        client._socket_writer = mock_writer
        client._capabilities = {"foo": "bar"}

        await client.stop()

        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_called_once()
        assert client._connection is None
        assert client._socket_writer is None


class TestSpawn:
    def test_creates_subprocess_client(self, tmp_path):
        client = KotlinLspClient.spawn(str(tmp_path), server_path="/bin/kls")
        assert client._server is not None
        assert client._config.server_path == "/bin/kls"

    def test_default_server_path(self, tmp_path):
        client = KotlinLspClient.spawn(str(tmp_path))
        assert client._config.server_path == "kotlin-lsp"

    async def test_start_launches_subprocess(self, tmp_path):
        client = KotlinLspClient.spawn(str(tmp_path), server_path="/bin/kls")

        mock_process = AsyncMock()
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_process.start = AsyncMock(return_value=(mock_reader, mock_writer))
        mock_process.is_running = True

        mock_conn = AsyncMock()
        mock_conn.send_request = AsyncMock(
            return_value={"capabilities": {"completionProvider": {}}}
        )
        mock_conn.send_notification = AsyncMock()

        with (
            patch.object(client, "_server", mock_process),
            patch("kotlineer.client.LspConnection", return_value=mock_conn),
        ):
            caps = await client.start()

        assert caps == {"completionProvider": {}}
        assert client.capabilities == {"completionProvider": {}}
        mock_conn.start.assert_called_once()
        mock_conn.send_notification.assert_called_once_with("initialized", {})

    async def test_stop_cleans_up(self, tmp_path):
        client = KotlinLspClient.spawn(str(tmp_path), server_path="/bin/kls")

        mock_process = AsyncMock()
        mock_process.is_running = True

        mock_conn = AsyncMock()
        mock_conn.send_request = AsyncMock(return_value=None)
        mock_conn.send_notification = AsyncMock()

        mock_docs = AsyncMock()

        client._server = mock_process
        client._connection = mock_conn
        client._documents = mock_docs
        client._capabilities = {"foo": "bar"}
        client._services = {"completion": object()}

        await client.stop()

        mock_docs.close_all.assert_called_once()
        mock_conn.send_request.assert_called_with("shutdown")
        mock_conn.close.assert_called_once()
        mock_process.stop.assert_called_once()
        assert client._connection is None
        assert client._documents is None
        assert client._capabilities is None
        assert client._services == {}


class TestClientDocumentHelpers:
    def _make_client(self, tmp_path) -> KotlinLspClient:
        """Create a client with mocked internals for document tests."""
        client = KotlinLspClient(str(tmp_path))
        mock_conn = AsyncMock()
        mock_docs = AsyncMock()
        client._connection = mock_conn
        client._documents = mock_docs
        return client

    async def test_open_file(self, tmp_path):
        kt_file = tmp_path / "Main.kt"
        kt_file.write_text("fun main() {}", encoding="utf-8")

        client = self._make_client(tmp_path)
        uri = await client.open_file(str(kt_file))

        assert uri.startswith("file://")
        assert "Main.kt" in uri
        client._documents.open.assert_called_once()

    async def test_open_file_relative(self, tmp_path):
        kt_file = tmp_path / "src" / "Main.kt"
        kt_file.parent.mkdir()
        kt_file.write_text("fun main() {}", encoding="utf-8")

        client = self._make_client(tmp_path)
        uri = await client.open_file("src/Main.kt")
        assert "Main.kt" in uri

    async def test_update_file(self, tmp_path):
        kt_file = tmp_path / "Main.kt"
        kt_file.write_text("v1", encoding="utf-8")

        client = self._make_client(tmp_path)
        uri = await client.update_file(str(kt_file), "v2")
        client._documents.update.assert_called_once()

    async def test_close_file(self, tmp_path):
        kt_file = tmp_path / "Main.kt"
        kt_file.write_text("", encoding="utf-8")

        client = self._make_client(tmp_path)
        await client.close_file(str(kt_file))
        client._documents.close.assert_called_once()

    async def test_open_file_not_running_raises(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))
        with pytest.raises(ServerNotRunningError):
            await client.open_file("Main.kt")


class TestClientServices:
    def _make_running_client(self, tmp_path) -> KotlinLspClient:
        client = KotlinLspClient(str(tmp_path))
        mock_conn = MagicMock()
        mock_conn.on_notification = MagicMock()
        client._connection = mock_conn
        return client

    def test_service_caching(self, tmp_path):
        client = self._make_running_client(tmp_path)
        svc1 = client.completion
        svc2 = client.completion
        assert svc1 is svc2

    def test_all_services_accessible(self, tmp_path):
        client = self._make_running_client(tmp_path)
        assert client.completion is not None
        assert client.hover is not None
        assert client.navigation is not None
        assert client.symbols is not None
        assert client.formatting is not None
        assert client.code_actions is not None
        assert client.refactoring is not None
        assert client.hierarchy is not None
        assert client.jetbrains is not None
        assert client.diagnostics is not None


class TestClientCapabilities:
    def test_client_capabilities_structure(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))
        caps = client._client_capabilities()

        assert "textDocument" in caps
        assert "workspace" in caps
        td = caps["textDocument"]
        assert "completion" in td
        assert "hover" in td
        assert "definition" in td
        assert "references" in td
        assert "codeAction" in td
        assert "formatting" in td
        assert "rename" in td
        assert "publishDiagnostics" in td

    def test_snippets_always_enabled(self, tmp_path):
        client = KotlinLspClient(str(tmp_path))
        caps = client._client_capabilities()
        assert caps["textDocument"]["completion"]["completionItem"]["snippetSupport"] is True
