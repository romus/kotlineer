# Python Library Reference

kotlineer can be used as an async Python library for programmatic access to all kotlin-lsp capabilities.

## Installation

```bash
pip install kotlineer
# or
uv pip install kotlineer
```

Requires Python 3.11+.

## Quick Start

```python
import asyncio
from kotlineer import KotlinLspClient

async def main():
    client = KotlinLspClient("/path/to/my-project")
    await client.start()

    uri = await client.open_file("src/main/kotlin/com/example/App.kt")
    info = await client.hover.hover(uri, line=14, character=8)
    print(info)

    await client.stop()

asyncio.run(main())
```

## Client Construction

### `KotlinLspClient(workspace_root, *, host, port, request_timeout)` — TCP connection (default)

Connects to an already-running kotlin-lsp server over TCP.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `workspace_root` | `str` | required | Absolute or relative path to the project root |
| `host` | `str` | `"localhost"` | Hostname of the kotlin-lsp server |
| `port` | `int` | `8200` | Port of the kotlin-lsp server |
| `request_timeout` | `float` | `30.0` | Timeout in seconds for each LSP request |

```python
# Default — localhost:8200
client = KotlinLspClient("/path/to/project")

# Custom host/port
client = KotlinLspClient("/path/to/project", host="10.0.0.5", port=9090)

# Custom timeout
client = KotlinLspClient("/path/to/project", request_timeout=60.0)
```

### `KotlinLspClient.spawn(workspace_root, *, server_path, request_timeout, server_args, server_env)` — Subprocess

Launches a new kotlin-lsp process. The `--stdio` flag is automatically injected.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `workspace_root` | `str` | required | Path to the project root |
| `server_path` | `str` | `"kotlin-lsp"` | Path to the kotlin-lsp binary |
| `request_timeout` | `float` | `30.0` | Timeout for LSP requests |
| `server_args` | `list[str] \| None` | `None` | Extra CLI arguments passed to the server |
| `server_env` | `dict[str, str] \| None` | `None` | Extra environment variables for the server process |

```python
# Default binary on PATH
client = KotlinLspClient.spawn("/path/to/project")

# Custom binary path
client = KotlinLspClient.spawn("/path/to/project", server_path="/opt/kls/bin/kotlin-lsp")

# With extra JVM args
client = KotlinLspClient.spawn(
    "/path/to/project",
    server_env={"JAVA_OPTS": "-Xmx4g"},
)
```

## Lifecycle

### `await client.start() -> dict`

Initialize the LSP session. Connects to the server (TCP) or starts the subprocess, then performs the LSP `initialize` / `initialized` handshake. Returns the server capabilities dict.

### `await client.stop()`

Gracefully shut down: closes all open documents, sends `shutdown` + `exit`, and closes the connection (or kills the subprocess).

### `client.is_running -> bool`

Whether the client has an active connection to the server.

### `client.capabilities -> dict | None`

Server capabilities returned during initialization. `None` before `start()` is called.

## Document Management

All positions in the library API are **0-based** (line 0 = first line, character 0 = first column). This matches the LSP protocol. The CLI uses 1-based positions for human readability.

### `await client.open_file(path) -> str`

Open a file from disk in the LSP session. Reads the file content and sends `textDocument/didOpen`. Returns the file URI.

- `path`: Absolute path or relative to `workspace_root`.

### `await client.update_file(path, content) -> str`

Update an already-open file with new content (full document sync). Sends `textDocument/didChange`. Returns the file URI.

- `path`: File path (absolute or relative).
- `content`: New full content of the file.

### `await client.close_file(path)`

Close a file in the LSP session. Sends `textDocument/didClose`.

## Services

All services are accessed as properties on the client. They are lazily created and cached.

---

### `client.completion` — CompletionService

#### `await completion.complete(uri, line, character) -> dict | list | None`

Get completion suggestions at a position. Returns a `CompletionList` dict (with `isIncomplete` and `items` fields) or a list of `CompletionItem` dicts.

#### `await completion.resolve(item) -> dict`

Resolve additional details (documentation, detail text) for a completion item.

```python
result = await client.completion.complete(uri, line=14, character=8)
items = result.get("items", []) if isinstance(result, dict) else result
for item in items[:5]:
    print(item["label"])
    resolved = await client.completion.resolve(item)
    print(resolved.get("detail", ""))
```

---

### `client.hover` — HoverService

#### `await hover.hover(uri, line, character) -> dict | None`

Get type information and documentation at a position. Returns a `Hover` dict with a `contents` field, or `None` if nothing is found.

#### `await hover.signature_help(uri, line, character) -> dict | None`

Get signature help (parameter hints) when inside a function call. Returns a `SignatureHelp` dict with `signatures`, `activeSignature`, and `activeParameter` fields.

```python
info = await client.hover.hover(uri, line=10, character=5)
if info:
    contents = info["contents"]
    if isinstance(contents, dict):
        print(contents.get("value", ""))
```

---

### `client.navigation` — NavigationService

#### `await navigation.definition(uri, line, character) -> list | dict | None`

Jump to the definition of a symbol. Returns a Location or list of Locations.

#### `await navigation.type_definition(uri, line, character) -> list | dict | None`

Jump to the type definition.

#### `await navigation.declaration(uri, line, character) -> list | dict | None`

Jump to the declaration.

#### `await navigation.implementation(uri, line, character) -> list | None`

Find all implementations of an interface or abstract member.

#### `await navigation.references(uri, line, character, include_declaration=True) -> list | None`

Find all references to a symbol.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_declaration` | `bool` | `True` | Whether to include the declaration itself in the results |

```python
# Go to definition
loc = await client.navigation.definition(uri, line=14, character=8)

# Find all references (excluding the declaration)
refs = await client.navigation.references(uri, 14, 8, include_declaration=False)

# Find implementations of an interface
impls = await client.navigation.implementation(uri, 5, 10)
```

---

### `client.symbols` — SymbolService

#### `await symbols.document_symbols(uri) -> list | None`

Get all symbols (classes, functions, properties) in a document. Returns hierarchical `DocumentSymbol` items with `name`, `kind`, `range`, and `children`.

#### `await symbols.workspace_symbols(query) -> list | None`

Search for symbols across the entire workspace by name pattern.

```python
# List all symbols in a file
syms = await client.symbols.document_symbols(uri)
for sym in syms or []:
    print(f"{sym['name']} (kind={sym['kind']})")

# Search workspace
results = await client.symbols.workspace_symbols("UserService")
```

---

### `client.formatting` — FormattingService

#### `await formatting.format(uri, tab_size=4, insert_spaces=True) -> list | None`

Format the entire document. Returns a list of `TextEdit` dicts (each with `range` and `newText`), or `None`/empty list if no changes needed.

#### `await formatting.format_range(uri, start_line, start_character, end_line, end_character, tab_size=4, insert_spaces=True) -> list | None`

Format a specific range within the document.

```python
edits = await client.formatting.format(uri)
if edits:
    for edit in edits:
        print(f"Replace {edit['range']} with: {edit['newText'][:50]}...")
```

---

### `client.code_actions` — CodeActionService

#### `await code_actions.get_actions(uri, start_line, start_character, end_line, end_character, diagnostics=None, only=None) -> list | None`

Get available code actions (quick fixes, refactoring suggestions) for a range.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `diagnostics` | `list[dict] \| None` | `None` | Relevant diagnostics to associate with the request |
| `only` | `list[str] \| None` | `None` | Filter by code action kinds: `"quickfix"`, `"refactor"`, `"refactor.extract"`, `"refactor.inline"`, `"refactor.rewrite"`, `"source"`, `"source.organizeImports"` |

#### `await code_actions.resolve(action) -> dict`

Resolve a code action to get the full edit.

#### `await code_actions.code_lens(uri) -> list | None`

Get code lens items for a document (e.g., "3 references", "run test").

#### `await code_actions.code_lens_resolve(lens) -> dict`

Resolve a code lens item to get the associated command.

```python
# Get quick fixes for a range
actions = await client.code_actions.get_actions(
    uri, 10, 0, 10, 20,
    only=["quickfix"],
)

# Organize imports
actions = await client.code_actions.get_actions(
    uri, 0, 0, 0, 0,
    only=["source.organizeImports"],
)
```

---

### `client.refactoring` — RefactoringService

#### `await refactoring.rename(uri, line, character, new_name) -> dict | None`

Rename a symbol across the workspace. Returns a `WorkspaceEdit` dict with file-level changes.

#### `await refactoring.prepare_rename(uri, line, character) -> dict | None`

Check if rename is possible at a position. Returns the range of the symbol and a placeholder name, or `None` if rename is not available.

```python
# Check if rename is possible
prep = await client.refactoring.prepare_rename(uri, 10, 5)
if prep:
    print(f"Can rename '{prep['placeholder']}'")
    edit = await client.refactoring.rename(uri, 10, 5, "newName")
```

---

### `client.hierarchy` — HierarchyService

#### Call Hierarchy

#### `await hierarchy.prepare_call_hierarchy(uri, line, character) -> list | None`

Get call hierarchy items at a position (the function itself).

#### `await hierarchy.incoming_calls(uri, line, character) -> list | None`

Find all functions that call the function at the given position. Automatically calls `prepare_call_hierarchy` first.

#### `await hierarchy.outgoing_calls(uri, line, character) -> list | None`

Find all functions called by the function at the given position.

#### Type Hierarchy

#### `await hierarchy.prepare_type_hierarchy(uri, line, character) -> list | None`

Get type hierarchy items at a position.

#### `await hierarchy.supertypes(uri, line, character) -> list | None`

Find all supertypes (parent classes/interfaces) of the type at the given position.

#### `await hierarchy.subtypes(uri, line, character) -> list | None`

Find all subtypes (subclasses/implementations) of the type at the given position.

```python
# Who calls this function?
callers = await client.hierarchy.incoming_calls(uri, 14, 4)

# What does this function call?
callees = await client.hierarchy.outgoing_calls(uri, 14, 4)

# Class hierarchy
supers = await client.hierarchy.supertypes(uri, 5, 10)
subs = await client.hierarchy.subtypes(uri, 5, 10)
```

---

### `client.diagnostics` — DiagnosticsService

The diagnostics service passively collects diagnostics pushed by the server via `textDocument/publishDiagnostics` notifications. It does not send requests.

#### `diagnostics.get(uri=None) -> dict[str, list]`

Get cached diagnostics. If `uri` is provided, returns `{uri: [...]}` for that file only. If `None`, returns all cached diagnostics across all files.

#### `diagnostics.get_errors(uri=None) -> dict[str, list]`

Get only error-level diagnostics (severity = 1).

#### `diagnostics.get_warnings(uri=None) -> dict[str, list]`

Get only warning-level diagnostics (severity = 2).

#### `diagnostics.on_update(handler)`

Register a callback `handler(uri: str, diagnostics: list)` that is called every time diagnostics are updated for any file.

#### `diagnostics.clear()`

Clear the diagnostics cache.

```python
# Open file and wait for diagnostics
uri = await client.open_file("src/Main.kt")
await asyncio.sleep(3)  # let the server analyze

# Get all diagnostics
all_diags = client.diagnostics.get()
for file_uri, diags in all_diags.items():
    for d in diags:
        print(f"{d['message']} (severity={d.get('severity')})")

# Errors only
errors = client.diagnostics.get_errors()

# React to updates in real-time
def on_diag(uri, diags):
    print(f"Updated: {uri} — {len(diags)} issues")
client.diagnostics.on_update(on_diag)
```

---

### `client.jetbrains` — JetBrainsExtensionService

Custom methods specific to JetBrains kotlin-lsp (not part of the LSP standard).

#### `await jetbrains.restart_lsp()`

Restart the Kotlin LSP server. Useful if the server gets into a bad state.

## Events

### `client.on_diagnostics(handler)`

Register a handler for raw `textDocument/publishDiagnostics` notifications. The handler receives the full notification params dict. For most use cases, prefer `client.diagnostics.on_update()` instead.

## Error Handling

kotlineer raises specific exceptions for different failure modes:

| Exception | When |
|-----------|------|
| `ServerNotRunningError` | A method is called before `start()` or after `stop()` |
| `RequestTimeoutError` | An LSP request exceeds the configured timeout |
| `ServerCrashedError` | The server subprocess exits unexpectedly (spawn mode only) |
| `LspError` | The server returned a JSON-RPC error response |

All exceptions inherit from `LspError`, which itself inherits from `Exception`.

```python
from kotlineer import KotlinLspClient, LspError, RequestTimeoutError

try:
    await client.start()
    result = await client.hover.hover(uri, 10, 5)
except RequestTimeoutError as e:
    print(f"Timed out after {e.timeout}s on {e.method}")
except LspError as e:
    print(f"LSP error (code={e.code}): {e}")
```

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_HOST` | `"localhost"` | Default host for TCP connections |
| `DEFAULT_PORT` | `8200` | Default port for TCP connections |
