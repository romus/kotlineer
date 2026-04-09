# Architecture

Overview of kotlineer's internal design and how it communicates with kotlin-lsp.

## Layer Diagram

```
┌─────────────────────────────────────────┐
│            CLI (cli.py)                 │  Human-facing commands
├─────────────────────────────────────────┤
│        KotlinLspClient (client.py)      │  Main facade, lifecycle
├──────────────┬──────────────────────────┤
│  Services    │   DocumentManager        │  High-level LSP APIs
│  (services/) │   (documents.py)         │
├──────────────┴──────────────────────────┤
│        LspConnection (connection.py)    │  JSON-RPC protocol
├──────────────┬──────────────────────────┤
│ TCP socket   │  Subprocess stdio        │  Transport layer
│ (asyncio)    │  (process.py)            │
└──────────────┴──────────────────────────┘
         │                    │
         ▼                    ▼
   ┌──────────┐        ┌──────────┐
   │kotlin-lsp│        │kotlin-lsp│
   │ (socket) │        │ (stdio)  │
   └──────────┘        └──────────┘
```

## Components

### KotlinLspClient (`client.py`)

The main entry point. Manages the full lifecycle:

1. **Construction** — Configures either TCP or subprocess mode
2. **`start()`** — Establishes connection + LSP `initialize` handshake
3. **Service access** — Lazy-loaded, cached service instances
4. **`stop()`** — Graceful `shutdown` + `exit` + cleanup

### LspConnection (`connection.py`)

Implements the JSON-RPC 2.0 protocol with LSP Content-Length framing. Transport-agnostic — works identically over TCP streams or subprocess stdio pipes.

Key responsibilities:
- **Request/response pairing** — Each request gets a unique ID; responses are matched via futures
- **Notification dispatch** — Server notifications routed to registered handlers
- **Server requests** — Auto-responds to `workspace/configuration` with empty configs; other server requests get `null`
- **Timeout handling** — Per-request timeouts with `RequestTimeoutError`

### ServerProcess (`process.py`)

Manages the kotlin-lsp subprocess lifecycle (spawn mode only):
- Starts the process with `--stdio` (auto-injected)
- Captures stderr for logging
- Graceful terminate with 5-second timeout, then force kill

### DocumentManager (`documents.py`)

Tracks open documents and sends LSP notifications:
- `textDocument/didOpen` — with full content
- `textDocument/didChange` — full document sync (not incremental)
- `textDocument/didClose`
- `textDocument/didSave`

### Services (`services/`)

Each service wraps a group of related LSP methods:

| Service | LSP Methods |
|---------|-------------|
| `CompletionService` | `textDocument/completion`, `completionItem/resolve` |
| `HoverService` | `textDocument/hover`, `textDocument/signatureHelp` |
| `NavigationService` | `textDocument/definition`, `typeDefinition`, `declaration`, `implementation`, `references` |
| `SymbolService` | `textDocument/documentSymbol`, `workspace/symbol` |
| `FormattingService` | `textDocument/formatting`, `textDocument/rangeFormatting` |
| `CodeActionService` | `textDocument/codeAction`, `codeAction/resolve`, `textDocument/codeLens`, `codeLens/resolve` |
| `RefactoringService` | `textDocument/rename`, `textDocument/prepareRename` |
| `HierarchyService` | `prepareCallHierarchy`, `callHierarchy/incomingCalls`, `outgoingCalls`, `prepareTypeHierarchy`, `typeHierarchy/supertypes`, `subtypes` |
| `DiagnosticsService` | Listens to `textDocument/publishDiagnostics` (passive, no requests) |
| `JetBrainsExtensionService` | `jetbrains.kotlin.restartLsp` |

## Connection Modes

### TCP Mode (default)

```
KotlinLspClient(workspace)
    └── start()
        └── asyncio.open_connection(host, port)
            └── LspConnection(reader, writer)
```

The client connects to a running kotlin-lsp via TCP. The server must be started separately with `kotlin-lsp --socket <port>`. On `stop()`, the TCP connection is closed but the server process continues running.

### Subprocess Mode

```
KotlinLspClient.spawn(workspace)
    └── start()
        └── ServerProcess.start()
            └── asyncio.create_subprocess_exec("kotlin-lsp", "--stdio")
                └── LspConnection(stdout, stdin)
```

The client spawns a new kotlin-lsp process with stdio communication. On `stop()`, the process is terminated (SIGTERM, then SIGKILL after 5s).

## File Discovery

The CLI automatically discovers `.kt` files when no specific files are provided. It recursively searches the workspace while ignoring these directories:

- `build/`
- `.gradle/`
- `.idea/`
- `out/`
- `.git/`

## Error Flow

```
LSP request
    ├── Success → result value
    ├── Timeout → RequestTimeoutError
    ├── JSON-RPC error → LspError (code, message, data)
    ├── Connection lost → LspError("Connection lost")
    └── Server crashed → ServerCrashedError (subprocess mode)
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `lsprotocol` | LSP type definitions (not directly used for serialization — raw dicts are used for flexibility) |
| `cattrs` | Object serialization utilities |
| Python `asyncio` | Async I/O, subprocess management, TCP connections |
