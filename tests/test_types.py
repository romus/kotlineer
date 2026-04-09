from __future__ import annotations

import pytest

from kotlineer.types import (
    KotlinLspConfig,
    LspError,
    OpenDocument,
    RequestTimeoutError,
    ServerCrashedError,
    ServerNotRunningError,
)


class TestKotlinLspConfig:
    def test_defaults(self):
        cfg = KotlinLspConfig(server_path="/bin/kls", workspace_root="/project")
        assert cfg.server_path == "/bin/kls"
        assert cfg.workspace_root == "/project"
        assert cfg.server_args == []
        assert cfg.server_env == {}
        assert cfg.request_timeout == 30.0

    def test_to_initialization_options_returns_empty(self):
        cfg = KotlinLspConfig(server_path="/bin/kls", workspace_root="/project")
        opts = cfg.to_initialization_options()
        assert opts == {}

    def test_mutable_defaults_are_independent(self):
        cfg1 = KotlinLspConfig(server_path="/a", workspace_root="/b")
        cfg2 = KotlinLspConfig(server_path="/c", workspace_root="/d")
        cfg1.server_args.append("--foo")
        cfg1.server_env["KEY"] = "val"
        assert cfg2.server_args == []
        assert cfg2.server_env == {}


class TestOpenDocument:
    def test_defaults(self):
        doc = OpenDocument(uri="file:///a.kt", content="fun main() {}", version=1)
        assert doc.uri == "file:///a.kt"
        assert doc.content == "fun main() {}"
        assert doc.version == 1
        assert doc.language_id == "kotlin"

    def test_custom_language(self):
        doc = OpenDocument(uri="file:///a.java", content="", version=1, language_id="java")
        assert doc.language_id == "java"


class TestLspError:
    def test_base_error(self):
        err = LspError("something broke", code=42, data={"info": "x"})
        assert str(err) == "something broke"
        assert err.code == 42
        assert err.data == {"info": "x"}

    def test_default_code(self):
        err = LspError("oops")
        assert err.code == -1
        assert err.data is None

    def test_is_exception(self):
        assert issubclass(LspError, Exception)


class TestServerNotRunningError:
    def test_message_and_code(self):
        err = ServerNotRunningError()
        assert "not running" in str(err)
        assert err.code == -1

    def test_is_lsp_error(self):
        assert issubclass(ServerNotRunningError, LspError)


class TestRequestTimeoutError:
    def test_message_and_attrs(self):
        err = RequestTimeoutError("textDocument/completion", 5.0)
        assert "completion" in str(err)
        assert "5.0" in str(err)
        assert err.code == -2
        assert err.method == "textDocument/completion"
        assert err.timeout == 5.0

    def test_is_lsp_error(self):
        assert issubclass(RequestTimeoutError, LspError)


class TestServerCrashedError:
    def test_with_exit_code(self):
        err = ServerCrashedError(exit_code=137)
        assert "137" in str(err)
        assert err.code == -3
        assert err.exit_code == 137

    def test_without_exit_code(self):
        err = ServerCrashedError()
        assert "crashed" in str(err).lower()
        assert err.exit_code is None

    def test_is_lsp_error(self):
        assert issubclass(ServerCrashedError, LspError)
