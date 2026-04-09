# CLI Reference

kotlineer provides a command-line interface for running Kotlin language analysis powered by JetBrains kotlin-lsp.

## Synopsis

```
kotlineer [GLOBAL OPTIONS] COMMAND [COMMAND OPTIONS] [ARGS...]
```

## Connection Modes

kotlineer supports two ways to communicate with kotlin-lsp:

### TCP connection (default)

Connects to an already-running kotlin-lsp server. This is the default and recommended mode because the server stays warm between invocations, making repeated calls significantly faster.

```bash
# Start the server once (in a separate terminal or background)
kotlin-lsp --socket 8200

# Every kotlineer call reuses the running server
kotlineer check
kotlineer format
kotlineer hover src/Main.kt 10 5
```

### Subprocess spawn

Launches a new kotlin-lsp process for each invocation. Simpler setup but slower because the server must initialize on every call.

```bash
kotlineer --spawn check
```

## Global Options

| Option | Default | Description |
|--------|---------|-------------|
| `--connect HOST:PORT` | `localhost:8200` | Address of a running kotlin-lsp server |
| `--spawn` | off | Launch a new kotlin-lsp subprocess instead of connecting |
| `--server-path PATH` | `kotlin-lsp` | Path to kotlin-lsp binary (only with `--spawn`). Overridden by `KOTLINEER_SERVER` env var |
| `-w, --workspace DIR` | `.` (current dir) | Project root directory. kotlineer resolves relative file paths against this |
| `--timeout SECONDS` | `30` | Timeout for individual LSP requests in seconds |
| `--json` | off | Output results as JSON instead of human-readable text |
| `-v, --verbose` | off | Enable debug logging (LSP messages, server stderr, etc.) |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KOTLINEER_SERVER` | Default path to kotlin-lsp binary (used with `--spawn`). Overrides the `--server-path` default |

## Commands

### `check` — Run diagnostics

Analyze Kotlin files for errors, warnings, and other issues.

```
kotlineer check [OPTIONS] [FILES...]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `FILES` | Specific `.kt` files to check. If omitted, discovers all `.kt` files in the workspace recursively (ignoring `build/`, `.gradle/`, `.idea/`, `out/`, `.git/` directories) |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--errors-only` | off | Show only errors (severity 1), suppress warnings and hints |
| `--settle-time SECONDS` | `3` | After the last diagnostic update from the server, wait this long before considering analysis complete. Increase for large projects |

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | No issues found (or no files to check) |
| `1` | Diagnostics found |
| `2` | Unexpected error |

**Output format (text):**

```
path/to/File.kt:15:9: error: Unresolved reference: userRepo
path/to/File.kt:8:1: warning: Unused import directive
```

**Output format (JSON with `--json`):**

```json
{
  "/abs/path/to/File.kt": [
    {
      "line": 15,
      "col": 9,
      "severity": "error",
      "message": "Unresolved reference: userRepo"
    }
  ]
}
```

**Examples:**

```bash
# Check all files in the project
kotlineer check

# Check specific files
kotlineer check src/main/kotlin/com/example/UserService.kt

# Errors only, JSON output
kotlineer check --errors-only --json

# Large project — increase settle time
kotlineer check --settle-time 10

# With a higher timeout for slow servers
kotlineer --timeout 60 check
```

---

### `format` — Format code

Format Kotlin source files using the server's built-in formatter.

```
kotlineer format [OPTIONS] [FILES...]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `FILES` | Specific `.kt` files to format. If omitted, discovers all `.kt` files in the workspace |

**Options:**

| Option | Description |
|--------|-------------|
| `--check` | Dry run: print which files would be reformatted and exit with code 1 if any changes needed. Does not modify files |
| `--diff` | Print a unified diff of the formatting changes to stdout instead of writing files |

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | All files already formatted (or no files found) |
| `1` | Files need formatting (only with `--check`) |

**Examples:**

```bash
# Format all files in place
kotlineer format

# Format specific files
kotlineer format src/main/kotlin/com/example/UserService.kt

# CI: check if formatting is needed
kotlineer format --check

# Preview changes without writing
kotlineer format --diff
```

---

### `hover` — Type information

Get type information and documentation at a specific position in a file.

```
kotlineer hover FILE LINE COL
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `FILE` | Kotlin file path (absolute or relative to workspace) |
| `LINE` | Line number (1-based) |
| `COL` | Column number (1-based) |

**Examples:**

```bash
# Get type info at line 15, column 9
kotlineer hover src/main/kotlin/com/example/UserService.kt 15 9
# Output: fun findById(id: Long): User?

# JSON output for tooling
kotlineer --json hover src/main/kotlin/com/example/UserService.kt 15 9
```

---

### `definition` — Go to definition

Find the definition location of a symbol at a given position.

```
kotlineer definition FILE LINE COL
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `FILE` | Kotlin file path |
| `LINE` | Line number (1-based) |
| `COL` | Column number (1-based) |

**Output:**

```
/abs/path/to/UserRepository.kt:8:5
```

**Examples:**

```bash
kotlineer definition src/main/kotlin/com/example/UserService.kt 15 9

# JSON output
kotlineer --json definition src/main/kotlin/com/example/UserService.kt 15 9
```

---

### `references` — Find all references

Find all locations where a symbol is referenced.

```
kotlineer references FILE LINE COL
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `FILE` | Kotlin file path |
| `LINE` | Line number (1-based) |
| `COL` | Column number (1-based) |

**Output:**

```
/abs/path/to/UserService.kt:15:9
/abs/path/to/UserServiceTest.kt:22:13
```

**Examples:**

```bash
kotlineer references src/main/kotlin/com/example/UserRepository.kt 8 14
```

---

### `symbols` — List symbols

List symbols in a file or search for symbols across the workspace.

```
kotlineer symbols [FILE] [--query PATTERN]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `FILE` | Kotlin file path. Lists all symbols in this file (classes, functions, properties, etc.) |
| `--query, -q PATTERN` | Search for symbols by name across the entire workspace. Cannot be combined with FILE |

**Output (document symbols):**

```
Class UserService  (line 10)
  Method findById  (line 14)
  Method save  (line 20)
  Property repository  (line 11)
```

**Output (workspace symbols):**

```
Class UserService  (line 10)
Class UserRepository  (line 5)
```

**Examples:**

```bash
# Symbols in a file
kotlineer symbols src/main/kotlin/com/example/UserService.kt

# Search workspace
kotlineer symbols --query UserService

# JSON output
kotlineer --json symbols src/main/kotlin/com/example/UserService.kt
```
