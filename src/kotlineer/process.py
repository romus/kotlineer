from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from .types import ServerCrashedError

if TYPE_CHECKING:
    from .types import KotlinLspConfig

logger = logging.getLogger(__name__)


class ServerProcess:
    """Manages the kotlin-lsp child process."""

    def __init__(self, config: KotlinLspConfig) -> None:
        self._config = config
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    async def start(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Start the server process and return (stdout_reader, stdin_writer)."""
        if self.is_running:
            raise RuntimeError("Server process is already running")

        env = {**os.environ, **self._config.server_env} if self._config.server_env else None

        extra_args = list(self._config.server_args)
        if "--stdio" not in extra_args:
            extra_args.insert(0, "--stdio")
        cmd = [self._config.server_path, *extra_args]
        logger.info("Starting kotlin-lsp: %s", " ".join(cmd))

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        assert self._process.stdout is not None
        assert self._process.stdin is not None
        assert self._process.stderr is not None

        # Log stderr in background
        self._stderr_task = asyncio.create_task(self._read_stderr(self._process.stderr))

        logger.info("Server started (pid=%d)", self._process.pid)

        # asyncio.subprocess.Process.stdin is StreamWriter-like but typed as such
        return self._process.stdout, self._process.stdin  # type: ignore[return-value]

    async def stop(self) -> None:
        """Stop the server process gracefully, then force-kill if needed."""
        if self._process is None:
            return

        if self._process.returncode is None:
            logger.info("Stopping server (pid=%d)", self._process.pid)
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Server did not terminate, killing")
                self._process.kill()
                await self._process.wait()

        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass

        logger.info("Server stopped")
        self._process = None
        self._stderr_task = None

    async def wait(self) -> int:
        """Wait for the process to exit and return exit code. Raises ServerCrashedError on non-zero."""
        if self._process is None:
            raise RuntimeError("Server process is not started")
        code = await self._process.wait()
        if code != 0:
            raise ServerCrashedError(exit_code=code)
        return code

    async def _read_stderr(self, stderr: asyncio.StreamReader) -> None:
        """Read stderr lines and log them."""
        try:
            while True:
                line = await stderr.readline()
                if not line:
                    break
                logger.debug("[kotlin-ls stderr] %s", line.decode(errors="replace").rstrip())
        except asyncio.CancelledError:
            pass
